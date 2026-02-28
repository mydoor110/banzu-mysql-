#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人员管理模块
负责员工信息管理、导入导出等功能
"""
import json
import os
import pymysql
from collections import Counter
from datetime import date, datetime, timedelta
from io import BytesIO
from typing import Dict, List, Optional

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, session, current_app
from openpyxl import Workbook, load_workbook

from config.settings import APP_TITLE, EXPORT_DIR
from models.database import get_db, close_db, get_year_month_concat
from ..decorators import login_required, manager_required
from ..helpers import (
    current_user_id, require_user_id, get_accessible_department_ids,
    get_accessible_departments, calculate_years_from_date, get_user_department,
    validate_employee_access, log_import_operation
)
from services.domain.safety_utils import extract_score_from_assessment

# 创建 Blueprint
personnel_bp = Blueprint('personnel', __name__, url_prefix='/personnel')


# ==================== 常量定义 ====================

PERSONNEL_FIELD_SCHEME = [
    {"name": "emp_no", "label": "工号", "input_type": "text", "required": True},
    {"name": "name", "label": "姓名", "input_type": "text", "required": True},
    {"name": "department_id", "label": "所属部门", "input_type": "department_select", "required": True},
    {"name": "class_name", "label": "班级", "input_type": "text"},
    {"name": "position", "label": "岗位", "input_type": "text"},
    {"name": "birth_date", "label": "出生年月", "input_type": "date"},
    {"name": "certification_date", "label": "取证时间", "input_type": "date"},
    {"name": "solo_driving_date", "label": "单独驾驶时间", "input_type": "date"},
    {"name": "marital_status", "label": "婚姻状况", "input_type": "select"},
    {"name": "hometown", "label": "籍贯", "input_type": "text"},
    {"name": "political_status", "label": "政治面貌", "input_type": "select"},
    {"name": "education", "label": "学历", "input_type": "select"},
    {"name": "graduation_school", "label": "毕业院校", "input_type": "text"},
    {"name": "work_start_date", "label": "参加工作时间", "input_type": "date"},
    {"name": "entry_date", "label": "入司时间", "input_type": "date"},
    {"name": "specialty", "label": "特长及兴趣爱好", "input_type": "textarea"},
]

PERSONNEL_DB_COLUMNS = [
    field["name"] for field in PERSONNEL_FIELD_SCHEME if field["name"] not in {"emp_no", "name"}
]

PERSONNEL_DATE_FIELDS = {"birth_date", "work_start_date", "entry_date", "certification_date", "solo_driving_date"}

PERSONNEL_SELECT_OPTIONS = {
    "marital_status": ["未婚", "已婚", "离异", "其它"],
    "political_status": ["中共党员", "中共预备党员", "共青团员", "群众", "其它"],
    "education": ["博士研究生", "硕士研究生", "本科", "大专", "中专", "高中", "其它"],
}

PERSONNEL_IMPORT_HEADER_MAP = {
    "工号": "emp_no",
    "姓名": "name",
    "所属部门": "department_id",
    "部门": "department_id",
    "班级": "class_name",
    "岗位": "position",
    "出生年月": "birth_date",
    "取证时间": "certification_date",
    "取证日期": "certification_date",
    "单独驾驶时间": "solo_driving_date",
    "单独驾驶日期": "solo_driving_date",
    "婚否": "marital_status",
    "婚姻状况": "marital_status",
    "籍贯": "hometown",
    "政治面貌": "political_status",
    "特长及兴趣爱好": "specialty",
    "特长": "specialty",
    "学历": "education",
    "毕业院校": "graduation_school",
    "参加工作时间": "work_start_date",
    "入司时间": "entry_date",
}


# ==================== 算法函数 ====================
# 核心算法已迁移到 services/domain/personnel_algo.py
# 此处保留 re-export 以确保向后兼容
from services.domain.personnel_algo import (
    calculate_learning_ability_monthly,
    calculate_learning_ability_longterm,
    calculate_stability_score,
    calculate_stability_score_new,
    calculate_stability_period_aggregated,
    calculate_inertia_penalty,
    calculate_learning_ability_new,
    calculate_stability_for_employee,
    _month_index,
    _month_shift,
    _month_range,
    _resolve_stability_window,
    _load_monthly_safety_violations,
    _build_monthly_safety_scores,
    _parse_date_string,
    _normalize_date_to_str,
    _calculate_age,
    _calculate_years_since,
    _serialize_person,
    _build_personnel_charts,
)



# ==================== 数据库访问函数 ====================

def list_personnel():
    """列出所有可访问的人员"""
    from flask import session
    user_role = session.get('role', 'user')

    conn = get_db()
    cur = conn.cursor()

    # 管理员可以看到所有员工，其他角色只能看到可访问部门的员工
    if user_role == 'admin':
        query = """
            SELECT e.emp_no, e.name, e.department_id, d.name as department_name,
                   e.class_name, e.position, e.birth_date, e.certification_date,
                   e.solo_driving_date, e.marital_status, e.hometown,
                   e.political_status, e.education, e.graduation_school,
                   e.work_start_date, e.entry_date, e.specialty
            FROM employees e
            LEFT JOIN departments d ON e.department_id = d.id
            ORDER BY CAST(e.emp_no AS SIGNED)
        """
        try:
            cur.execute(query)
        except Exception:
            cur.execute(query.replace("CAST(e.emp_no AS SIGNED)", "e.emp_no"))
    else:
        accessible_dept_ids = get_accessible_department_ids()
        if not accessible_dept_ids:
            return []

        placeholders = ','.join(['%s'] * len(accessible_dept_ids))
        query = f"""
            SELECT e.emp_no, e.name, e.department_id, d.name as department_name,
                   e.class_name, e.position, e.birth_date, e.certification_date,
                   e.solo_driving_date, e.marital_status, e.hometown,
                   e.political_status, e.education, e.graduation_school,
                   e.work_start_date, e.entry_date, e.specialty
            FROM employees e
            LEFT JOIN departments d ON e.department_id = d.id
            WHERE e.department_id IN ({placeholders})
            ORDER BY CAST(e.emp_no AS SIGNED)
        """
        try:
            cur.execute(query, accessible_dept_ids)
        except Exception:
            cur.execute(
                query.replace("CAST(e.emp_no AS SIGNED)", "e.emp_no"),
                accessible_dept_ids,
            )

    rows = cur.fetchall()
    result = []
    for row in rows:
        person_dict = _serialize_person(row)
        # 添加计算字段
        if person_dict.get('certification_date'):
            person_dict['certification_years'] = calculate_years_from_date(person_dict['certification_date'])
        else:
            person_dict['certification_years'] = None

        if person_dict.get('solo_driving_date'):
            person_dict['solo_driving_years'] = calculate_years_from_date(person_dict['solo_driving_date'])
        else:
            person_dict['solo_driving_years'] = None

        result.append(person_dict)

    return result


def get_personnel(emp_no: str) -> Optional[Dict]:
    """获取指定工号的人员信息"""
    uid = require_user_id()

    # 🔒 权限检查: 非管理员需要验证是否有权访问该员工
    from flask import session
    user_role = session.get('role', 'user')
    if user_role != 'admin':
        if not validate_employee_access(emp_no):
            return None

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT e.emp_no, e.name, e.department_id, d.name as department_name,
               e.class_name, e.position, e.birth_date, e.certification_date,
               e.solo_driving_date, e.marital_status, e.hometown,
               e.political_status, e.education, e.graduation_school,
               e.work_start_date, e.entry_date, e.specialty, e.created_at
        FROM employees e
        LEFT JOIN departments d ON e.department_id = d.id
        WHERE e.emp_no=%s
        """,
        (emp_no,),
    )
    row = cur.fetchone()
    if not row:
        return None

    person_dict = _serialize_person(row)
    # 添加计算字段
    if person_dict.get('certification_date'):
        person_dict['certification_years'] = calculate_years_from_date(person_dict['certification_date'])
    if person_dict.get('solo_driving_date'):
        person_dict['solo_driving_years'] = calculate_years_from_date(person_dict['solo_driving_date'])

    return person_dict


