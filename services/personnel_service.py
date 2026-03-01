#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人员管理服务层

从 blueprints/personnel/__init__.py 迁移而来的业务逻辑：
- list_personnel / get_personnel
- _sanitize_person_payload / upsert_personnel / bulk_import_personnel
- update_personnel_field / delete_employee

所有函数使用 g.user_ctx 进行权限判断，不直接读取 session['role']。
写操作使用 db_transaction() 管理事务边界。
"""
from typing import Dict, List, Optional

from flask import g

from models.database import get_db
from models.db_transaction import db_transaction
from services.access_control_service import AccessControlService
from services.domain.personnel_algo import calculate_years_from_date

# P1.2：常量现在从 service 领域层导入，不再反向依赖 Blueprint
_CACHED_CONSTANTS = {}


def _get_constants():
    """加载 personnel 领域常量"""
    if not _CACHED_CONSTANTS:
        from services.domain.personnel_constants import PERSONNEL_DB_COLUMNS, PERSONNEL_DATE_FIELDS
        from services.domain.personnel_algo import _normalize_date_to_str, _serialize_person
        _CACHED_CONSTANTS['PERSONNEL_DB_COLUMNS'] = PERSONNEL_DB_COLUMNS
        _CACHED_CONSTANTS['PERSONNEL_DATE_FIELDS'] = PERSONNEL_DATE_FIELDS
        _CACHED_CONSTANTS['_normalize_date_to_str'] = _normalize_date_to_str
        _CACHED_CONSTANTS['_serialize_person'] = _serialize_person
    return _CACHED_CONSTANTS


def _get_user_role() -> str:
    """从 AccessControlService 获取当前用户角色（P1 统一出口）"""
    return AccessControlService.get_current_role() or 'user'


def _require_user_id():
    """获取当前用户 ID，未登录则抛出异常

    P1.2：从 helpers.require_user_id 下沉，避免 service → blueprint 反向依赖。
    """
    from flask import session
    uid = session.get('user_id')
    if not uid:
        raise RuntimeError("No current user id in session")
    return uid


def list_personnel():
    """列出所有可访问的人员"""
    user_role = _get_user_role()

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
        accessible_dept_ids = AccessControlService.get_accessible_department_ids()
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
    c = _get_constants()
    _serialize = c['_serialize_person']
    result = []
    for row in rows:
        person_dict = _serialize(row)
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
    uid = _require_user_id()

    # 🔒 权限检查: 非管理员需要验证是否有权访问该员工
    user_role = _get_user_role()
    if user_role != 'admin':
        if not AccessControlService.validate_employee_access(emp_no):
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

    c = _get_constants()
    person_dict = c['_serialize_person'](row)
    # 添加计算字段
    if person_dict.get('certification_date'):
        person_dict['certification_years'] = calculate_years_from_date(person_dict['certification_date'])
    if person_dict.get('solo_driving_date'):
        person_dict['solo_driving_years'] = calculate_years_from_date(person_dict['solo_driving_date'])

    return person_dict


def _sanitize_person_payload(data: Dict[str, Optional[str]]) -> Dict[str, Optional[str]]:
    """清理和标准化人员数据"""
    c = _get_constants()
    PERSONNEL_DB_COLUMNS = c['PERSONNEL_DB_COLUMNS']
    PERSONNEL_DATE_FIELDS = c['PERSONNEL_DATE_FIELDS']
    _normalize_date_to_str = c['_normalize_date_to_str']

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


def _upsert_single(payload: Dict, uid: int, cur) -> bool:
    """单条 upsert（无事务，由调用方管理事务边界）

    P1.3：内部实现，供 upsert_personnel 和 bulk_import_personnel 共用。
    不包含事务管理，不做 commit/rollback。

    Args:
        payload: 已经过 _sanitize_person_payload 处理的数据
        uid: 操作用户 ID
        cur: 数据库游标（外部管理事务）

    Returns:
        bool: 是否执行成功
    """
    emp_no = payload.get("emp_no")
    name = payload.get("name")
    department_id = payload.get("department_id")

    if not emp_no or not name:
        return False
    if department_id is None or department_id == "":
        return False
    try:
        department_id = int(department_id)
    except (ValueError, TypeError):
        return False

    c = _get_constants()
    PERSONNEL_DB_COLUMNS = c['PERSONNEL_DB_COLUMNS']
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
    return True


def upsert_personnel(data: Dict[str, Optional[str]]) -> bool:
    """插入或更新人员信息（单条，自带事务）

    向后兼容接口，内部使用 _upsert_single + db_transaction。
    """
    payload = _sanitize_person_payload(data)
    uid = _require_user_id()
    with db_transaction() as conn:
        cur = conn.cursor()
        return _upsert_single(payload, uid, cur)


def bulk_import_personnel(records: List[Dict[str, Optional[str]]]) -> Dict:
    """批量导入人员信息（整批原子提交）

    P1.3：使用单一 db_transaction 包裹所有记录，要么全成功要么全回滚。
    返回结构化结果，包含成功数、跳过数和失败明细。

    Args:
        records: 人员数据字典列表

    Returns:
        dict: {
            'imported': 成功导入/更新数量,
            'skipped': 跳过数量（缺少必填字段等）,
            'errors': 失败明细列表 [{'emp_no': str, 'error': str}, ...]
        }

    Raises:
        Exception: 整批回滚后重新抛出（由 db_transaction 管理）
    """
    uid = _require_user_id()
    imported = 0
    skipped = 0
    errors = []

    with db_transaction() as conn:
        cur = conn.cursor()
        for idx, record in enumerate(records):
            try:
                payload = _sanitize_person_payload(record)
                if _upsert_single(payload, uid, cur):
                    imported += 1
                else:
                    skipped += 1
            except Exception as e:
                errors.append({
                    'index': idx,
                    'emp_no': record.get('emp_no', '?'),
                    'error': str(e)
                })
                # 遇到异常直接 raise，让 db_transaction 统一回滚
                raise

    return {'imported': imported, 'skipped': skipped, 'errors': errors}


def update_personnel_field(emp_no: str, field: str, value: Optional[str]) -> bool:
    """更新人员的单个字段"""
    c = _get_constants()
    PERSONNEL_DB_COLUMNS = c['PERSONNEL_DB_COLUMNS']
    if field not in {"name", *PERSONNEL_DB_COLUMNS}:
        return False

    # 🔒 权限检查: 非管理员需要验证是否有权修改该员工
    user_role = _get_user_role()
    if user_role != 'admin':
        if not AccessControlService.validate_employee_access(emp_no):
            return False

    payload = _sanitize_person_payload({field: value})

    with db_transaction() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            UPDATE employees
            SET {field} = %s
            WHERE emp_no=%s
            """,
            (payload.get(field), emp_no),
        )
        affected = cur.rowcount > 0
    return affected


def delete_employee(emp_no):
    """删除员工"""
    uid = _require_user_id()

    # 🔒 权限检查: 非管理员需要验证是否有权删除该员工
    user_role = _get_user_role()
    if user_role != 'admin':
        if not AccessControlService.validate_employee_access(emp_no):
            return False

    with db_transaction() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM employees WHERE emp_no=%s", (emp_no,))
    return True
