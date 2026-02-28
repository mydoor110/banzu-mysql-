#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""人员管理 - 仪表盘路由"""
from flask import render_template, request, redirect, url_for, flash, jsonify, send_file, session, current_app

from config.settings import APP_TITLE, EXPORT_DIR
from models.database import get_db, close_db, get_year_month_concat
from ..decorators import login_required, manager_required
from ..helpers import (
    current_user_id, require_user_id, get_accessible_department_ids,
    get_accessible_departments, calculate_years_from_date, get_user_department,
    validate_employee_access, log_import_operation
)
from . import personnel_bp
from . import (
    PERSONNEL_FIELD_SCHEME, PERSONNEL_SELECT_OPTIONS,
    list_personnel, _serialize_person, _build_personnel_charts
)
import json
from datetime import date, datetime

@personnel_bp.route('/employees')
@login_required
def employees_legacy_redirect():
    """旧版employees路由重定向"""
    flash("花名册入口已升级为人员管理，请使用新页面。", "info")
    return redirect(url_for("personnel.index"))


@personnel_bp.route('/dashboard')
@login_required
def dashboard():
    """人员工作台首页"""
    # 先获取部门权限（内部会使用自己的数据库连接）
    accessible_dept_ids = get_accessible_department_ids()

    # 再获取新的数据库连接用于统计查询
    conn = get_db()
    cur = conn.cursor()

    # ===== 统计数据查询 =====
    # 1. 员工总数
    if accessible_dept_ids:
        placeholders = ','.join(['%s'] * len(accessible_dept_ids))
        cur.execute(f"SELECT COUNT(*) AS cnt FROM employees WHERE department_id IN ({placeholders})", accessible_dept_ids)
    else:
        cur.execute("SELECT COUNT(*) AS cnt FROM employees")
    employee_count = cur.fetchone()['cnt']

    # 2. 部门/班组数量
    if accessible_dept_ids:
        placeholders = ','.join(['%s'] * len(accessible_dept_ids))
        cur.execute(f"SELECT COUNT(*) AS cnt FROM departments WHERE id IN ({placeholders})", accessible_dept_ids)
    else:
        cur.execute("SELECT COUNT(*) AS cnt FROM departments")
    dept_count = cur.fetchone()['cnt']

    # 3. 培训覆盖率（有培训记录的员工 / 总员工数）
    try:
        if accessible_dept_ids:
            placeholders = ','.join(['%s'] * len(accessible_dept_ids))
            cur.execute(f"""
                SELECT COUNT(DISTINCT tr.emp_no) AS trained
                FROM training_records tr
                JOIN employees e ON tr.emp_no = e.emp_no
                WHERE e.department_id IN ({placeholders})
            """, accessible_dept_ids)
        else:
            cur.execute("SELECT COUNT(DISTINCT emp_no) AS trained FROM training_records")
        trained_count = cur.fetchone()['trained']
        training_coverage = round(trained_count / max(employee_count, 1) * 100, 1)
    except Exception:
        training_coverage = 0

    # 4. 风险预警数量（安全检查中未整改的记录）
    try:
        cur.execute("""
            SELECT COUNT(*) AS cnt FROM safety_inspection_records
            WHERE rectification_status IS NULL
               OR rectification_status = ''
               OR rectification_status = '未整改'
        """)
        risk_count = cur.fetchone()['cnt']
    except Exception:
        risk_count = 0

    dashboard_stats = {
        'employee_count': f"{employee_count:,}",
        'dept_count': dept_count,
        'training_coverage': f"{training_coverage}%",
        'risk_count': risk_count,
    }

    feature_cards = [
        {
            "title": "人员管理",
            "description": "管理员工基础档案信息，支持增删改查。",
            "endpoint": "personnel.index",
            "icon": "fas fa-users",
        },
        {
            "title": "数据分析",
            "description": "多维度的员工数据交叉分析。",
            "endpoint": "personnel.analytics",
            "icon": "fas fa-chart-pie",
        },
        {
            "title": "能力画像",
            "description": "查看员工个人综合能力雷达图。",
            "endpoint": "personnel.capability_profile",
            "icon": "fas fa-user-circle",
        },
        {
            "title": "人才九宫格",
            "description": "基于绩效和潜力的九宫格人才分布。",
            "endpoint": "personnel.page_nine_grid",
            "icon": "fas fa-th",
        },
        {
            "title": "风险挖掘",
            "description": "挖掘潜在的人员风险因素。",
            "endpoint": "personnel.risk_mining_page",
            "icon": "fas fa-search",
        },
        {
            "title": "导出 PPT 报告",
            "description": "按日期范围将统计图表和关键人员画像导出为演示文稿。",
            "endpoint": "export_ppt.ppt_export_page",
            "icon": "fas fa-file-powerpoint",
        },
    ]
    return render_template(
        "personnel_dashboard.html",
        title=f"人员工作台 | {APP_TITLE}",
        feature_cards=feature_cards,
        stats=dashboard_stats,
    )
