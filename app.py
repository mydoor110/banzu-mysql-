#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
班组管理系统 - Blueprint 架构版本
主应用程序入口

整改说明：
  - 引入 create_app() 工厂函数，统一 python app.py 与 flask run 行为
  - 安全头改为配置驱动，消除 config/settings.py 与 app.py 的重复定义
  - 修复 conn.close() 为 close_db()，避免 thread-local 泄漏
  - 删除 before_request 中冗余的算法配置初始化
  - 蓝图注册统一使用 register_blueprints()
"""
import os
from dotenv import load_dotenv
load_dotenv()

import json

import click
from flask import Flask, redirect, url_for, session, request, flash, jsonify, g
from werkzeug.security import generate_password_hash
from werkzeug.exceptions import RequestEntityTooLarge

try:
    from flask_wtf.csrf import CSRFProtect, generate_csrf
    CSRF_AVAILABLE = True
except ImportError:
    CSRF_AVAILABLE = False
    CSRFProtect = None
    def generate_csrf():
        return ""

# 导入配置
from config.settings import (
    APP_TITLE,
    UPLOAD_DIR, EXPORT_DIR,
    SecurityConfig,
    get_config
)

# 导入数据库工具
from models.database import get_db, close_db, init_database, bootstrap_data

# 导入日志配置
from utils.logger import setup_logging, log_request


# ==================== 应用工厂 ====================

def create_app(config_name=None):
    """Flask 应用工厂函数
    
    统一所有启动方式（python app.py / flask run）的初始化行为。
    """
    application = Flask(__name__)
    app_config = get_config(config_name)
    application.config.from_object(app_config)

    if not application.config.get("DEBUG") and application.config.get("SECRET_KEY") in (None, "", "dev-secret-change-in-production"):
        raise ValueError("SECRET_KEY must be set for production")

    # 初始化日志
    setup_logging(application)

    # 启用访问日志中间件（before_request/after_request）
    log_request(application)

    # 初始化 CSRF 保护
    if CSRF_AVAILABLE and CSRFProtect and application.config.get("WTF_CSRF_ENABLED", True):
        CSRFProtect(application)
    elif application.config.get("WTF_CSRF_ENABLED", True):
        raise RuntimeError("flask-wtf is required for CSRF protection")

    # 注册错误处理器
    _register_error_handlers(application)

    # 注册数据库连接管理
    _register_teardown(application)

    # 注册上下文处理器和安全头
    _register_context_and_security(application)

    # 注册请求级用户上下文（每请求一次加载用户信息，消除重复查询）
    _register_user_context(application)

    # 统一注册蓝图
    _register_all_blueprints(application)

    # 注册根路由
    _register_root_routes(application)

    # 注册 CLI 命令（入口统一：flask --app app init-db / check-system）
    _register_cli_commands(application)

    # 确保必要目录存在
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(EXPORT_DIR, exist_ok=True)

    return application



def _register_error_handlers(application):
    """注册错误处理器"""
    @application.errorhandler(RequestEntityTooLarge)
    def handle_file_too_large(error):
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'error': '上传文件过大', 'status': 413}), 413
        flash('上传文件过大，请压缩后重试。', 'danger')
        return redirect(request.referrer or url_for('index'))


def _register_teardown(application):
    """注册数据库连接管理"""
    @application.teardown_appcontext
    def teardown_db(exception=None):
        """在请求结束时关闭数据库连接"""
        close_db()


def _register_user_context(application):
    """注册请求级用户上下文
    
    每个请求最多查一次数据库，将用户信息缓存到 g.user_ctx。
    后续 decorators、helpers、blueprint 直接从 g.user_ctx 读取，
    消除重复的 SELECT role FROM users 查询。
    """
    @application.before_request
    def load_user_context():
        """Load user context into g for the current request"""
        g.user_ctx = None

        user_id = session.get('user_id')
        if not user_id or not session.get('logged_in'):
            return

        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                SELECT u.id, u.username, u.role, u.department_id,
                       d.level AS dept_level, d.name AS dept_name, d.path AS dept_path
                FROM users u
                LEFT JOIN departments d ON u.department_id = d.id
                WHERE u.id = %s
            """, (user_id,))
            row = cur.fetchone()
            if row:
                g.user_ctx = dict(row)
        except Exception:
            # 用户上下文加载失败不阻塞请求
            pass


# ==================== 数据库初始化 ====================

