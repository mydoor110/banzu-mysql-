# -*- coding: utf-8 -*-
"""
PPT 导出 Blueprint
POST /api/export/ppt  → 权限 manager+

请求格式（JSON）:
{
    "start_month": "2026-01",
    "end_month":   "2026-02",
    "module_slides": [
        {
            "title":  "人员数据分析",
            "images": ["<base64>", "<base64>"],   // 1或2张
            "note":   "..."                        // 可选说明
        },
        ...
    ],
    "nine_grid_image": "<base64>",     // 九宫格截图
    "key_persons":     ["EMP001", ...]  // 工号列表（用户勾选）
}
"""
from flask import Blueprint, request, jsonify, session, send_file, render_template
import io

export_ppt_bp = Blueprint('export_ppt', __name__)


@export_ppt_bp.route('/export/ppt')
def ppt_export_page():
    """PPT 导出独立页面（人员管理工作台入口）"""
    from flask import redirect, url_for, flash
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    # P1 统一出口
    from services.access_control_service import AccessControlService
    if not AccessControlService.has_permission('manager'):
        flash('需要管理员权限才能使用导出功能', 'danger')
        return redirect(url_for('personnel.dashboard'))

    return render_template('ppt_export.html', title='导出综合能力报告 PPT')


@export_ppt_bp.route('/export/ppt/config')
def ppt_export_config_page():
    """PPT 导出新配置页（Phase 1 新建，与旧页面并行运行）"""
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
def export_ppt():
    # ── 权限检查 ──────────────────────────────────────────────────────────────
    if not session.get('logged_in'):
        return jsonify({'error': '请先登录'}), 401

    user_id, role, dept_id = _get_user_info()
    if role == 'user':
        return jsonify({'error': '权限不足，需要管理员权限'}), 403

    # ── 解析请求 ──────────────────────────────────────────────────────────────
    body = request.get_json(silent=True) or {}
    start_month   = body.get('start_month', '')
    end_month     = body.get('end_month', '')
    module_slides = body.get('module_slides', [])   # list of {title, images, note}
    nine_grid_img = body.get('nine_grid_image', '')
    key_emp_nos   = body.get('key_persons', [])     # list of emp_no strings
    theme         = body.get('theme', 'blue')       # e.g., 'blue', 'dark', 'simple'
    summary_data  = body.get('summary_data', None)  # 执行摘要数据

    # 标准化日期：月份 → YYYY-MM-DD（Service 层统一接收标准日期）
    from blueprints.helpers import month_range_to_dates
    start_date_std, end_date_std = month_range_to_dates(start_month, end_month)

    if not module_slides and not key_emp_nos:
        return jsonify({'error': '请提供图表数据或关键人员'}), 400

    # ── 权限过滤关键人员 ──────────────────────────────────────────────────────
    if role == 'manager' and dept_id:
        key_emp_nos = [e for e in key_emp_nos if _belongs_to_dept(e, dept_id)]

    # ── 构建关键人员数据 ───────────────────────────────────────────────────────
    key_persons = []
    person_profiles_from_frontend = body.get('person_profiles', {})  # 前端已查好的profile

    for emp_no in key_emp_nos:
        profile = person_profiles_from_frontend.get(emp_no)
        if not profile:
            profile = _load_person_profile(emp_no, start_date_std, end_date_std)

        emp_info = _get_employee_info(emp_no)
        radar_img  = body.get('radar_images', {}).get(emp_no, '')

        key_persons.append({
            'name':       emp_info['name'],
            'emp_no':     emp_no,
            'department': emp_info['department'],
            'radar_image':radar_img,
            'scores':     profile.get('scores', {}),
            'details':    profile,
        })

    # ── 生成 PPT ──────────────────────────────────────────────────────────────
    from services.ppt_export_service import PPTExportService

    try:
        svc = PPTExportService(theme_name=theme)
        pptx_bytes = svc.generate(
            start_date    = start_month,
            end_date      = end_month,
            module_slides = module_slides,
            nine_grid_image = nine_grid_img,
            key_persons   = key_persons,
            summary_data  = summary_data,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'PPT生成失败：{e}'}), 500

    # ── 返回文件 ──────────────────────────────────────────────────────────────
    date_tag = f"{start_month}_{end_month}".replace('-', '').replace('__', '_')
    filename = f"人员综合能力报告_{date_tag}.pptx"

    return send_file(
        io.BytesIO(pptx_bytes),
        mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
        as_attachment=True,
        download_name=filename
    )


@export_ppt_bp.route('/api/export/ppt/v2', methods=['POST'])
def export_ppt_v2():
    """
    PPT 导出 v2 接口（Phase 2 新建）
    接收新协议：export_config + raw_images → builder 组装 → PPTExportService
    与旧 /api/export/ppt 并行，验证通过后切换配置页调用目标。

    请求格式（JSON）：
    {
        "start_month": "2026-01",
        "end_month":   "2026-02",
        "theme":       "blue",
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

    # ── 生成 PPT ──────────────────────────────────────────────────────────────
    from services.ppt_export_service import PPTExportService

    try:
        svc = PPTExportService(theme_name=theme)
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

