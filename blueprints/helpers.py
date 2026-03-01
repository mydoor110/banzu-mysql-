#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公共工具函数模块
提供各 Blueprint 共用的辅助函数
"""
from flask import session, request
from models.database import get_db
from datetime import datetime, timedelta
import calendar


def is_dingtalk_session_valid():
    """统一的钉钉 session 有效性校验函数
    
    判断逻辑:
    - 非钉钉登录源: 始终有效
    - 钉钉登录源: 判断是否在 24 小时内
    
    Returns:
        bool: session 是否有效
    """
    if session.get('login_source') != 'dingtalk':
        return True

    login_at = session.get('login_at')
    if not login_at:
        return False

    try:
        login_time = datetime.fromisoformat(login_at)
    except (TypeError, ValueError):
        return False

    return datetime.now() - login_time <= timedelta(hours=24)


def current_user_id():
    """
    获取当前登录用户的ID

    Returns:
        int: 用户ID,未登录返回None
    """
    return session.get('user_id')


def current_username():
    """
    获取当前登录用户的用户名

    Returns:
        str: 用户名,未登录返回None
    """
    return session.get('username')


def current_user_role():
    """
    获取当前登录用户的角色
    委托给 AccessControlService（P1 统一出口）

    Returns:
        str: 用户角色 ('admin', 'manager', 'user'),未登录返回None
    """
    from services.access_control_service import AccessControlService
    return AccessControlService.get_current_role()


def is_logged_in():
    """
    检查用户是否已登录

    Returns:
        bool: True表示已登录,False表示未登录
    """
    return session.get('logged_in', False)


def is_admin():
    """
    检查当前用户是否为管理员
    委托给 AccessControlService（P1 统一出口）

    Returns:
        bool: True表示是管理员,False表示不是
    """
    if not is_logged_in():
        return False
    from services.access_control_service import AccessControlService
    return AccessControlService.is_admin()


def get_user_role():
    """
    获取当前用户的数据库角色
    委托给 AccessControlService（P1 统一出口）

    Returns:
        str: 用户角色,未登录或查询失败返回None
    """
    from services.access_control_service import AccessControlService
    return AccessControlService.get_current_role()


def has_permission(required_role):
    """
    检查用户是否具有指定权限
    委托给 AccessControlService（P1 统一出口）

    Args:
        required_role: 需要的角色 ('admin', 'manager', 'user')

    Returns:
        bool: True表示有权限,False表示无权限
    """
    from services.access_control_service import AccessControlService
    return AccessControlService.has_permission(required_role)


def get_user_info(user_id=None):
    """
    获取用户完整信息

    Args:
        user_id: 用户ID,默认为当前登录用户

    Returns:
        dict: 用户信息字典,失败返回None
    """
    if user_id is None:
        user_id = current_user_id()

    if not user_id:
        return None

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.id, u.username, u.role, u.created_at,
               d.name as department_name, d.id as department_id
        FROM users u
        LEFT JOIN departments d ON u.department_id = d.id
        WHERE u.id = %s
    """, (user_id,))
    row = cur.fetchone()

    if row:
        return dict(row)
    return None


def format_date(date_str, format_type='display'):
    """
    格式化日期字符串

    Args:
        date_str: 日期字符串
        format_type: 格式类型 ('display', 'database', 'short')

    Returns:
        str: 格式化后的日期字符串
    """
    from datetime import datetime

    if not date_str:
        return ''

    try:
        if isinstance(date_str, str):
            # 尝试多种日期格式解析
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d']:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                return date_str
        else:
            dt = date_str

        # 根据类型返回不同格式
        if format_type == 'display':
            return dt.strftime('%Y年%m月%d日 %H:%M')
        elif format_type == 'database':
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        elif format_type == 'short':
            return dt.strftime('%Y-%m-%d')
        else:
            return date_str

    except Exception:
        return date_str


def safe_int(value, default=0):
    """
    安全转换为整数

    Args:
        value: 要转换的值
        default: 转换失败时的默认值

    Returns:
        int: 转换后的整数
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value, default=0.0):
    """
    安全转换为浮点数

    Args:
        value: 要转换的值
        default: 转换失败时的默认值

    Returns:
        float: 转换后的浮点数
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def paginate(query_result, page=1, per_page=20):
    """
    简单的分页功能

    Args:
        query_result: 查询结果列表
        page: 当前页码
        per_page: 每页显示数量

    Returns:
        dict: 包含分页信息的字典
    """
    total = len(query_result)
    start = (page - 1) * per_page
    end = start + per_page

    return {
        'items': query_result[start:end],
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page,
        'has_prev': page > 1,
        'has_next': end < total
    }


