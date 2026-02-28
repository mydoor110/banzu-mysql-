#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公共装饰器模块
提供认证、授权等通用装饰器

整改说明：
  - 统一 session 校验：使用 helpers.is_dingtalk_session_valid()
  - 权限从 g.user_ctx 读取，避免每个装饰器重复查 DB
  - g.user_ctx 由 app.py 的 before_request 钩子统一加载
"""
from functools import wraps
from flask import session, redirect, url_for, flash, request, g
from .helpers import is_dingtalk_session_valid as _is_dingtalk_session_valid


def _get_user_role():
    """从 g.user_ctx 获取当前用户角色（零查询）
    
    如果 g.user_ctx 不可用（极罕见情况），回退查库。
    """
    ctx = getattr(g, 'user_ctx', None)
    if ctx:
        return ctx.get('role')
    # 回退：直接查库（兼容未注册 user_ctx 的情况）
    from models.database import get_db
    user_id = session.get('user_id')
    if not user_id:
        return None
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT role FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    return row['role'] if row else None


def _check_login_and_session():
    """统一的登录 + session 有效性检查
    
    Returns:
        None: 检查通过
        Response: 需要重定向的响应对象
    """
    if not session.get('logged_in'):
        flash('请先登录', 'warning')
        return redirect(url_for('auth.login', next=request.path))
    if not _is_dingtalk_session_valid():
        session.clear()
        flash('登录已过期，请重新登录', 'warning')
        return redirect(url_for('auth.login', next=request.path))
    return None


def login_required(f):
    """
    登录验证装饰器

    用于需要用户登录才能访问的路由
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        redirect_resp = _check_login_and_session()
        if redirect_resp:
            return redirect_resp
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    管理员权限验证装饰器

    用于需要管理员权限才能访问的路由
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        redirect_resp = _check_login_and_session()
        if redirect_resp:
            return redirect_resp

        # 从 g.user_ctx 读取角色（无额外 DB 查询）
        role = _get_user_role()
        if role != 'admin':
            flash('需要管理员权限才能访问此功能', 'danger')
            return redirect(url_for('personnel.dashboard'))

        return f(*args, **kwargs)
    return decorated_function


def manager_required(f):
    """
    部门管理员权限验证装饰器

    要求用户角色为 manager 或 admin
    用于需要管理权限的操作（导入、修改、删除等）
    普通用户（user）只有查看权限
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        redirect_resp = _check_login_and_session()
        if redirect_resp:
            return redirect_resp

        # 从 g.user_ctx 读取角色（无额外 DB 查询）
        role = _get_user_role()
        if role not in ('admin', 'manager'):
            flash('需要部门管理员或管理员权限才能执行此操作', 'danger')
            return redirect(url_for('personnel.dashboard'))

        return f(*args, **kwargs)
    return decorated_function


def role_required(required_role):
    """
    角色权限验证装饰器工厂

    Args:
        required_role: 需要的角色 ('admin', 'manager', 'user')

    Returns:
        装饰器函数
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            redirect_resp = _check_login_and_session()
            if redirect_resp:
                return redirect_resp

            # 从 g.user_ctx 读取角色（无额外 DB 查询）
            role_hierarchy = {'admin': 3, 'manager': 2, 'user': 1}
            required_level = role_hierarchy.get(required_role, 0)

            role = _get_user_role()
            if not role:
                flash('用户信息异常', 'danger')
                return redirect(url_for('auth.login'))

            user_level = role_hierarchy.get(role, 0)
            if user_level < required_level:
                role_names = {
                    'admin': '管理员',
                    'manager': '管理员或部门经理',
                    'user': '登录用户'
                }
                flash(f'需要{role_names.get(required_role, required_role)}权限', 'danger')
                return redirect(url_for('personnel.dashboard'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def top_level_manager_required(f):
    """
    顶级部门管理员权限验证装饰器
    
    允许以下用户访问：
    1. 系统管理员（admin）
    2. 顶级部门管理员（manager角色且所属部门level=1）
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        redirect_resp = _check_login_and_session()
        if redirect_resp:
            return redirect_resp

        # 从 g.user_ctx 读取（已包含 dept_level）
        ctx = getattr(g, 'user_ctx', None)
        if not ctx:
            flash('用户信息异常', 'danger')
            return redirect(url_for('auth.login'))

        user_role = ctx.get('role')
        dept_level = ctx.get('dept_level')

        # 系统管理员直接通过
        if user_role == 'admin':
            return f(*args, **kwargs)
        
        # 部门管理员需要检查是否为顶级部门
        if user_role == 'manager' and dept_level == 1:
            return f(*args, **kwargs)
        
        # 其他情况拒绝访问
        flash('需要系统管理员或顶级部门管理员权限', 'danger')
        return redirect(url_for('personnel.dashboard'))
    
    return decorated_function