def _sanitize_person_payload(data: Dict[str, Optional[str]]) -> Dict[str, Optional[str]]:
    """清理和标准化人员数据"""
    sanitized: Dict[str, Optional[str]] = {}
    for field in PERSONNEL_DB_COLUMNS + ["emp_no", "name"]:
        if field == "emp_no":
            value = str(data.get(field) or "").strip()
            sanitized[field] = value or None
            continue
        raw_val = data.get(field)
        if raw_val is None:
            sanitized[field] = None
            continue
        if field in PERSONNEL_DATE_FIELDS:
            sanitized[field] = _normalize_date_to_str(raw_val)
        else:
            sanitized[field] = str(raw_val).strip() or None
    return sanitized


def upsert_personnel(data: Dict[str, Optional[str]]) -> bool:
    """插入或更新人员信息"""
    payload = _sanitize_person_payload(data)
    emp_no = payload.get("emp_no")
    name = payload.get("name")
    department_id = payload.get("department_id")

    if not emp_no or not name:
        return False

    # department_id是必填项，如果没有提供则返回False
    if department_id is None or department_id == "":
        return False

    # 转换department_id为整数
    try:
        department_id = int(department_id)
    except (ValueError, TypeError):
        return False

    uid = require_user_id()
    conn = get_db()
    cur = conn.cursor()

    # 注意: UNIQUE约束是emp_no（全局唯一），数据以department_id为基准隔离
    columns = ["emp_no", "name", "created_by", "department_id"] + [col for col in PERSONNEL_DB_COLUMNS if col != "department_id"]
    values = [emp_no, name, uid, department_id] + [payload.get(col) for col in PERSONNEL_DB_COLUMNS if col != "department_id"]
    update_clause = ", ".join(
        f"{col}=VALUES({col})" for col in ["name", "department_id"] + [col for col in PERSONNEL_DB_COLUMNS if col != "department_id"]
    )
    cur.execute(
        f"""
        INSERT INTO employees ({", ".join(columns)})
        VALUES ({", ".join(["%s"] * len(columns))})
        ON DUPLICATE KEY UPDATE {update_clause}
        """,
        values,
    )
    conn.commit()
    return True


