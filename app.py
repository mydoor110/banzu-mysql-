#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
班组管理系统 - Blueprint 架构版本
主应用程序入口
"""
import os
from dotenv import load_dotenv
load_dotenv()

import json

from flask import Flask, redirect, url_for, session
from werkzeug.security import generate_password_hash

try:
    from flask_wtf.csrf import CSRFProtect, generate_csrf
    CSRF_AVAILABLE = True
except ImportError:
    CSRF_AVAILABLE = False
    def generate_csrf():
        return ""

# 导入配置
from config.settings import (
    APP_TITLE, SECRET_KEY,
    UPLOAD_DIR, EXPORT_DIR
)

# 导入数据库工具
from models.database import get_db, close_db, init_database, bootstrap_data

# 导入日志配置
from utils.logger import setup_logging

# ==================== Flask 应用初始化 ====================

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY

# Initialize logging
setup_logging(app)

# Security configurations
app.config["WTF_CSRF_TIME_LIMIT"] = None
app.config["WTF_CSRF_SSL_STRICT"] = False
app.config["SESSION_COOKIE_SECURE"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = 3600 * 8

# Initialize CSRF protection
if CSRF_AVAILABLE:
    csrf = CSRFProtect(app)
else:
    csrf = None


# ==================== 数据库连接管理 ====================

@app.teardown_appcontext
def teardown_db(exception=None):
    """在请求结束时关闭数据库连接"""
    close_db()


# ==================== 数据库初始化 ====================

def init_db():
    """初始化数据库表和索引 - MySQL"""
    # 使用 models/database.py 中的初始化函数
    init_database()

    # 初始化基础数据（部门、管理员账户、停用词等）
    bootstrap_data()

    # 初始化算法配置
    _init_algorithm_config()


def _init_algorithm_config():
    """初始化算法配置预设"""
    conn = get_db()
    cur = conn.cursor()

    # 检查算法预设表是否存在且为空
    try:
        cur.execute("SELECT COUNT(1) as cnt FROM algorithm_presets")
        result = cur.fetchone()
        count = result['cnt'] if result else 0
        if count > 0:
            conn.close()
            return  # 已初始化
    except:
        conn.close()
        return  # 表不存在，跳过

    # Initialize algorithm configuration presets
    # 标准档配置
    standard_config = {
        "performance": {
            "grade_coefficients": {"D": 0.0, "C": 0.6, "B": 0.9, "B+": 1.0, "A": 1.1},
            "grade_ranges": {
                "D": {"min": 0, "max": 79.9, "radar_override": 50},
                "C": {"min": 80, "max": 89.9},
                "B": {"min": 90, "max": 94.9},
                "B+": {"min": 95, "max": 99.9},
                "A": {"min": 100, "max": 110}
            },
            "contamination_rules": {
                "d_count_threshold": 1,
                "c_count_threshold": 2,
                "d_cap_score": 90,
                "c_cap_score": 94.9
            }
        },
        "safety": {
            "behavior_track": {
                "freq_thresholds": [2, 5, 6],
                "freq_multipliers": [2, 5, 10]
            },
            "severity_track": {
                "score_ranges": [
                    {"max": 3, "multiplier": 1.0},
                    {"min": 3, "max": 5, "multiplier": 2.5},
                    {"min": 5, "multiplier": 5.0}
                ],
                "critical_threshold": 12
            },
            "thresholds": {"fail_score": 60, "warning_score": 90}
        },
        "training": {
            "penalty_rules": {
                "absolute_threshold": {"fail_count": 3, "coefficient": 0.5},
                "small_sample": {"sample_size": 10, "coefficient": 0.7},
                "afr_thresholds": [
                    {"min": 2.5, "coefficient": 0.5, "label": "高频失格"},
                    {"min": 1.5, "max": 2.5, "coefficient": 0.7, "label": "频率偏高"},
                    {"min": 0.5, "max": 1.5, "coefficient": 0.9, "label": "偶发失格"}
                ]
            },
            "duration_thresholds": {
                "short_term_days": 60,
                "mid_term_days": 180,
                "default_scores": {"short": 65, "mid": 50, "long": 0}
            }
        },
        "comprehensive": {
            "score_weights": {
                "performance": 0.35,
                "safety": 0.30,
                "training": 0.20,
                "stability": 0.10,
                "learning": 0.05
            }
        },
        "key_personnel": {
            "comprehensive_threshold": 70,
            "monthly_violation_threshold": 3
        },
        "learning": {
            "potential_threshold": 0.5,
            "decline_threshold": -0.2,
            "decline_penalty": 0.8,
            "slope_amplifier": 10
        },
        "stability_new": {
            "base_stability": 100.0,
            "violation_penalty": 10.0,
            "redline_penalty": 40.0,
            "safety_cv_limit": 1.2
        },
        "learning_new": {
            "trend_warning_ratio": 1.5,
            "trend_warning_floor": 2,
            "trend_critical_ratio": 3.0,
            "trend_critical_floor": 5,
            "factor_improvement": 1.2,
            "factor_solidification": 0.4,
            "factor_deterioration": 0.0
        },
        "nine_grid": {
            "y_axis_weights": {
                "stability": 0.4,
                "learning": 0.6
            }
        }
    }

    # 严格档配置
    strict_config = json.loads(json.dumps(standard_config))
    strict_config["performance"]["contamination_rules"] = {
        "d_count_threshold": 1, "c_count_threshold": 2,
        "d_cap_score": 85, "c_cap_score": 92
    }
    strict_config["safety"]["severity_track"]["critical_threshold"] = 10
    strict_config["training"]["penalty_rules"]["absolute_threshold"]["coefficient"] = 0.4
    strict_config["training"]["penalty_rules"]["small_sample"]["coefficient"] = 0.6
    strict_config["training"]["penalty_rules"]["afr_thresholds"] = [
        {"min": 2.5, "coefficient": 0.4, "label": "高频失格"},
        {"min": 1.5, "max": 2.5, "coefficient": 0.6, "label": "频率偏高"},
        {"min": 0.5, "max": 1.5, "coefficient": 0.85, "label": "偶发失格"}
    ]
    strict_config["key_personnel"] = {
        "comprehensive_threshold": 75,
        "monthly_violation_threshold": 2
    }
    strict_config["learning"] = {
        "potential_threshold": 0.6,
        "decline_threshold": -0.2,
        "decline_penalty": 0.7,
        "slope_amplifier": 10
    }
    strict_config["stability_new"] = {
        "base_stability": 100.0,
        "violation_penalty": 15.0,
        "redline_penalty": 50.0,
        "safety_cv_limit": 1.0
    }
    strict_config["learning_new"] = {
        "trend_warning_ratio": 1.3,
        "trend_warning_floor": 2,
        "trend_critical_ratio": 2.5,
        "trend_critical_floor": 4,
        "factor_improvement": 1.3,
        "factor_solidification": 0.3,
        "factor_deterioration": 0.0
    }
    strict_config["nine_grid"] = {
        "y_axis_weights": {
            "stability": 0.4,
            "learning": 0.6
        }
    }

    # 宽松档配置
    lenient_config = json.loads(json.dumps(standard_config))
    lenient_config["performance"]["contamination_rules"] = {
        "d_count_threshold": 1, "c_count_threshold": 3,
        "d_cap_score": 95, "c_cap_score": 97
    }
    lenient_config["safety"]["severity_track"]["critical_threshold"] = 15
    lenient_config["training"]["penalty_rules"]["absolute_threshold"]["fail_count"] = 4
    lenient_config["training"]["penalty_rules"]["absolute_threshold"]["coefficient"] = 0.6
    lenient_config["training"]["penalty_rules"]["small_sample"]["coefficient"] = 0.8
    lenient_config["training"]["penalty_rules"]["afr_thresholds"] = [
        {"min": 3.0, "coefficient": 0.6, "label": "高频失格"},
        {"min": 2.0, "max": 3.0, "coefficient": 0.8, "label": "频率偏高"},
        {"min": 0.8, "max": 2.0, "coefficient": 0.95, "label": "偶发失格"}
    ]
    lenient_config["key_personnel"] = {
        "comprehensive_threshold": 65,
        "monthly_violation_threshold": 4
    }
    lenient_config["learning"] = {
        "potential_threshold": 0.4,
        "decline_threshold": -0.2,
        "decline_penalty": 0.9,
        "slope_amplifier": 10
    }
    lenient_config["stability_new"] = {
        "base_stability": 100.0,
        "violation_penalty": 8.0,
        "redline_penalty": 30.0,
        "safety_cv_limit": 1.5
    }
    lenient_config["learning_new"] = {
        "trend_warning_ratio": 2.0,
        "trend_warning_floor": 3,
        "trend_critical_ratio": 4.0,
        "trend_critical_floor": 6,
        "factor_improvement": 1.1,
        "factor_solidification": 0.5,
        "factor_deterioration": 0.0
    }
    lenient_config["nine_grid"] = {
        "y_axis_weights": {
            "stability": 0.4,
            "learning": 0.6
        }
    }

    # 插入预设方案
    presets = [
        ('严格', 'strict', '更严格的惩罚力度，适用于高要求场景', json.dumps(strict_config, ensure_ascii=False)),
        ('标准', 'standard', '标准惩罚力度，平衡公平与激励', json.dumps(standard_config, ensure_ascii=False)),
        ('宽松', 'lenient', '较宽松的惩罚力度，适用于培养阶段', json.dumps(lenient_config, ensure_ascii=False))
    ]
    for preset_name, preset_key, description, config_data in presets:
        cur.execute(
            "INSERT INTO algorithm_presets (preset_name, preset_key, description, config_data) VALUES (%s, %s, %s, %s)",
            (preset_name, preset_key, description, config_data)
        )

    # 初始化当前配置为"标准"档
    from datetime import datetime
    cur.execute(
        "INSERT INTO algorithm_active_config (id, based_on_preset, is_customized, config_data, updated_at) VALUES (1, 'standard', 0, %s, %s)",
        (json.dumps(standard_config, ensure_ascii=False), datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    )

    # 记录初始化日志
    cur.execute(
        "INSERT INTO algorithm_config_logs (action, preset_name, new_config, change_reason, changed_by, changed_by_name) VALUES ('INIT', 'standard', %s, '系统初始化', 1, 'system')",
        (json.dumps(standard_config, ensure_ascii=False),)
    )

    conn.commit()
    print("✅ 算法配置初始化完成: 已创建3个预设方案(严格/标准/宽松)，当前配置为'标准'档")
    conn.close()


# ==================== 上下文处理器和安全头 ====================

@app.context_processor
def inject_csrf_token():
    """Inject CSRF token into all templates"""
    if CSRF_AVAILABLE:
        return {'csrf_token': generate_csrf}
    return {'csrf_token': lambda: ""}


@app.after_request
def set_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "font-src 'self' https://cdn.jsdelivr.net; "
        "img-src 'self' data:; "
        "connect-src 'self' https://cdn.jsdelivr.net; "
        "object-src 'none'"
    )
    return response


# ==================== Blueprint 注册 ====================

from blueprints.auth import auth_bp
from blueprints.admin import admin_bp
from blueprints.departments import departments_bp
from blueprints.personnel import personnel_bp
from blueprints.training import training_bp
from blueprints.performance import performance_bp
from blueprints.safety import safety_bp
from blueprints.system_config import system_config_bp

app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(departments_bp)
app.register_blueprint(personnel_bp)
app.register_blueprint(training_bp)
app.register_blueprint(performance_bp)
app.register_blueprint(safety_bp)
app.register_blueprint(system_config_bp)


# ==================== 根路由 ====================

@app.route('/')
def index():
    """首页，重定向到绩效管理"""
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))
    return redirect(url_for('performance.index'))


# ==================== 应用入口 ====================

if __name__ == "__main__":
    # 确保必要的目录存在
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(EXPORT_DIR, exist_ok=True)

    # 初始化数据库（使用 IF NOT EXISTS，安全地创建缺失的表）
    init_db()

    # 启动应用
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)), debug=True)
