# -*- coding: utf-8 -*-
"""PPT 导出 Blueprint。"""
from flask import Blueprint, request, jsonify, session, send_file, render_template
import io

export_ppt_bp = Blueprint('export_ppt', __name__)


@export_ppt_bp.route('/export/ppt')
def ppt_export_page():
    """PPT 导出入口，统一跳转到配置页。"""
    from flask import redirect, url_for, flash
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    # P1 统一出口
    from services.access_control_service import AccessControlService
    if not AccessControlService.has_permission('manager'):
        flash('需要管理员权限才能使用导出功能', 'danger')
        return redirect(url_for('personnel.dashboard'))

    flash('PPT 导出已切换到新配置页。', 'info')
    return redirect(url_for('export_ppt.ppt_export_config_page'))


@export_ppt_bp.route('/export/ppt/config')
def ppt_export_config_page():
    """PPT 导出配置页。"""
    from flask import redirect, url_for, flash
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    from services.access_control_service import AccessControlService
    if not AccessControlService.has_permission('manager'):
        flash('需要管理员权限才能使用导出功能', 'danger')
        return redirect(url_for('personnel.dashboard'))

    return render_template('ppt_export_config.html', title='配置 PPT 导出')


def _get_user_info():
    """返回 (user_id, role, department_id)（P1 统一出口）"""
    from services.access_control_service import AccessControlService
    ctx = AccessControlService.get_current_user_context()
    uid = session.get('user_id')
    if ctx:
        return uid, ctx.get('role', 'user'), ctx.get('department_id')
    # fallback
    role = AccessControlService.get_current_role() or 'user'
    dept_info = AccessControlService.get_user_department_info()
    dept_id = dept_info.get('department_id') if dept_info else None
    return uid, role, dept_id


def _belongs_to_dept(emp_no: str, dept_id: int) -> bool:
    """判断员工是否属于指定部门（含子部门）"""
    try:
        from models.database import get_db
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            SELECT e.id FROM employees e
            JOIN departments d ON e.department_id = d.id
            WHERE e.emp_no = %s AND (
                e.department_id = %s
                OR d.path LIKE CONCAT(
                    (SELECT path FROM departments WHERE id = %s), '/%')
            )
        """, (emp_no, dept_id, dept_id))
        return cur.fetchone() is not None
    except Exception:
        return True  # 查询失败默认放行，不阻断导出


def _load_person_profile(emp_no: str, start_date: str, end_date: str) -> dict:
    """直接调用 ComprehensiveProfileService（无 HTTP 开销，同一进程内完成）

    Args:
        emp_no: 员工工号
        start_date: 开始日期 (YYYY-MM-DD 格式)
        end_date: 结束日期 (YYYY-MM-DD 格式)
    """
    try:
        from services.comprehensive_profile_service import ComprehensiveProfileService
        result = ComprehensiveProfileService.get_profile(emp_no, start_date, end_date)
        return result or {}
    except Exception as e:
        print(f"[_load_person_profile] Service 调用失败: {e}")
    return {}


def _get_employee_info(emp_no: str) -> dict:
    """获取员工姓名和部门"""
    try:
        from models.database import get_db
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            SELECT e.name, d.name as dept_name
            FROM employees e
            LEFT JOIN departments d ON e.department_id = d.id
            WHERE e.emp_no = %s
        """, (emp_no,))
        row = cur.fetchone()
        if row:
            return {'name': row['name'], 'department': row['dept_name'] or ''}
    except Exception:
        pass
    return {'name': emp_no, 'department': ''}


