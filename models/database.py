#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database connection and management module
Supports both SQLite and MySQL backends
"""
import os
from threading import local
from config.settings import DB_PATH, DatabaseConfig

# Thread-local storage for database connections
_local = local()


def is_mysql():
    """Check if MySQL is configured as the database backend"""
    return DatabaseConfig.DB_TYPE.lower() == 'mysql'


def get_db():
    """Get database connection with optimized settings"""
    if not hasattr(_local, 'connection'):
        if is_mysql():
            _local.connection = _get_mysql_connection()
        else:
            _local.connection = _get_sqlite_connection()

    return _local.connection


def _get_sqlite_connection():
    """Get SQLite database connection"""
    import sqlite3

    conn = sqlite3.connect(
        DB_PATH,
        timeout=DatabaseConfig.TIMEOUT,
        check_same_thread=DatabaseConfig.CHECK_SAME_THREAD
    )
    conn.row_factory = sqlite3.Row

    # SQLite Performance optimizations
    if DatabaseConfig.FOREIGN_KEYS:
        conn.execute("PRAGMA foreign_keys = ON")

    conn.execute(f"PRAGMA journal_mode = {DatabaseConfig.JOURNAL_MODE}")
    conn.execute(f"PRAGMA synchronous = {DatabaseConfig.SYNCHRONOUS}")
    conn.execute(f"PRAGMA cache_size = {DatabaseConfig.CACHE_SIZE}")

    return conn


def _get_mysql_connection():
    """Get MySQL database connection"""
    import pymysql
    from pymysql.cursors import DictCursor

    conn = pymysql.connect(
        host=DatabaseConfig.MYSQL_HOST,
        port=DatabaseConfig.MYSQL_PORT,
        user=DatabaseConfig.MYSQL_USER,
        password=DatabaseConfig.MYSQL_PASSWORD,
        database=DatabaseConfig.MYSQL_DATABASE,
        charset=DatabaseConfig.MYSQL_CHARSET,
        cursorclass=DictCursor,
        autocommit=False
    )

    return conn


def close_db():
    """Close database connection"""
    if hasattr(_local, 'connection'):
        _local.connection.close()
        delattr(_local, 'connection')


def get_param_placeholder():
    """Get parameter placeholder based on database type"""
    return '%s' if is_mysql() else '?'


def get_year_month_concat():
    """
    Get SQL expression for concatenating year and month into 'YYYY-MM' format.
    Returns the SQL expression string to use in queries.

    Usage:
        query = f"SELECT * FROM performance_records WHERE {get_year_month_concat()} >= ?"
    """
    if is_mysql():
        # MySQL: CONCAT(year, '-', LPAD(month, 2, '0'))
        return "CONCAT(year, '-', LPAD(month, 2, '0'))"
    else:
        # SQLite: year || '-' || printf('%02d', month)
        return "year || '-' || printf('%02d', month)"


def init_database():
    """Initialize database with all tables and indexes"""
    conn = get_db()
    cur = conn.cursor()

    # Use CURRENT_TIMESTAMP for both SQLite and MySQL compatibility
    if is_mysql():
        _init_mysql_tables(cur)
    else:
        _init_sqlite_tables(cur)

    conn.commit()
    return conn


def _init_sqlite_tables(cur):
    """Initialize SQLite tables"""
    import sqlite3

    # Create tables with foreign key constraints
    tables = [
        # Users table
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            department_id INTEGER,
            role TEXT DEFAULT 'user',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL
        )
        """,

        # Departments table
        """
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parent_id INTEGER,
            description TEXT,
            manager_user_id INTEGER,
            level INTEGER DEFAULT 1,
            path TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_id) REFERENCES departments(id) ON DELETE SET NULL,
            FOREIGN KEY (manager_user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """,

        # Employees table
        """
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_no TEXT NOT NULL,
            name TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            class_name TEXT,
            position TEXT,
            birth_date TEXT,
            marital_status TEXT,
            hometown TEXT,
            political_status TEXT,
            specialty TEXT,
            education TEXT,
            graduation_school TEXT,
            work_start_date TEXT,
            entry_date TEXT,
            department_id INTEGER,
            solo_driving_date TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(emp_no, user_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL
        )
        """,

        # Performance records table
        """
        CREATE TABLE IF NOT EXISTS performance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_no TEXT NOT NULL,
            name TEXT NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            score REAL,
            grade TEXT,
            src_file TEXT,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(emp_no, year, month, user_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """,

        # Training records table
        """
        CREATE TABLE IF NOT EXISTS training_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_no TEXT NOT NULL,
            name TEXT NOT NULL,
            team_name TEXT,
            training_date TEXT NOT NULL,
            project_id INTEGER,
            problem_type TEXT,
            specific_problem TEXT,
            corrective_measures TEXT,
            time_spent TEXT,
            score INTEGER,
            assessor TEXT,
            remarks TEXT,
            is_qualified INTEGER DEFAULT 1,
            is_disqualified INTEGER DEFAULT 0,
            is_retake INTEGER DEFAULT 0,
            retake_of_record_id INTEGER,
            user_id INTEGER NOT NULL,
            source_file TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (retake_of_record_id) REFERENCES training_records(id) ON DELETE SET NULL,
            FOREIGN KEY (project_id) REFERENCES training_projects(id) ON DELETE SET NULL
        )
        """,

        # Safety inspection records table
        """
        CREATE TABLE IF NOT EXISTS safety_inspection_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            inspection_date TEXT NOT NULL,
            location TEXT,
            hazard_description TEXT,
            corrective_measures TEXT,
            deadline_date TEXT,
            inspected_person TEXT,
            responsible_team TEXT,
            assessment TEXT,
            rectification_status TEXT,
            rectifier TEXT,
            work_type TEXT,
            responsibility_location TEXT,
            inspection_item TEXT,
            created_by INTEGER,
            source_file TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
        )
        """,

        # Grade mapping table
        """
        CREATE TABLE IF NOT EXISTS grade_map (
            user_id INTEGER NOT NULL,
            grade TEXT NOT NULL,
            value REAL NOT NULL,
            PRIMARY KEY (user_id, grade),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """,

        # Quarter overrides table
        """
        CREATE TABLE IF NOT EXISTS quarter_overrides (
            user_id INTEGER NOT NULL,
            emp_no TEXT NOT NULL,
            year INTEGER NOT NULL,
            quarter INTEGER NOT NULL,
            grade TEXT NOT NULL,
            PRIMARY KEY (user_id, emp_no, year, quarter),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """,

        # Quarter grade options table
        """
        CREATE TABLE IF NOT EXISTS quarter_grade_options (
            user_id INTEGER NOT NULL,
            grade TEXT NOT NULL,
            display_order INTEGER NOT NULL,
            is_default INTEGER NOT NULL DEFAULT 0,
            color TEXT,
            PRIMARY KEY (user_id, grade),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """,

        # Stopwords table for NLP text mining
        """
        CREATE TABLE IF NOT EXISTS stopwords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL UNIQUE,
            category TEXT DEFAULT 'custom',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,

        # AI Providers configuration table
        """
        CREATE TABLE IF NOT EXISTS ai_providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            provider_type TEXT NOT NULL,
            api_key TEXT,
            base_url TEXT NOT NULL,
            model TEXT NOT NULL,
            is_active INTEGER DEFAULT 0,
            is_default INTEGER DEFAULT 0,
            priority INTEGER DEFAULT 0,
            timeout INTEGER DEFAULT 30,
            max_tokens INTEGER DEFAULT 200,
            temperature REAL DEFAULT 0.7,
            extra_headers TEXT,
            description TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,

        # AI usage logs table
        """
        CREATE TABLE IF NOT EXISTS ai_usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider_id INTEGER,
            provider_name TEXT,
            model TEXT,
            tokens_used INTEGER DEFAULT 0,
            success INTEGER DEFAULT 1,
            error_message TEXT,
            request_type TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (provider_id) REFERENCES ai_providers(id) ON DELETE SET NULL
        )
        """,

        # AI analysis history table (for caching AI diagnosis results)
        """
        CREATE TABLE IF NOT EXISTS ai_analysis_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_no TEXT NOT NULL,
            data_hash TEXT NOT NULL,
            time_window TEXT,
            ai_result TEXT NOT NULL,
            provider_name TEXT,
            model TEXT,
            tokens_used INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(emp_no, data_hash)
        )
        """,

        # Training projects table
        """
        CREATE TABLE IF NOT EXISTS training_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """,

        # AI prompt configurations table
        """
        CREATE TABLE IF NOT EXISTS ai_prompt_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            prompt_type TEXT NOT NULL,
            system_prompt TEXT,
            user_prompt_template TEXT NOT NULL,
            is_active INTEGER DEFAULT 0,
            is_default INTEGER DEFAULT 0,
            description TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    ]

    # Execute table creation
    for table_sql in tables:
        try:
            cur.execute(table_sql)
        except sqlite3.Error as e:
            print(f"Error creating table: {e}")

    # Create performance indexes
    _create_indexes(cur, is_mysql=False)


def _init_mysql_tables(cur):
    """Initialize MySQL tables"""
    # Create tables with MySQL syntax
    tables = [
        # Users table
        """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            department_id INT,
            role VARCHAR(50) DEFAULT 'user',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,

        # Departments table
        """
        CREATE TABLE IF NOT EXISTS departments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            parent_id INT,
            description TEXT,
            manager_user_id INT,
            level INT DEFAULT 1,
            path VARCHAR(500),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_id) REFERENCES departments(id) ON DELETE SET NULL,
            FOREIGN KEY (manager_user_id) REFERENCES users(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,

        # Employees table
        """
        CREATE TABLE IF NOT EXISTS employees (
            id INT AUTO_INCREMENT PRIMARY KEY,
            emp_no VARCHAR(100) NOT NULL,
            name VARCHAR(255) NOT NULL,
            user_id INT NOT NULL,
            class_name VARCHAR(255),
            position VARCHAR(255),
            birth_date VARCHAR(20),
            marital_status VARCHAR(50),
            hometown VARCHAR(255),
            political_status VARCHAR(100),
            specialty VARCHAR(255),
            education VARCHAR(100),
            graduation_school VARCHAR(255),
            work_start_date VARCHAR(20),
            entry_date VARCHAR(20),
            department_id INT,
            solo_driving_date VARCHAR(20),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_emp_user (emp_no, user_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,

        # Performance records table
        """
        CREATE TABLE IF NOT EXISTS performance_records (
            id INT AUTO_INCREMENT PRIMARY KEY,
            emp_no VARCHAR(100) NOT NULL,
            name VARCHAR(255) NOT NULL,
            year INT NOT NULL,
            month INT NOT NULL,
            score DECIMAL(10,2),
            grade VARCHAR(50),
            src_file VARCHAR(500),
            user_id INT NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_perf (emp_no, year, month, user_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,

        # Training records table
        """
        CREATE TABLE IF NOT EXISTS training_records (
            id INT AUTO_INCREMENT PRIMARY KEY,
            emp_no VARCHAR(100) NOT NULL,
            name VARCHAR(255) NOT NULL,
            team_name VARCHAR(255),
            training_date VARCHAR(20) NOT NULL,
            project_id INT,
            problem_type VARCHAR(255),
            specific_problem TEXT,
            corrective_measures TEXT,
            time_spent VARCHAR(100),
            score INT,
            assessor VARCHAR(255),
            remarks TEXT,
            is_qualified INT DEFAULT 1,
            is_disqualified INT DEFAULT 0,
            is_retake INT DEFAULT 0,
            retake_of_record_id INT,
            user_id INT NOT NULL,
            source_file VARCHAR(500),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (retake_of_record_id) REFERENCES training_records(id) ON DELETE SET NULL,
            FOREIGN KEY (project_id) REFERENCES training_projects(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,

        # Safety inspection records table
        """
        CREATE TABLE IF NOT EXISTS safety_inspection_records (
            id INT AUTO_INCREMENT PRIMARY KEY,
            category VARCHAR(255) NOT NULL,
            inspection_date VARCHAR(20) NOT NULL,
            location VARCHAR(500),
            hazard_description TEXT,
            corrective_measures TEXT,
            deadline_date VARCHAR(20),
            inspected_person VARCHAR(255),
            responsible_team VARCHAR(255),
            assessment TEXT,
            rectification_status VARCHAR(100),
            rectifier VARCHAR(255),
            work_type VARCHAR(255),
            responsibility_location VARCHAR(500),
            inspection_item VARCHAR(500),
            created_by INT,
            source_file VARCHAR(500),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,

        # Grade mapping table
        """
        CREATE TABLE IF NOT EXISTS grade_map (
            user_id INT NOT NULL,
            grade VARCHAR(50) NOT NULL,
            value DECIMAL(10,2) NOT NULL,
            PRIMARY KEY (user_id, grade),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,

        # Quarter overrides table
        """
        CREATE TABLE IF NOT EXISTS quarter_overrides (
            user_id INT NOT NULL,
            emp_no VARCHAR(100) NOT NULL,
            year INT NOT NULL,
            quarter INT NOT NULL,
            grade VARCHAR(50) NOT NULL,
            PRIMARY KEY (user_id, emp_no, year, quarter),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,

        # Quarter grade options table
        """
        CREATE TABLE IF NOT EXISTS quarter_grade_options (
            user_id INT NOT NULL,
            grade VARCHAR(50) NOT NULL,
            display_order INT NOT NULL,
            is_default INT NOT NULL DEFAULT 0,
            color VARCHAR(50),
            PRIMARY KEY (user_id, grade),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,

        # Stopwords table for NLP text mining
        """
        CREATE TABLE IF NOT EXISTS stopwords (
            id INT AUTO_INCREMENT PRIMARY KEY,
            word VARCHAR(100) NOT NULL UNIQUE,
            category VARCHAR(100) DEFAULT 'custom',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,

        # AI Providers configuration table
        """
        CREATE TABLE IF NOT EXISTS ai_providers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            provider_type VARCHAR(100) NOT NULL,
            api_key VARCHAR(500),
            base_url VARCHAR(500) NOT NULL,
            model VARCHAR(255) NOT NULL,
            is_active INT DEFAULT 0,
            is_default INT DEFAULT 0,
            priority INT DEFAULT 0,
            timeout INT DEFAULT 30,
            max_tokens INT DEFAULT 200,
            temperature DECIMAL(3,2) DEFAULT 0.70,
            extra_headers TEXT,
            description TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,

        # AI usage logs table
        """
        CREATE TABLE IF NOT EXISTS ai_usage_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            provider_id INT,
            provider_name VARCHAR(255),
            model VARCHAR(255),
            tokens_used INT DEFAULT 0,
            success INT DEFAULT 1,
            error_message TEXT,
            request_type VARCHAR(100),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (provider_id) REFERENCES ai_providers(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,

        # AI analysis history table (for caching AI diagnosis results)
        """
        CREATE TABLE IF NOT EXISTS ai_analysis_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            emp_no VARCHAR(100) NOT NULL,
            data_hash VARCHAR(64) NOT NULL,
            time_window VARCHAR(50),
            ai_result TEXT NOT NULL,
            provider_name VARCHAR(255),
            model VARCHAR(255),
            tokens_used INT DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_emp_hash (emp_no, data_hash)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,

        # Training projects table
        """
        CREATE TABLE IF NOT EXISTS training_projects (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            user_id INT NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,

        # AI prompt configurations table
        """
        CREATE TABLE IF NOT EXISTS ai_prompt_configs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            prompt_type VARCHAR(100) NOT NULL,
            system_prompt TEXT,
            user_prompt_template TEXT NOT NULL,
            is_active INT DEFAULT 0,
            is_default INT DEFAULT 0,
            description TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    ]

    # Execute table creation (handle circular foreign key references)
    # First create tables without foreign keys that reference other tables
    for table_sql in tables:
        try:
            cur.execute(table_sql)
        except Exception as e:
            print(f"Error creating table: {e}")

    # Create performance indexes
    _create_indexes(cur, is_mysql=True)


def _create_indexes(cur, is_mysql=False):
    """Create performance indexes"""
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_departments_path ON departments(path)",
        "CREATE INDEX IF NOT EXISTS idx_departments_parent_id ON departments(parent_id)",
        "CREATE INDEX IF NOT EXISTS idx_users_department_id ON users(department_id)",
        "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
        "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
        "CREATE INDEX IF NOT EXISTS idx_employees_user_id ON employees(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_employees_emp_no ON employees(emp_no)",
        "CREATE INDEX IF NOT EXISTS idx_perf_user_year_month ON performance_records(user_id, year, month)",
        "CREATE INDEX IF NOT EXISTS idx_perf_emp_no ON performance_records(emp_no)",
        "CREATE INDEX IF NOT EXISTS idx_training_records_user_id ON training_records(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_training_records_emp_no ON training_records(emp_no)",
        "CREATE INDEX IF NOT EXISTS idx_training_records_date ON training_records(training_date)",
        "CREATE INDEX IF NOT EXISTS idx_training_records_disqualified ON training_records(is_disqualified)",
        "CREATE INDEX IF NOT EXISTS idx_safety_inspection_created_by ON safety_inspection_records(created_by)",
        "CREATE INDEX IF NOT EXISTS idx_safety_inspection_date ON safety_inspection_records(inspection_date)",
        "CREATE INDEX IF NOT EXISTS idx_safety_inspection_category ON safety_inspection_records(category)",
        "CREATE INDEX IF NOT EXISTS idx_safety_inspection_team ON safety_inspection_records(responsible_team)",
        "CREATE INDEX IF NOT EXISTS idx_stopwords_word ON stopwords(word)",
        "CREATE INDEX IF NOT EXISTS idx_stopwords_category ON stopwords(category)",
        "CREATE INDEX IF NOT EXISTS idx_ai_providers_active ON ai_providers(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_ai_providers_default ON ai_providers(is_default)",
        "CREATE INDEX IF NOT EXISTS idx_ai_usage_logs_provider ON ai_usage_logs(provider_id)",
        "CREATE INDEX IF NOT EXISTS idx_ai_usage_logs_created ON ai_usage_logs(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_ai_analysis_history_emp_hash ON ai_analysis_history(emp_no, data_hash)",
        "CREATE INDEX IF NOT EXISTS idx_ai_analysis_history_created ON ai_analysis_history(created_at)"
    ]

    for index_sql in indexes:
        try:
            if is_mysql:
                # MySQL doesn't support IF NOT EXISTS for indexes, need to check first
                index_name = index_sql.split('IF NOT EXISTS ')[1].split(' ON ')[0]
                table_name = index_sql.split(' ON ')[1].split('(')[0]
                try:
                    cur.execute(f"SHOW INDEX FROM {table_name} WHERE Key_name = '{index_name}'")
                    if cur.fetchone() is None:
                        # Index doesn't exist, create it
                        create_sql = index_sql.replace('IF NOT EXISTS ', '')
                        cur.execute(create_sql)
                except:
                    pass
            else:
                cur.execute(index_sql)
        except Exception as e:
            print(f"Warning: Could not create index: {e}")


def bootstrap_data():
    """Bootstrap initial data if database is empty"""
    conn = get_db()
    cur = conn.cursor()

    placeholder = get_param_placeholder()

    # Bootstrap default department
    cur.execute("SELECT COUNT(1) FROM departments")
    result = cur.fetchone()
    count = result[0] if isinstance(result, (list, tuple)) else result.get('COUNT(1)', 0)

    if count == 0:
        cur.execute(
            f"INSERT INTO departments(name, description, level, path) VALUES({placeholder}, {placeholder}, {placeholder}, {placeholder})",
            ("总公司", "顶级部门", 1, "/1")
        )
        conn.commit()

    # Bootstrap admin account
    cur.execute("SELECT COUNT(1) FROM users")
    result = cur.fetchone()
    count = result[0] if isinstance(result, (list, tuple)) else result.get('COUNT(1)', 0)

    if count == 0:
        from werkzeug.security import generate_password_hash

        bootstrap_user = os.environ.get("APP_USER", "admin").strip()
        bootstrap_pass = os.environ.get("APP_PASS", "admin123").strip()

        cur.execute(
            f"INSERT INTO users(username, password_hash, department_id, role) VALUES({placeholder}, {placeholder}, {placeholder}, {placeholder})",
            (bootstrap_user, generate_password_hash(bootstrap_pass), 1, "admin"),
        )
        conn.commit()

    # Bootstrap default stopwords
    bootstrap_stopwords()


def bootstrap_stopwords():
    """Initialize default stopwords for NLP text mining"""
    conn = get_db()
    cur = conn.cursor()

    placeholder = get_param_placeholder()

    # Check if stopwords already exist
    cur.execute("SELECT COUNT(1) FROM stopwords")
    result = cur.fetchone()
    count = result[0] if isinstance(result, (list, tuple)) else result.get('COUNT(1)', 0)

    if count > 0:
        return  # Already initialized

    # Default Chinese stopwords for text mining
    default_stopwords = [
        # 常用虚词
        "的", "了", "和", "是", "就", "都", "而", "及", "与", "着",
        "或", "一个", "没有", "我们", "你们", "他们", "它们", "这个", "那个", "这些",
        "那些", "之", "于", "以", "为", "其", "等", "但", "并", "把",
        "被", "比", "这", "那", "如", "你", "我", "他", "她", "它",
        # 标点符号
        "，", "。", "！", "？", "；", "：", """, """, "'", "'",
        "（", "）", "【", "】", "、", "…", "—", "《", "》",
        # 数字
        "一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
        "百", "千", "万", "亿", "第", "次", "个", "年", "月", "日",
        # 常用动词（在安全/培训记录中高频但无意义）
        "进行", "开展", "发现", "存在", "要求", "需要", "应该", "可以", "能够", "已经",
        "正在", "开始", "结束", "完成", "实施", "执行", "检查", "整改", "处理", "落实",
        # 常用名词（在记录中高频但无分析价值）
        "情况", "问题", "工作", "人员", "单位", "部门", "现场", "区域", "位置", "时间",
        "过程", "内容", "方面", "方式", "措施", "要求", "标准", "规定", "制度", "管理",
        # 连接词
        "因为", "所以", "但是", "而且", "或者", "如果", "虽然", "不过", "然而", "因此",
        "此外", "另外", "同时", "首先", "其次", "最后", "总之", "即", "也", "还",
        # 程度副词
        "很", "非常", "特别", "十分", "相当", "比较", "稍微", "略", "更", "最",
        "太", "极", "过于", "尤其", "格外", "分外", "越", "越来越", "愈", "愈加",
        # 时间词
        "今天", "明天", "昨天", "现在", "当前", "目前", "近期", "最近", "以前", "以后",
        "之前", "之后", "期间", "当时", "随后", "立即", "马上", "即刻", "暂时", "临时",
        # 指示代词
        "这里", "那里", "这边", "那边", "这样", "那样", "如此", "怎样", "怎么", "什么",
        "哪里", "哪个", "哪些", "谁", "多少", "几", "某", "某些", "各", "每",
        # 助词
        "吗", "呢", "吧", "啊", "呀", "哦", "哪", "啥", "嘛", "罢了",
        "而已", "罢", "矣", "焉", "耳", "乎", "兮", "也罢", "也好", "便是"
    ]

    # Insert default stopwords
    try:
        if is_mysql():
            cur.executemany(
                f"INSERT IGNORE INTO stopwords (word, category) VALUES ({placeholder}, 'builtin')",
                [(word,) for word in default_stopwords]
            )
        else:
            cur.executemany(
                "INSERT OR IGNORE INTO stopwords (word, category) VALUES (?, 'builtin')",
                [(word,) for word in default_stopwords]
            )
        conn.commit()
        print(f"Initialized {len(default_stopwords)} default stopwords")
    except Exception as e:
        print(f"Error initializing stopwords: {e}")


class DatabaseManager:
    """Database management helper class"""

    @staticmethod
    def execute_query(query, params=None, fetch=False):
        """Execute a query with optional parameters"""
        conn = get_db()
        cur = conn.cursor()

        try:
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)

            if fetch:
                return cur.fetchall()
            else:
                conn.commit()
                return cur.rowcount

        except Exception as e:
            conn.rollback()
            raise e

    @staticmethod
    def execute_many(query, params_list):
        """Execute a query with multiple parameter sets"""
        conn = get_db()
        cur = conn.cursor()

        try:
            cur.executemany(query, params_list)
            conn.commit()
            return cur.rowcount

        except Exception as e:
            conn.rollback()
            raise e

    @staticmethod
    def transaction(func):
        """Decorator for database transactions"""
        def wrapper(*args, **kwargs):
            conn = get_db()
            try:
                result = func(*args, **kwargs)
                conn.commit()
                return result
            except Exception as e:
                conn.rollback()
                raise e
        return wrapper