def init_db():
    """初始化数据库表和索引 - MySQL
    
    注意：此函数在请求上下文外运行（CLI/启动时），
    必须显式 close_db() 回收连接。
    """
    try:
        # 使用 models/database.py 中的初始化函数
        init_database()

        # 初始化基础数据（部门、管理员账户、停用词等）
        bootstrap_data()

        # 初始化算法配置（已迁移到 services/bootstrap_service.py）
        from services.bootstrap_service import init_algorithm_config
        init_algorithm_config()
    finally:
        # 启动型调用不在请求上下文内，teardown_appcontext 不会触发
        close_db()


# ==================== CLI 命令 ====================

def _register_cli_commands(application):
    """注册 Flask CLI 命令，统一入口语义
    
    使用方式：
        flask --app app init-db      # 初始化数据库和基础数据
        flask --app app check-system  # 检查系统依赖
    """
    @application.cli.command('init-db')
    @click.option('--silent', is_flag=True, help='静默模式')
    def cli_init_db(silent):
        """初始化数据库表、索引和基础数据"""
        if not silent:
            click.echo('🔧 开始初始化数据库...')
        init_db()
        if not silent:
            click.echo('✅ 数据库初始化完成')

    @application.cli.command('check-system')
    def cli_check_system():
        """检查系统依赖"""
        from utils.system_check import check_system_dependencies
        check_system_dependencies(silent=False, interactive=False)

    @application.cli.command('migrate-employee-id')
    @click.option('--dry-run', is_flag=True, help='仅预览，不执行')
    def cli_migrate_employee_id(dry_run):
        """为业务表添加 employee_id 外键并回填"""
        from scripts.migrate_employee_id import migrate_employee_id
        migrate_employee_id(dry_run=dry_run)

    @application.cli.command('migrate-dates')
    @click.option('--dry-run', is_flag=True, help='仅预览，不执行')
    def cli_migrate_dates(dry_run):
        """将 employees 表日期字段迁移为 DATE 类型"""
        from scripts.migrate_date_fields import migrate_date_fields
        migrate_date_fields(dry_run=dry_run)


# ==================== 上下文处理器和安全头 ====================

def _register_context_and_security(application):
    """注册上下文处理器和安全头（配置驱动）"""

    @application.context_processor
    def inject_csrf_token():
        """Inject CSRF token into all templates"""
        if CSRF_AVAILABLE:
            return {'csrf_token': generate_csrf}
        return {'csrf_token': lambda: ""}

    @application.after_request
    def set_security_headers(response):
        """Add security headers to all responses - 从 app 实例级配置读取"""
        cfg = application.config
        response.headers['X-Frame-Options'] = cfg.get('X_FRAME_OPTIONS', 'DENY')
        response.headers['X-Content-Type-Options'] = cfg.get('X_CONTENT_TYPE_OPTIONS', 'nosniff')
        response.headers['X-XSS-Protection'] = cfg.get('X_XSS_PROTECTION', '1; mode=block')

        # CSP 从实例配置读取
        csp_config = cfg.get('CSP', {})
        if csp_config:
            csp_parts = [f"{key} {value}" for key, value in csp_config.items()]
            response.headers['Content-Security-Policy'] = '; '.join(csp_parts)

        referrer_policy = cfg.get('REFERRER_POLICY')
        if referrer_policy:
            response.headers['Referrer-Policy'] = referrer_policy

        return response


# ==================== Blueprint 注册 ====================

def _register_all_blueprints(application):
    """统一注册所有蓝图 - 委托给 blueprints/__init__.py 唯一注册入口"""
    from blueprints import register_blueprints
    register_blueprints(application)


def _register_root_routes(application):
    """注册根路由"""
    @application.route('/')
    def index():
        """首页，重定向到人员管理"""
        if not session.get('logged_in'):
            return redirect(url_for('auth.login'))
        return redirect(url_for('personnel.dashboard'))


# ==================== 应用入口 ====================

# ==================== 创建应用实例 ====================
# 兼容原有的全局 app 引用（flask run 需要模块级 app 变量）
app = create_app()


# ==================== 应用入口 ====================

if __name__ == "__main__":
    # 检查系统依赖
    print("\n" + "=" * 70)
    print("🚀 启动班组管理系统")
    print("=" * 70 + "\n")

    from utils.system_check import check_system_dependencies
    check_system_dependencies(silent=False, interactive=False)

    # 初始化数据库（使用 IF NOT EXISTS，安全地创建缺失的表）
    print()  # 空行分隔
    init_db()

    # 启动应用
    print("\n" + "=" * 70)
    print("✓ 系统启动成功")
    print(f"访问地址: http://0.0.0.0:{int(os.environ.get('PORT', 5001))}")
    print("=" * 70 + "\n")

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5001)),
        debug=app.config.get("DEBUG", False)
    )