@export_ppt_bp.route('/api/export/ppt', methods=['POST'])
def export_ppt_v2():
    """
    PPT 导出接口。
    接收 export_config + raw_images → builder 组装 → PPTExportService

    请求格式（JSON）：
    {
        "start_month": "2026-01",
        "end_month":   "2026-02",
        "theme":       "blue",
        "template_id": 1,          // 可选，企业模板 ID
        "export_config": {
            "chartConfigs": { "<chartId>": { "selected": true, ... } },
            "appendSummaryGlobal": true,
            "enhance": { "trendEnabled": true, ... }
        },
        "raw_images": {
            "<chartId>": {
                "image": "<base64>", "title": "...", "hint": "...",
                "moduleKey": "safety", "pptEnhance": {...},
                "enhanceData": null, "summaryData": null
            }
        },
        "key_persons":     [],
        "radar_images":    {},
        "person_profiles": {}
    }
    """
    if not session.get('logged_in'):
        return jsonify({'error': '请先登录'}), 401

    user_id, role, dept_id = _get_user_info()
    if role == 'user':
        return jsonify({'error': '权限不足，需要管理员权限'}), 403

    body = request.get_json(silent=True) or {}
    start_month   = body.get('start_month', '')
    end_month     = body.get('end_month', '')
    theme         = body.get('theme', 'blue')
    template_id   = body.get('template_id')
    export_config = body.get('export_config') or {}
    raw_images    = body.get('raw_images') or {}
    key_emp_nos   = body.get('key_persons', [])
    summary_data  = body.get('summary_data', None)

    if not raw_images:
        return jsonify({'error': '图像资产（raw_images）为空，请检查截图是否完成'}), 400

    # ── 中间层：组装 module_slides ─────────────────────────────────────────────
    from services.export_config_builder import build_module_slides_from_config
    module_slides = build_module_slides_from_config(export_config, raw_images)

    if not module_slides and not key_emp_nos:
        return jsonify({'error': '没有选中任何图表，或截图数据为空'}), 400

    # ── 权限过滤关键人员 ──────────────────────────────────────────────────────
    from blueprints.helpers import month_range_to_dates
    start_date_std, end_date_std = month_range_to_dates(start_month, end_month)

    if role == 'manager' and dept_id:
        key_emp_nos = [e for e in key_emp_nos if _belongs_to_dept(e, dept_id)]

    # ── 构建关键人员数据 ───────────────────────────────────────────────────────
    key_persons = []
    person_profiles_from_frontend = body.get('person_profiles', {})

    for emp_no in key_emp_nos:
        profile = person_profiles_from_frontend.get(emp_no)
        if not profile:
            profile = _load_person_profile(emp_no, start_date_std, end_date_std)
        emp_info = _get_employee_info(emp_no)
        radar_img = body.get('radar_images', {}).get(emp_no, '')
        key_persons.append({
            'name':        emp_info['name'],
            'emp_no':      emp_no,
            'department':  emp_info['department'],
            'radar_image': radar_img,
            'scores':      profile.get('scores', {}),
            'details':     profile,
        })

    # ── 读取模板配置 ──────────────────────────────────────────────────────────
    template_config = None
    if template_id:
        template_config = _load_template(template_id)

    # ── 生成 PPT ──────────────────────────────────────────────────────────────
    from services.ppt_export_service import PPTExportService

    try:
        svc = PPTExportService(theme_name=theme, template_config=template_config)
        pptx_bytes = svc.generate(
            start_date      = start_month,
            end_date        = end_month,
            module_slides   = module_slides,
            nine_grid_image = '',
            key_persons     = key_persons,
            summary_data    = summary_data,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'PPT生成失败：{e}'}), 500

    date_tag = f"{start_month}_{end_month}".replace('-', '').replace('__', '_')
    filename = f"人员综合能力报告_{date_tag}.pptx"

    return send_file(
        io.BytesIO(pptx_bytes),
        mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
        as_attachment=True,
        download_name=filename
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PPT 模板 CRUD API
# ═══════════════════════════════════════════════════════════════════════════════

def _load_template(template_id):
    """根据 ID 从数据库读取模板配置，返回 dict 或 None"""
    try:
        from models.database import get_db
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM ppt_templates WHERE id = %s", (template_id,))
        row = cur.fetchone()
        if row:
            return dict(row)
    except Exception as e:
        print(f"[_load_template] 读取模板失败: {e}")
    return None


@export_ppt_bp.route('/api/ppt-templates', methods=['GET'])
def list_ppt_templates():
    """获取所有 PPT 模板列表（不含大字段 logo_image / end_page_background）"""
    if not session.get('logged_in'):
        return jsonify({'error': '请先登录'}), 401

    try:
        from models.database import get_db
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, template_name, primary_color, secondary_color,
                   title_color, footer_color, font_family,
                   end_page_title, end_page_subtitle, is_default,
                   created_at, updated_by,
                   CASE WHEN logo_image IS NOT NULL AND logo_image != '' THEN 1 ELSE 0 END AS has_logo,
                   CASE WHEN end_page_background IS NOT NULL AND end_page_background != '' THEN 1 ELSE 0 END AS has_end_bg
            FROM ppt_templates
            ORDER BY is_default DESC, id ASC
        """)
        rows = cur.fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({'error': f'查询失败: {e}'}), 500


@export_ppt_bp.route('/api/ppt-templates/<int:tpl_id>', methods=['GET'])
def get_ppt_template(tpl_id):
    """获取单个模板完整数据（含大字段）"""
    if not session.get('logged_in'):
        return jsonify({'error': '请先登录'}), 401

    try:
        from models.database import get_db
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM ppt_templates WHERE id = %s", (tpl_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': '模板不存在'}), 404
        return jsonify(dict(row))
    except Exception as e:
        return jsonify({'error': f'查询失败: {e}'}), 500


@export_ppt_bp.route('/api/ppt-templates', methods=['POST'])
def create_ppt_template():
    """新增 PPT 模板"""
    if not session.get('logged_in'):
        return jsonify({'error': '请先登录'}), 401

    from services.access_control_service import AccessControlService
    if not AccessControlService.has_permission('admin'):
        return jsonify({'error': '需要系统管理员权限'}), 403

    body = request.get_json(silent=True) or {}
    name = (body.get('template_name') or '').strip()
    if not name:
        return jsonify({'error': '模板名称不能为空'}), 400

    try:
        from models.database import get_db
        conn = get_db()
        cur = conn.cursor()

        # 如果设为默认，先取消其他默认
        if body.get('is_default'):
            cur.execute("UPDATE ppt_templates SET is_default = 0 WHERE is_default = 1")

        cur.execute("""
            INSERT INTO ppt_templates
                (template_name, logo_image, end_page_background,
                 primary_color, secondary_color, title_color, footer_color,
                 font_family, end_page_title, end_page_subtitle,
                 is_default, updated_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            name,
            body.get('logo_image') or None,
            body.get('end_page_background') or None,
            body.get('primary_color') or '#1A56DB',
            body.get('secondary_color') or '#DC3545',
            body.get('title_color') or None,
            body.get('footer_color') or None,
            body.get('font_family') or None,
            body.get('end_page_title') or None,
            body.get('end_page_subtitle') or None,
            1 if body.get('is_default') else 0,
            session.get('user_id')
        ))
        conn.commit()
        new_id = cur.lastrowid
        return jsonify({'id': new_id, 'message': '模板创建成功'})
    except Exception as e:
        return jsonify({'error': f'创建失败: {e}'}), 500