def require_user_id():
    """
    获取当前用户ID，未登录则抛出异常

    Returns:
        int: 用户ID

    Raises:
        RuntimeError: 用户未登录时抛出
    """
    uid = current_user_id()
    if not uid:
        raise RuntimeError("No current user id in session")
    return uid


def get_user_department():
    """
    获取当前用户的部门信息
    委托给 AccessControlService（P1 统一出口）

    Returns:
        dict: 包含部门信息的字典，未登录或无部门返回None
    """
    from services.access_control_service import AccessControlService
    return AccessControlService.get_user_department_info()


def get_accessible_departments(user_dept_info=None):
    """
    获取当前用户可以访问的所有部门
    委托给 AccessControlService（P1 统一出口）

    Args:
        user_dept_info: 用户部门信息，默认自动获取

    Returns:
        list: 可访问的部门列表
    """
    from services.access_control_service import AccessControlService
    return AccessControlService.get_accessible_departments(user_dept_info)


def get_accessible_user_ids():
    """
    [已废弃] 获取当前用户可以访问的所有用户ID

    注意：权限系统已改为基于department_id，不再使用user_id过滤数据
    请使用 get_accessible_department_ids() 替代

    Returns:
        list: 可访问的用户ID列表（为兼容性保留）
    """
    import warnings
    warnings.warn(
        "get_accessible_user_ids()已废弃，请使用get_accessible_department_ids()进行权限过滤",
        DeprecationWarning,
        stacklevel=2
    )

    user_dept_info = get_user_department()
    accessible_depts = get_accessible_departments(user_dept_info)

    if not accessible_depts:
        return [current_user_id()]  # 回退到仅当前用户

    dept_ids = [dept['id'] for dept in accessible_depts] + [user_dept_info['department_id']]

    conn = get_db()
    cur = conn.cursor()
    placeholders = ','.join(['%s'] * len(dept_ids))
    cur.execute(
        f"SELECT id FROM users WHERE department_id IN ({placeholders}) OR id = %s",
        dept_ids + [current_user_id()]
    )
    user_ids = [row['id'] for row in cur.fetchall()]

    return user_ids if user_ids else [current_user_id()]


def get_accessible_department_ids(user_dept_info=None):
    """
    获取当前用户可以访问的所有部门ID列表
    委托给 AccessControlService（P1 统一出口）

    Args:
        user_dept_info: 用户部门信息，默认自动获取

    Returns:
        list: 可访问的部门ID列表
    """
    from services.access_control_service import AccessControlService
    return AccessControlService.get_accessible_department_ids(user_dept_info)


def validate_employee_access(emp_no):
    """
    检查当前用户是否可以访问指定员工
    委托给 AccessControlService（P1 统一出口）

    Args:
        emp_no: 员工工号

    Returns:
        bool: True表示可以访问，False表示无权访问
    """
    from services.access_control_service import AccessControlService
    return AccessControlService.validate_employee_access(emp_no)


def get_employee_department_id(emp_no):
    """
    获取指定员工的部门ID
    委托给 AccessControlService（P1 统一出口）

    Args:
        emp_no: 员工工号

    Returns:
        int: 部门ID，员工不存在返回None
    """
    from services.access_control_service import AccessControlService
    return AccessControlService._get_employee_department_id(emp_no)


def calculate_years_from_date(date_val):
    """
    计算从指定日期到当前的年限（保留1位小数）

    P1.2：实现已下沉到 services/domain/personnel_algo.py。
    此处保留 thin wrapper 保持向后兼容。

    Args:
        date_val: 日期（支持字符串格式YYYY-MM-DD、datetime对象、date对象）

    Returns:
        float: 年限（保留1位小数），日期无效返回None
    """
    from services.domain.personnel_algo import calculate_years_from_date as _impl
    return _impl(date_val)


