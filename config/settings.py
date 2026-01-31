#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Application configuration settings
Separated from main app for better maintainability
"""
import os
from datetime import timedelta

# Base configuration
BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
EXPORT_DIR = os.path.join(BASE_DIR, "exports")

# Application settings
APP_TITLE = "班组管理系统"
SECRET_KEY = (
    os.environ.get("SECRET_KEY")
    or os.environ.get("APP_SECRET_KEY")
    or "dev-secret-change-in-production"
)
ALLOWED_EXTENSIONS = {"pdf", "xlsx", "xls"}
DINGTALK_CORP_ID = os.environ.get("DINGTALK_CORP_ID", "").strip()

# Security configuration
class SecurityConfig:
    # CSRF Protection
    WTF_CSRF_TIME_LIMIT = None  # No time limit for CSRF tokens
    WTF_CSRF_SSL_STRICT = False  # Set to True in production with HTTPS
    WTF_CSRF_ENABLED = os.environ.get("WTF_CSRF_ENABLED", "True").lower() == "true"

    # Session Security
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "False").lower() == "true"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = int(os.environ.get("SESSION_TIMEOUT", 3600 * 24))  # 24 hours default

    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", str(50 * 1024 * 1024)))

    # Security Headers
    X_FRAME_OPTIONS = "DENY"
    X_CONTENT_TYPE_OPTIONS = "nosniff"
    X_XSS_PROTECTION = "1; mode=block"
    REFERRER_POLICY = "strict-origin-when-cross-origin"

    # Content Security Policy
    CSP = {
        "default-src": "'self'",
        "script-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net https://g.alicdn.com",
        "style-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        "font-src": "'self' https://cdn.jsdelivr.net",
        "img-src": "'self' data:",
        "object-src": "'none'"
    }

# Database configuration (MySQL only)
class DatabaseConfig:
    # MySQL connection settings
    MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
    MYSQL_USER = os.environ.get("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "team_management")
    MYSQL_CHARSET = os.environ.get("MYSQL_CHARSET", "utf8mb4")

# Application environment
class Config:
    """Base configuration class"""

    def __init__(self):
        self.SECRET_KEY = SECRET_KEY
        self.SQLALCHEMY_TRACK_MODIFICATIONS = False
        self.DINGTALK_CORP_ID = DINGTALK_CORP_ID

        # Security settings
        for key, value in vars(SecurityConfig).items():
            if not key.startswith('_'):
                setattr(self, key, value)

        # Database settings
        for key, value in vars(DatabaseConfig).items():
            if not key.startswith('_'):
                setattr(self, key, value)

class DevelopmentConfig(Config):
    """Development environment configuration"""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_SSL_STRICT = False

class ProductionConfig(Config):
    """Production environment configuration"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    WTF_CSRF_SSL_STRICT = True

    # Override with production settings
    # Note: SECRET_KEY will be validated when this config is actually used
    SECRET_KEY = os.environ.get("SECRET_KEY") or None

    def __init__(self):
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY environment variable must be set in production")

class TestingConfig(Config):
    """Testing environment configuration"""
    DEBUG = True
    TESTING = True
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False

# Configuration selection
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config(config_name=None):
    """Get configuration class based on environment"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')

    return config.get(config_name, config['default'])()


# AI Configuration for risk diagnosis
class AIConfig:
    """AI/LLM configuration for behavior diagnosis"""

    # Provider: 'openrouter', 'qwen' (通义千问), 'wenxin' (文心一言), 'deepseek'
    PROVIDER = os.environ.get("AI_PROVIDER", "openrouter")

    # API Key (required)
    API_KEY = os.environ.get("AI_API_KEY", "")

    # Model selection
    # OpenRouter: 'anthropic/claude-3-haiku', 'openai/gpt-3.5-turbo', 'meta-llama/llama-3-8b-instruct'
    # Qwen: 'qwen-turbo', 'qwen-plus'
    # DeepSeek: 'deepseek-chat'
    MODEL = os.environ.get("AI_MODEL", "anthropic/claude-3-haiku")

    # Base URL for API
    BASE_URLS = {
        "openrouter": "https://openrouter.ai/api/v1",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "wenxin": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop",
        "deepseek": "https://api.deepseek.com/v1"
    }

    @classmethod
    @property
    def BASE_URL(cls) -> str:
        """Get base URL for current provider"""
        return os.environ.get("AI_BASE_URL", cls.BASE_URLS.get(cls.PROVIDER, cls.BASE_URLS["openrouter"]))

    # Request timeout in seconds
    TIMEOUT = float(os.environ.get("AI_TIMEOUT", "30"))

    # Cost control settings
    MAX_DIAGNOSES_PER_RUN = int(os.environ.get("AI_MAX_DIAGNOSES", "10"))  # Max AI calls per analysis run
    RISK_THRESHOLD = float(os.environ.get("AI_RISK_THRESHOLD", "80"))  # Min risk score to trigger AI
