#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公共装饰器模块
提供认证、授权等通用装饰器

整改说明：
  - 统一 session 校验：使用 helpers.is_dingtalk_session_valid()
  - 权限判断委托给 AccessControlService（P1 统一出口）
  - g.user_ctx 由 app.py 的 before_request 钩子统一加载
"""
from functools import wraps
from flask import session, redirect, url_for, flash, request, g
from .helpers import is_dingtalk_session_valid as _is_dingtalk_session_valid


def _get_user_role():
    """从 AccessControlService 获取当前用户角色（P1 统一出口）"""
    from services.access_control_service import AccessControlService
    return AccessControlService.get_current_role()


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
    使用 AccessControlService.has_permission()（P1 统一出口）

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

            from services.access_control_service import AccessControlService
            if not AccessControlService.has_permission(required_role):
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
    使用 AccessControlService.is_top_level_manager()（P1 统一出口）

    允许以下用户访问：
    1. 系统管理员（admin）
    2. 顶级部门管理员（manager角色且所属部门level=1）
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        redirect_resp = _check_login_and_session()
        if redirect_resp:
            return redirect_resp

        from services.access_control_service import AccessControlService
        if not AccessControlService.is_top_level_manager():
            flash('需要系统管理员或顶级部门管理员权限', 'danger')
            return redirect(url_for('personnel.dashboard'))

        return f(*args, **kwargs)

    return decorated_function
