# -*- coding: utf-8 -*-
"""
PPT 导出 Blueprint
POST /api/export/ppt  → 权限 manager+

请求格式（JSON）:
{
    "start_date": "2026-01",
    "end_date":   "2026-02",
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

    # role 在登录时已写入 session，直接读取，无需再查库
    role = session.get('role', 'user')
    if role == 'user':
        flash('需要管理员权限才能使用导出功能', 'danger')
        return redirect(url_for('personnel.dashboard'))

    return render_template('ppt_export.html', title='导出综合能力报告 PPT')


def _get_user_info():
    """返回 (user_id, role, department_id)"""
    from models.database import get_db
    conn = get_db()
    cur  = conn.cursor()
    uid  = session.get('user_id')
    cur.execute("SELECT role, department_id FROM users WHERE id = %s", (uid,))
    row = cur.fetchone()
    if not row:
        return uid, 'user', None
    return uid, row['role'], row['department_id']


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
    """直接调用 comprehensive-profile 核心逻辑（绕过 HTTP，在同一进程内完成）"""
    try:
        from flask import current_app
        params = {}
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date

        # 用 test_client 发内部请求，携带当前 session cookie
        client = current_app.test_client()
        session_cookie = request.cookies.get('session', '')

        # 构建查询字符串
        from urllib.parse import urlencode
        qs = urlencode(params)
        url = f"/personnel/api/comprehensive-profile/{emp_no}"
        if qs:
            url = f"{url}?{qs}"

        # 传递 session cookie 实现权限穿透
        environ_base = {}
        if session_cookie:
            environ_base['HTTP_COOKIE'] = f"session={session_cookie}"

        resp = client.get(url, environ_base=environ_base)
        if resp.status_code == 200:
            return resp.get_json() or {}
    except Exception as e:
        print(f"[_load_person_profile] 内部调用失败: {e}")
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
    start_date    = body.get('start_date', '')
    end_date      = body.get('end_date', '')
    module_slides = body.get('module_slides', [])   # list of {title, images, note}
    nine_grid_img = body.get('nine_grid_image', '')
    key_emp_nos   = body.get('key_persons', [])     # list of emp_no strings
    theme         = body.get('theme', 'blue')       # e.g., 'blue', 'dark', 'simple'
    summary_data  = body.get('summary_data', None)  # 执行摘要数据

    if not module_slides and not key_emp_nos:
        return jsonify({'error': '请提供图表数据或关键人员'}), 400

    # ── 权限过滤关键人员 ──────────────────────────────────────────────────────
    if role == 'manager' and dept_id:
        key_emp_nos = [e for e in key_emp_nos if _belongs_to_dept(e, dept_id)]

    # ── 构建关键人员数据 ───────────────────────────────────────────────────────
    key_persons = []
    person_profiles_from_frontend = body.get('person_profiles', {})  # 前端已查好的profile

    for emp_no in key_emp_nos:
        # 优先使用前端传来的 profile（前端已成功调用 comprehensive-profile API）
        profile = person_profiles_from_frontend.get(emp_no)
        if not profile:
            # 降级：后端再查一次
            profile = _load_person_profile(emp_no, start_date, end_date)

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
            start_date    = start_date,
            end_date      = end_date,
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
    date_tag = f"{start_date}_{end_date}".replace('-', '').replace('__', '_')
    filename = f"人员综合能力报告_{date_tag}.pptx"

    return send_file(
        io.BytesIO(pptx_bytes),
        mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
        as_attachment=True,
        download_name=filename
    )