def log_import_operation(module, operation, file_name=None, total_rows=0,
                         success_rows=0, failed_rows=0, skipped_rows=0,
                         error_message=None, import_details=None):
    """
    记录数据导入操作日志

    Args:
        module: 模块名称 (personnel/performance/training/safety)
        operation: 操作类型 (import/batch_import)
        file_name: 导入文件名
        total_rows: 总行数
        success_rows: 成功导入行数
        failed_rows: 失败行数
        skipped_rows: 跳过行数（权限不足等）
        error_message: 错误信息
        import_details: 导入详情（可以是字典，会自动转JSON）

    Returns:
        int: 日志记录ID，失败返回None
    """
    from flask import session, request
    import json

    try:
        user_id = session.get('user_id')
        if not user_id:
            return None

        conn = get_db()
        cur = conn.cursor()

        # 获取用户信息
        cur.execute("""
            SELECT u.username, u.role, u.department_id, d.name as department_name
            FROM users u
            LEFT JOIN departments d ON u.department_id = d.id
            WHERE u.id = %s
        """, (user_id,))
        user_info = cur.fetchone()

        if not user_info:
            return None

        # 获取IP地址
        ip_address = request.remote_addr if request else None

        # 转换导入详情为JSON
        details_json = None
        if import_details:
            if isinstance(import_details, dict):
                details_json = json.dumps(import_details, ensure_ascii=False)
            else:
                details_json = str(import_details)

        # 插入日志记录
        cur.execute("""
            INSERT INTO import_logs (
                module, operation, user_id, username, user_role,
                department_id, department_name, file_name,
                total_rows, success_rows, failed_rows, skipped_rows,
                error_message, import_details, ip_address
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            module, operation, user_id, user_info['username'], user_info['role'],
            user_info['department_id'], user_info['department_name'], file_name,
            total_rows, success_rows, failed_rows, skipped_rows,
            error_message, details_json, ip_address
        ))

        conn.commit()
        return cur.lastrowid

    except Exception as e:
        print(f"记录导入日志失败: {e}")
        return None


def build_department_filter(table_alias=None):
    """
    构建基于部门的SQL过滤条件
    委托给 AccessControlService（P1 统一出口）

    Args:
        table_alias: 表别名（如 'e', 'p', 'tr'），用于构建 JOIN 子句

    Returns:
        tuple: (WHERE条件, JOIN子句, 参数列表)

    示例:
        # 对于employees表（已有department_id）
        where_clause, join_clause, params = build_department_filter()

        # 对于performance_records表（通过emp_no关联employees）
        where_clause, join_clause, params = build_department_filter('pr')
    """
    from services.access_control_service import AccessControlService
    return AccessControlService.build_department_filter(table_alias)


# ==================== 日期筛选工具函数 ====================

import re

# 格式校验正则
_RE_DAY = re.compile(r'^\d{4}-\d{2}-\d{2}$')     # YYYY-MM-DD
_RE_MONTH = re.compile(r'^\d{4}-\d{2}$')          # YYYY-MM
_RE_YEAR = re.compile(r'^\d{4}$')                  # YYYY


class TimeRangeError(ValueError):
    """时间区间参数不合法时抛出，Blueprint 层应 catch 并返回 400。"""
    pass


def month_range_to_dates(start_month, end_month):
    """
    月区间转标准日期区间

    Args:
        start_month: 开始月份 (YYYY-MM)
        end_month: 结束月份 (YYYY-MM)

    Returns:
        tuple: (start_date, end_date) - YYYY-MM-DD 格式

    示例:
        month_range_to_dates('2026-01', '2026-03')  # ('2026-01-01', '2026-03-31')
    """
    start_date = None
    end_date = None

    if start_month:
        start_date = f"{start_month}-01"

    if end_month:
        try:
            y, m = map(int, end_month.split('-'))
            last_day = calendar.monthrange(y, m)[1]
            end_date = f"{y:04d}-{m:02d}-{last_day:02d}"
        except (ValueError, TypeError):
            end_date = f"{end_month}-01"

    return (start_date, end_date)


def year_range_to_dates(start_year, end_year):
    """
    年区间转标准日期区间

    Args:
        start_year: 开始年份 (YYYY)
        end_year: 结束年份 (YYYY)

    Returns:
        tuple: (start_date, end_date) - YYYY-MM-DD 格式

    示例:
        year_range_to_dates('2024', '2026')  # ('2024-01-01', '2026-12-31')
    """
    start_date = f"{start_year}-01-01" if start_year else None
    end_date = f"{end_year}-12-31" if end_year else None
    return (start_date, end_date)


def parse_time_range(args, allowed_grains=None, default_grain=None, default_range='current_month'):
    """
    统一时间区间解析入口 — 仓库唯一合法的时间区间解析函数

    根据请求参数自动识别时间粒度，并返回标准化的日期区间。

    校验规则（依次执行）：
    1. allowed_grains 拦截：传了时间参数但粒度不被允许 → 抛 TimeRangeError
    2. 格式校验：day=YYYY-MM-DD, month=YYYY-MM, year=YYYY → 抛 TimeRangeError
    3. 起止顺序校验：start > end → 抛 TimeRangeError

    Args:
        args: 请求参数字典（通常为 request.args 或 dict）
        allowed_grains: 允许的粒度列表，如 ['day'], ['month'], ['day', 'month']
                        为 None 时允许所有粒度
        default_grain: 当无法从参数推断粒度时使用的默认粒度
        default_range: 无参数时的默认范围
            - 'current_month': 当月
            - 'last_month': 上月
            - 'last_3_months': 最近3个月
            - 'last_6_months': 最近6个月
            - 'last_12_months': 最近12个月
            - None: 不设默认值

    Returns:
        dict: 标准化的时间区间对象
            {
                'grain': 'day' | 'month' | 'year',
                'raw_start': 原始起始值,
                'raw_end': 原始结束值,
                'start_date': 'YYYY-MM-DD' 格式的起始日期,
                'end_date': 'YYYY-MM-DD' 格式的结束日期,
                'start_month': 'YYYY-MM' 或 None,
                'end_month': 'YYYY-MM' 或 None,
                'start_year': 'YYYY' 或 None,
                'end_year': 'YYYY' 或 None,
            }

    Raises:
        TimeRangeError: 粒度不允许 / 格式错误 / 起止倒序
    """

    # 读取各粒度参数
    start_month = (args.get('start_month') or '').strip()
    end_month = (args.get('end_month') or '').strip()
    start_year = (args.get('start_year') or '').strip()
    end_year = (args.get('end_year') or '').strip()
    start_date = (args.get('start_date') or '').strip()
    end_date = (args.get('end_date') or '').strip()

    grain = None
    raw_start = None
    raw_end = None

    # ── 1. 按粒度参数名识别 ──
    if start_month or end_month:
        grain = 'month'
        raw_start = start_month or None
        raw_end = end_month or None
    elif start_year or end_year:
        grain = 'year'
        raw_start = start_year or None
        raw_end = end_year or None
    elif start_date or end_date:
        grain = 'day'
        raw_start = start_date or None
        raw_end = end_date or None

    # ── 2. 无参数 → 走默认范围 ──
    if grain is None:
        grain = default_grain or (allowed_grains[0] if allowed_grains else 'month')

        if default_range is None:
            return {
                'grain': grain,
                'raw_start': None, 'raw_end': None,
                'start_date': None, 'end_date': None,
                'start_month': None, 'end_month': None,
                'start_year': None, 'end_year': None,
            }

        now = datetime.now()

        if grain == 'day':
            if default_range == 'current_month':
                first_day = datetime(now.year, now.month, 1)
                last_day_num = calendar.monthrange(now.year, now.month)[1]
                start_date = first_day.strftime('%Y-%m-%d')
                end_date = datetime(now.year, now.month, last_day_num).strftime('%Y-%m-%d')
            elif default_range == 'last_month':
                first_this = datetime(now.year, now.month, 1)
                last_prev = first_this - timedelta(days=1)
                start_date = datetime(last_prev.year, last_prev.month, 1).strftime('%Y-%m-%d')
                end_date = last_prev.strftime('%Y-%m-%d')
            elif default_range == 'last_3_months':
                end_date = now.strftime('%Y-%m-%d')
                start_date = (now - timedelta(days=90)).strftime('%Y-%m-%d')
            else:
                start_date = None
                end_date = None
            raw_start = start_date
            raw_end = end_date

        elif grain == 'month':
            if default_range == 'current_month':
                start_month = now.strftime('%Y-%m')
                end_month = now.strftime('%Y-%m')
            elif default_range == 'last_month':
                first_this = datetime(now.year, now.month, 1)
                last_prev = first_this - timedelta(days=1)
                start_month = last_prev.strftime('%Y-%m')
                end_month = last_prev.strftime('%Y-%m')
            elif default_range == 'last_3_months':
                end_month = now.strftime('%Y-%m')
                s = datetime(now.year, now.month - 2, 1) if now.month > 2 else datetime(now.year - 1, now.month + 10, 1)
                start_month = s.strftime('%Y-%m')
            elif default_range == 'last_6_months':
                end_month = now.strftime('%Y-%m')
                s = datetime(now.year, now.month, 1) - timedelta(days=1)
                for _ in range(4):
                    s = datetime(s.year, s.month, 1) - timedelta(days=1)
                start_month = datetime(s.year, s.month, 1).strftime('%Y-%m')
            elif default_range == 'last_12_months':
                end_month = now.strftime('%Y-%m')
                s = datetime(now.year - 1, now.month, 1)
                start_month = s.strftime('%Y-%m')
            else:
                start_month = None
                end_month = None
            raw_start = start_month
            raw_end = end_month

        elif grain == 'year':
            yr = str(now.year)
            start_year = yr
            end_year = yr
            raw_start = yr
            raw_end = yr

        # 默认值路径跳过校验（程序生成的值一定合法），直接归一化返回
        return _build_time_range_result(grain, raw_start, raw_end,
                                        start_date, end_date,
                                        start_month, end_month,
                                        start_year, end_year)

    # ── 3. allowed_grains 拦截 ──
    if allowed_grains and grain not in allowed_grains:
        raise TimeRangeError(
            f"此接口只允许 {allowed_grains} 粒度的时间参数，"
            f"但收到了 '{grain}' 粒度的参数"
        )

    # ── 4. 格式校验 ──
    _validate_format(grain, raw_start, raw_end)

    # ── 5. 起止顺序校验 ──
    if raw_start and raw_end and raw_start > raw_end:
        raise TimeRangeError(
            f"起始时间 '{raw_start}' 晚于结束时间 '{raw_end}'"
        )

    # ── 6. 归一化 ──
    return _build_time_range_result(grain, raw_start, raw_end,
                                    start_date, end_date,
                                    start_month, end_month,
                                    start_year, end_year)


def _validate_format(grain, raw_start, raw_end):
    """校验时间参数格式是否合法，不合法则抛 TimeRangeError。"""
    fmt_map = {
        'day':   (_RE_DAY,   'YYYY-MM-DD'),
        'month': (_RE_MONTH, 'YYYY-MM'),
        'year':  (_RE_YEAR,  'YYYY'),
    }
    regex, expected_fmt = fmt_map[grain]

    for label, val in [('起始时间', raw_start), ('结束时间', raw_end)]:
        if val is None:
            continue
        if not regex.match(val):
            raise TimeRangeError(
                f"{label} '{val}' 格式错误，要求 {expected_fmt}"
            )
        # 对 day 和 month 进一步验证值合法性（如 2026-02-30 不合法）
        if grain == 'day':
            try:
                datetime.strptime(val, '%Y-%m-%d')
            except ValueError:
                raise TimeRangeError(f"{label} '{val}' 不是合法的日期")
        elif grain == 'month':
            try:
                y, m = map(int, val.split('-'))
                if m < 1 or m > 12:
                    raise ValueError
            except ValueError:
                raise TimeRangeError(f"{label} '{val}' 不是合法的月份")


def _build_time_range_result(grain, raw_start, raw_end,
                              start_date, end_date,
                              start_month, end_month,
                              start_year, end_year):
    """构建标准化的时间区间返回对象。"""
    result = {
        'grain': grain,
        'raw_start': raw_start,
        'raw_end': raw_end,
        'start_date': None,
        'end_date': None,
        'start_month': None,
        'end_month': None,
        'start_year': None,
        'end_year': None,
    }

    if grain == 'day':
        result['start_date'] = start_date or None
        result['end_date'] = end_date or None

    elif grain == 'month':
        result['start_month'] = start_month or None
        result['end_month'] = end_month or None
        sd, ed = month_range_to_dates(start_month, end_month)
        result['start_date'] = sd
        result['end_date'] = ed

    elif grain == 'year':
        result['start_year'] = start_year or None
        result['end_year'] = end_year or None
        sd, ed = year_range_to_dates(start_year, end_year)
        result['start_date'] = sd
        result['end_date'] = ed

    return result


def build_date_filter_sql(date_column, start_date=None, end_date=None):
    """
    构建日期筛选的SQL条件和参数

    注意：此函数仅接受标准 YYYY-MM-DD 格式的日期。
    请先通过 parse_time_range() 标准化后再调用。

    Args:
        date_column: 日期字段名（如'training_date', 'tr.training_date'）
        start_date: 开始日期（YYYY-MM-DD格式）
        end_date: 结束日期（YYYY-MM-DD格式）

    Returns:
        tuple: (conditions, params)
            - conditions: SQL条件列表（可直接用AND连接）
            - params: 参数列表（用于参数化查询）
    """
    conditions = []
    params = []

    if start_date:
        conditions.append(f"{date_column} >= %s")
        params.append(start_date)

    if end_date:
        conditions.append(f"{date_column} <= %s")
        params.append(end_date)

    return (conditions, params)
