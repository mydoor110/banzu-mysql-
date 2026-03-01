#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一权限控制服务 (P1)

所有权限判断的唯一数据源和逻辑实现。
路由层装饰器、helpers、service 层均应通过本模块判断权限，
不再各自重复读取角色或拼装部门过滤条件。

数据来源：g.user_ctx （由 app.py before_request 统一加载）
"""
from typing import Dict, List, Optional, Tuple

from flask import g, session

from models.database import get_db


class AccessControlService:
    """统一权限控制出口

    设计原则：
    - 所有方法为 @staticmethod，无状态
    - 角色层级定义唯一（ROLE_HIERARCHY）
    - g.user_ctx 为唯一数据源，fallback 仅覆盖极端场景
    """

    # ── 角色层级定义（唯一定义点） ──
    ROLE_HIERARCHY: Dict[str, int] = {
        'admin': 3,
        'manager': 2,
        'user': 1,
    }

    # ──────────── 用户上下文 ────────────

    @staticmethod
    def get_current_user_context() -> Optional[Dict]:
        """获取当前请求的用户上下文（从 g.user_ctx 读取）

        Returns:
            dict: 包含 id, username, role, department_id, dept_level,
                  dept_name, dept_path 等字段。
            None: 未登录或上下文不可用。
        """
        return getattr(g, 'user_ctx', None)

    # ──────────── 角色判断 ────────────

    @staticmethod
    def get_current_role() -> Optional[str]:
        """获取当前用户角色（零查询）

        优先从 g.user_ctx 读取。仅在 g.user_ctx 不可用的极端情况下
        回退查库（兼容未注册 user_ctx 的测试场景）。

        Returns:
            str: 'admin' | 'manager' | 'user'
            None: 未登录
        """
        ctx = getattr(g, 'user_ctx', None)
        if ctx:
            return ctx.get('role')

        # fallback：直接查库（极罕见，兼容测试场景）
        user_id = session.get('user_id')
        if not user_id:
            return None
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        return row['role'] if row else None

    @staticmethod
    def is_admin() -> bool:
        """当前用户是否为系统管理员"""
        return AccessControlService.get_current_role() == 'admin'

    @staticmethod
    def has_permission(required_role: str) -> bool:
        """检查当前用户是否具有指定角色权限（含层级继承）

        Args:
            required_role: 需要的最低角色 ('admin', 'manager', 'user')

        Returns:
            bool: True 表示有权限
        """
        current_role = AccessControlService.get_current_role()
        if not current_role:
            return False

        hierarchy = AccessControlService.ROLE_HIERARCHY
        return hierarchy.get(current_role, 0) >= hierarchy.get(required_role, 0)

    @staticmethod
    def is_top_level_manager() -> bool:
        """当前用户是否为系统管理员或顶级部门管理员（level=1）

        Returns:
            bool: admin 直接通过；manager 需 dept_level == 1
        """
        ctx = getattr(g, 'user_ctx', None)
        if not ctx:
            return False
        role = ctx.get('role')
        if role == 'admin':
            return True
        if role == 'manager':
            dept_level = ctx.get('dept_level')
            return dept_level == 1
        return False

    # ──────────── 部门权限 ────────────

    @staticmethod
    def get_user_department_info() -> Optional[Dict]:
        """获取当前用户的部门信息

        优先从 g.user_ctx 读取，避免额外查询。

        Returns:
            dict: 包含 department_id, role, dept_name, level, path
            None: 未登录或无部门
        """
        ctx = getattr(g, 'user_ctx', None)
        if ctx:
            return {
                'department_id': ctx.get('department_id'),
                'role': ctx.get('role'),
                'dept_name': ctx.get('dept_name'),
                'level': ctx.get('dept_level'),
                'path': ctx.get('dept_path'),
            }

        # fallback：查库
        user_id = session.get('user_id')
        if not user_id:
            return None

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT u.department_id, u.role, d.name as dept_name, d.level, d.path
            FROM users u
            LEFT JOIN departments d ON u.department_id = d.id
            WHERE u.id = %s
        """, (user_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_accessible_departments(user_dept_info: Optional[Dict] = None) -> List[Dict]:
        """获取当前用户可以访问的所有部门

        Args:
            user_dept_info: 用户部门信息，默认自动获取

        Returns:
            list: 可访问的部门列表 [{id, name, level, path}, ...]
        """
        if user_dept_info is None:
            user_dept_info = AccessControlService.get_user_department_info()

        if not user_dept_info:
            return []

        conn = get_db()
        cur = conn.cursor()

        # 管理员可以看到所有部门（即使没有 department_id）
        if user_dept_info['role'] == 'admin':
            cur.execute("SELECT id, name, level, path FROM departments ORDER BY level, name")
        else:
            # 普通用户必须有 department_id
            if not user_dept_info['department_id']:
                return []

            # 普通用户可以看到自己的部门及所有子部门
            user_path = user_dept_info['path'] or f"/{user_dept_info['department_id']}"
            cur.execute(
                "SELECT id, name, level, path FROM departments WHERE path LIKE %s OR id = %s ORDER BY level, name",
                (f"{user_path}/%", user_dept_info['department_id'])
            )

        rows = cur.fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def get_accessible_department_ids(user_dept_info: Optional[Dict] = None) -> List[int]:
        """获取当前用户可以访问的所有部门 ID 列表

        Args:
            user_dept_info: 用户部门信息，默认自动获取

        Returns:
            list: 部门 ID 列表
        """
        depts = AccessControlService.get_accessible_departments(user_dept_info)
        return [dept['id'] for dept in depts] if depts else []

    # ──────────── 员工访问校验 ────────────

    @staticmethod
    def validate_employee_access(emp_no: str) -> bool:
        """检查当前用户是否可以访问指定员工

        Args:
            emp_no: 员工工号

        Returns:
            bool: True 表示可以访问
        """
        if not emp_no:
            return False

        # 管理员可以访问所有员工
        if AccessControlService.is_admin():
            return True

        # 获取员工所属部门
        emp_dept_id = AccessControlService._get_employee_department_id(emp_no)
        if emp_dept_id is None:
            return False

        # 获取当前用户可访问的部门列表
        accessible_dept_ids = AccessControlService.get_accessible_department_ids()
        return emp_dept_id in accessible_dept_ids

    @staticmethod
    def _get_employee_department_id(emp_no: str) -> Optional[int]:
        """获取指定员工的部门 ID（内部方法）"""
        if not emp_no:
            return None

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT department_id FROM employees WHERE emp_no = %s", (emp_no,))
        row = cur.fetchone()
        return row['department_id'] if row else None

    # ──────────── SQL 过滤条件构建 ────────────

    @staticmethod
    def build_department_filter(table_alias: Optional[str] = None) -> Tuple[str, str, List]:
        """构建基于部门的 SQL 过滤条件

        Args:
            table_alias: 表别名（如 'e', 'pr', 'tr'），用于构建 JOIN 子句

        Returns:
            tuple: (WHERE 条件, JOIN 子句, 参数列表)

        Examples:
            # employees 表（已有 department_id）
            where, join, params = build_department_filter()
            # → ("department_id IN (%s,%s)", "", [1, 2])

            # performance_records 表（通过 emp_no 关联）
            where, join, params = build_department_filter('pr')
            # → ("e.department_id IN (%s,%s)", "LEFT JOIN employees e ON pr.emp_no = e.emp_no", [1, 2])
        """
        user_dept_info = AccessControlService.get_user_department_info()

        # 管理员无需过滤
        if user_dept_info and user_dept_info['role'] == 'admin':
            return "1=1", "", []

        # 获取可访问部门
        dept_ids = AccessControlService.get_accessible_department_ids(user_dept_info)

        if not dept_ids:
            # 无可访问部门，返回空结果条件
            return "1=0", "", []

        placeholders = ','.join(['%s'] * len(dept_ids))

        # 根据是否有表别名决定 JOIN 和 WHERE
        if table_alias:
            join_clause = f"LEFT JOIN employees e ON {table_alias}.emp_no = e.emp_no"
            where_clause = f"e.department_id IN ({placeholders})"
        else:
            join_clause = ""
            where_clause = f"department_id IN ({placeholders})"

        return where_clause, join_clause, dept_ids