@export_ppt_bp.route('/api/ppt-templates/<int:tpl_id>', methods=['PUT'])
def update_ppt_template(tpl_id):
    """编辑 PPT 模板"""
    if not session.get('logged_in'):
        return jsonify({'error': '请先登录'}), 401

    from services.access_control_service import AccessControlService
    if not AccessControlService.has_permission('admin'):
        return jsonify({'error': '需要系统管理员权限'}), 403

    body = request.get_json(silent=True) or {}
    name = (body.get('template_name') or '').strip()
    if not name:
        return jsonify({'error': '模板名称不能为空'}), 400

    try:
        from models.database import get_db
        conn = get_db()
        cur = conn.cursor()

        # 检查是否存在
        cur.execute("SELECT id FROM ppt_templates WHERE id = %s", (tpl_id,))
        if not cur.fetchone():
            return jsonify({'error': '模板不存在'}), 404

        # 如果设为默认，先取消其他默认
        if body.get('is_default'):
            cur.execute("UPDATE ppt_templates SET is_default = 0 WHERE is_default = 1 AND id != %s", (tpl_id,))

        cur.execute("""
            UPDATE ppt_templates SET
                template_name = %s,
                logo_image = %s,
                end_page_background = %s,
                primary_color = %s,
                secondary_color = %s,
                title_color = %s,
                footer_color = %s,
                font_family = %s,
                end_page_title = %s,
                end_page_subtitle = %s,
                is_default = %s,
                updated_by = %s
            WHERE id = %s
        """, (
            name,
            body.get('logo_image') or None,
            body.get('end_page_background') or None,
            body.get('primary_color') or '#1A56DB',
            body.get('secondary_color') or '#DC3545',
            body.get('title_color') or None,
            body.get('footer_color') or None,
            body.get('font_family') or None,
            body.get('end_page_title') or None,
            body.get('end_page_subtitle') or None,
            1 if body.get('is_default') else 0,
            session.get('user_id'),
            tpl_id
        ))
        conn.commit()
        return jsonify({'message': '模板更新成功'})
    except Exception as e:
        return jsonify({'error': f'更新失败: {e}'}), 500


@export_ppt_bp.route('/api/ppt-templates/<int:tpl_id>', methods=['DELETE'])
def delete_ppt_template(tpl_id):
    """删除 PPT 模板"""
    if not session.get('logged_in'):
        return jsonify({'error': '请先登录'}), 401

    from services.access_control_service import AccessControlService
    if not AccessControlService.has_permission('admin'):
        return jsonify({'error': '需要系统管理员权限'}), 403

    try:
        from models.database import get_db
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM ppt_templates WHERE id = %s", (tpl_id,))
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({'error': '模板不存在'}), 404
        return jsonify({'message': '模板删除成功'})
    except Exception as e:
        return jsonify({'error': f'删除失败: {e}'}), 500