def bulk_import_personnel(records: List[Dict[str, Optional[str]]]) -> int:
    """批量导入人员信息"""
    imported = 0
    for record in records:
        if upsert_personnel(record):
            imported += 1
    return imported


def update_personnel_field(emp_no: str, field: str, value: Optional[str]) -> bool:
    """更新人员的单个字段"""
    if field not in {"name", *PERSONNEL_DB_COLUMNS}:
        return False

    # 🔒 权限检查: 非管理员需要验证是否有权修改该员工
    from flask import session
    user_role = session.get('role', 'user')
    if user_role != 'admin':
        if not validate_employee_access(emp_no):
            return False

    payload = _sanitize_person_payload({field: value})
    uid = require_user_id()
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        f"""
        UPDATE employees
        SET {field} = %s
        WHERE emp_no=%s
        """,
        (payload.get(field), emp_no),
    )
    conn.commit()
    affected = cur.rowcount > 0
    return affected


def delete_employee(emp_no):
    """删除员工"""
    uid = require_user_id()

    # 🔒 权限检查: 非管理员需要验证是否有权删除该员工
    from flask import session
    user_role = session.get('role', 'user')
    if user_role != 'admin':
        if not validate_employee_access(emp_no):
            return False

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM employees WHERE emp_no=%s", (emp_no,))
    conn.commit()
    return True


# ==================== 路由处理 ====================



# ==================== 路由子模块 ====================
# 路由按业务子域拆分，此处导入以注册到 personnel_bp
from . import routes_crud       # noqa: F401, E402
from . import routes_dashboard  # noqa: F401, E402
from . import routes_analytics  # noqa: F401, E402
from . import routes_ai         # noqa: F401, E402
