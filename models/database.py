#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database connection and management module
MySQL backend only
"""
import os
import pymysql
from pymysql.cursors import DictCursor
from threading import local
from config.settings import DatabaseConfig

# Thread-local storage for database connections
_local = local()


def get_db():
    """Get MySQL database connection"""
    if not hasattr(_local, 'connection') or _local.connection is None:
        _local.connection = pymysql.connect(
            host=DatabaseConfig.MYSQL_HOST,
            port=DatabaseConfig.MYSQL_PORT,
            user=DatabaseConfig.MYSQL_USER,
            password=DatabaseConfig.MYSQL_PASSWORD,
            database=DatabaseConfig.MYSQL_DATABASE,
            charset=DatabaseConfig.MYSQL_CHARSET,
            cursorclass=DictCursor,
            autocommit=False
        )
    return _local.connection


def close_db():
    """Close database connection"""
    if hasattr(_local, 'connection') and _local.connection:
        try:
            _local.connection.close()
        except pymysql.Error:
            pass  # Ignore if already closed
        finally:
            _local.connection = None


def get_year_month_concat():
    """
    Get SQL expression for concatenating year and month into 'YYYY-MM' format.
    Returns the SQL expression string to use in queries.
    """
    return "CONCAT(year, '-', LPAD(month, 2, '0'))"


def init_database():
    """Initialize database with all tables and indexes"""
    conn = get_db()
    cur = conn.cursor()
    _init_mysql_tables(cur)
    conn.commit()
    return conn


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
            emp_no VARCHAR(100) NOT NULL UNIQUE,
            name VARCHAR(255) NOT NULL,
            created_by INT,
            class_name VARCHAR(255),
            position VARCHAR(255),
            birth_date VARCHAR(20),
            certification_date VARCHAR(20),
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
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
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
            created_by INT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_perf (emp_no, year, month),
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
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
            project_name_snapshot VARCHAR(255),
            category_name_snapshot VARCHAR(255),
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
            created_by INT,
            source_file VARCHAR(500),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
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
            grade VARCHAR(50) NOT NULL PRIMARY KEY,
            value DECIMAL(10,2) NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,

        # Quarter overrides table (全局配置，不按用户隔离)
        """
        CREATE TABLE IF NOT EXISTS quarter_overrides (
            emp_no VARCHAR(100) NOT NULL,
            year INT NOT NULL,
            quarter INT NOT NULL,
            grade VARCHAR(50) NOT NULL,
            PRIMARY KEY (emp_no, year, quarter)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,

        # Quarter grade options table (全局配置，不按用户隔离)
        """
        CREATE TABLE IF NOT EXISTS quarter_grade_options (
            grade VARCHAR(50) NOT NULL PRIMARY KEY,
            display_order INT NOT NULL,
            is_default INT NOT NULL DEFAULT 0,
            color VARCHAR(50)
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
            temperature FLOAT DEFAULT 0.70,
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
            name VARCHAR(255) NOT NULL UNIQUE,
            description TEXT,
            category_id INT,
            is_active INT NOT NULL DEFAULT 1,
            is_archived INT NOT NULL DEFAULT 0,
            archived_at DATETIME,
            archived_by INT,
            created_by INT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES training_project_categories(id) ON DELETE SET NULL,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (archived_by) REFERENCES users(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,

        # AI prompt configurations table (5-dimension analysis)
        """
        CREATE TABLE IF NOT EXISTS ai_analysis_config (
            id INT AUTO_INCREMENT PRIMARY KEY,
            config_key VARCHAR(50) NOT NULL UNIQUE,
            title VARCHAR(255) NOT NULL,
            default_instruction TEXT,
            current_instruction TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
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
        """,

        # Training project categories table
        """
        CREATE TABLE IF NOT EXISTS training_project_categories (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL UNIQUE,
            description TEXT,
            display_order INT DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,

        # Import logs audit table
        """
        CREATE TABLE IF NOT EXISTS import_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            module VARCHAR(100) NOT NULL,
            operation VARCHAR(100) NOT NULL,
            user_id INT,
            username VARCHAR(255) NOT NULL,
            user_role VARCHAR(50) NOT NULL,
            department_id INT,
            department_name VARCHAR(255),
            file_name VARCHAR(500),
            total_rows INT DEFAULT 0,
            success_rows INT DEFAULT 0,
            failed_rows INT DEFAULT 0,
            skipped_rows INT DEFAULT 0,
            error_message TEXT,
            import_details TEXT,
            ip_address VARCHAR(50),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,

        # Algorithm presets table
        """
        CREATE TABLE IF NOT EXISTS algorithm_presets (
            id INT AUTO_INCREMENT PRIMARY KEY,
            preset_name VARCHAR(255) NOT NULL UNIQUE,
            preset_key VARCHAR(100) NOT NULL UNIQUE,
            description TEXT,
            config_data TEXT NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,

        # Algorithm active config table
        """
        CREATE TABLE IF NOT EXISTS algorithm_active_config (
            id INT PRIMARY KEY DEFAULT 1,
            based_on_preset VARCHAR(100),
            is_customized INT DEFAULT 0,
            config_data TEXT NOT NULL,
            updated_by INT,
            updated_at DATETIME,
            FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL,
            CHECK (id = 1)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,

        # Algorithm config logs table
        """
        CREATE TABLE IF NOT EXISTS algorithm_config_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            action VARCHAR(50) NOT NULL,
            preset_name VARCHAR(255),
            old_config TEXT,
            new_config TEXT,
            change_reason TEXT,
            changed_by INT,
            changed_by_name VARCHAR(255),
            changed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            ip_address VARCHAR(50),
            FOREIGN KEY (changed_by) REFERENCES users(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        
        # Async tasks table
        """
        CREATE TABLE IF NOT EXISTS async_tasks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            task_type VARCHAR(50) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, processing, completed, failed
            user_id INT,
            file_name VARCHAR(255),
            file_path VARCHAR(500),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            completed_at DATETIME,
            result_message TEXT,
            error_message TEXT,
            meta_data TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    ]

    # Execute table creation (handle circular foreign key references)
    # Disable foreign key checks to handle circular dependencies
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")

    for table_sql in tables:
        try:
            cur.execute(table_sql)
        except Exception as e:
            print(f"Error creating table: {e}")

    # Re-enable foreign key checks
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")

    # Create view for recent imports (MySQL version)
    try:
        cur.execute("DROP VIEW IF EXISTS v_recent_imports")
        cur.execute("""
            CREATE VIEW v_recent_imports AS
            SELECT
                il.*,
                d.name as dept_name,
                CASE
                    WHEN il.user_role = 'admin' THEN '系统管理员'
                    WHEN il.user_role = 'manager' THEN '部门管理员'
                    ELSE '普通用户'
                END as role_display,
                CASE il.module
                    WHEN 'personnel' THEN '人员管理'
                    WHEN 'performance' THEN '绩效管理'
                    WHEN 'training' THEN '培训管理'
                    WHEN 'safety' THEN '安全管理'
                    ELSE il.module
                END as module_display
            FROM import_logs il
            LEFT JOIN departments d ON il.department_id = d.id
            ORDER BY il.created_at DESC
            LIMIT 100
        """)
    except Exception as e:
        print(f"Error creating view: {e}")

    # Create performance indexes
    _create_indexes(cur)


def _create_indexes(cur):
    """Create performance indexes for MySQL"""
    indexes = [
        ("idx_departments_path", "departments", "path"),
        ("idx_departments_parent_id", "departments", "parent_id"),
        ("idx_users_department_id", "users", "department_id"),
        ("idx_users_role", "users", "role"),
        ("idx_users_username", "users", "username"),
        ("idx_employees_dept_id", "employees", "department_id"),
        ("idx_employees_emp_no", "employees", "emp_no"),
        ("idx_perf_year_month", "performance_records", "year, month"),
        ("idx_perf_emp_no", "performance_records", "emp_no"),
        ("idx_training_records_created_by", "training_records", "created_by"),
        ("idx_training_records_emp_no", "training_records", "emp_no"),
        ("idx_training_records_date", "training_records", "training_date"),
        ("idx_training_records_disqualified", "training_records", "is_disqualified"),
        ("idx_safety_inspection_created_by", "safety_inspection_records", "created_by"),
        ("idx_safety_inspection_date", "safety_inspection_records", "inspection_date"),
        ("idx_safety_inspection_category", "safety_inspection_records", "category"),
        ("idx_safety_inspection_team", "safety_inspection_records", "responsible_team"),
        ("idx_stopwords_word", "stopwords", "word"),
        ("idx_stopwords_category", "stopwords", "category"),
        ("idx_ai_providers_active", "ai_providers", "is_active"),
        ("idx_ai_providers_default", "ai_providers", "is_default"),
        ("idx_ai_usage_logs_provider", "ai_usage_logs", "provider_id"),
        ("idx_ai_usage_logs_created", "ai_usage_logs", "created_at"),
        ("idx_ai_analysis_history_emp_hash", "ai_analysis_history", "emp_no, data_hash"),
        ("idx_ai_analysis_history_created", "ai_analysis_history", "created_at"),
        ("idx_import_logs_module", "import_logs", "module"),
        ("idx_import_logs_user_id", "import_logs", "user_id"),
        ("idx_import_logs_created_at", "import_logs", "created_at"),
        ("idx_import_logs_department_id", "import_logs", "department_id"),
        ("idx_config_logs_changed_at", "algorithm_config_logs", "changed_at"),
        ("idx_training_projects_category_id", "training_projects", "category_id"),
        ("idx_training_projects_archived", "training_projects", "is_archived"),
        ("idx_training_records_project_snapshot", "training_records", "project_name_snapshot"),
        # 性能优化复合索引
        ("idx_training_emp_date_composite", "training_records", "emp_no, training_date"),
        ("idx_safety_person_date_composite", "safety_inspection_records", "inspected_person, inspection_date"),
        ("idx_performance_emp_year_month", "performance_records", "emp_no, year, month"),
    ]

    for index_name, table_name, columns in indexes:
        try:
            cur.execute(f"SHOW INDEX FROM {table_name} WHERE Key_name = %s", (index_name,))
            if cur.fetchone() is None:
                cur.execute(f"CREATE INDEX {index_name} ON {table_name}({columns})")
        except Exception as e:
            print(f"Warning: Could not create index: {e}")


def bootstrap_data():
    """Bootstrap initial data if database is empty"""
    conn = get_db()
    cur = conn.cursor()

    # Bootstrap default department
    cur.execute("SELECT COUNT(1) AS cnt FROM departments")
    result = cur.fetchone()
    count = result['cnt'] if result else 0

    if count == 0:
        cur.execute(
            "INSERT INTO departments(name, description, level, path) VALUES(%s, %s, %s, %s)",
            ("总公司", "顶级部门", 1, "/1")
        )
        conn.commit()

    # Bootstrap admin account
    cur.execute("SELECT COUNT(1) AS cnt FROM users")
    result = cur.fetchone()
    count = result['cnt'] if result else 0

    if count == 0:
        from werkzeug.security import generate_password_hash

        bootstrap_user = os.environ.get("APP_USER", "admin").strip()
        bootstrap_pass = os.environ.get("APP_PASS", "admin123").strip()

        cur.execute(
            "INSERT INTO users(username, password_hash, department_id, role) VALUES(%s, %s, %s, %s)",
            (bootstrap_user, generate_password_hash(bootstrap_pass), 1, "admin"),
        )
        conn.commit()

    # Bootstrap default stopwords
    bootstrap_stopwords()

    # Bootstrap default AI analysis configs
    bootstrap_ai_analysis_config()


def bootstrap_ai_analysis_config():
    """Initialize default AI analysis configurations"""
    conn = get_db()
    cur = conn.cursor()

    # Check if configs already exist
    cur.execute("SELECT COUNT(1) AS cnt FROM ai_analysis_config")
    result = cur.fetchone()
    count = result['cnt'] if result else 0

    if count > 0:
        return  # Already initialized

    # Default configs (copied from AIPromptConfigService to avoid circular import)
    default_configs = [
        {
            "key": "risk_profile",
            "title": "1. 关键风险画像",
            "instruction": """1. 高频违章点：指出出现频率最高的前3个问题类型。
2. 严重违章点：提取所有考核分值 > 3分（或双倍扣分）的严重问题。
3. 时空规律：分析这些问题是否集中在特定时间（如早晚班）或特定作业环节（如出入库、正线折返）。"""
        },
        {
            "key": "training_gap",
            "title": "2. 培训关联分析",
            "instruction": """1. 结合"培训失格"和"培训具体问题"记录，分析他的**实操弱项**是否直接导致了上述违章？
2. (例如：培训中多次"车门故障"不合格，现场是否也发生了车门操作违章？)"""
        },
        {
            "key": "root_cause",
            "title": "3. 根因深度定性",
            "instruction": """请判断该员工的主要风险来源是以下哪一种，并给出理由：
A. **技能型短板** (Skill Deficit): 业务生疏，不知道怎么做。
B. **习惯性违章** (Habitual Violation): 知道标准，但为了省事简化作业。
C. **状态型异常** (State Anomaly): 近期家庭变故、疲劳或情绪波动导致。"""
        },
        {
            "key": "prediction",
            "title": "4. 预测性预警",
            "instruction": """基于现有趋势，如果不仅行干预，预测该员工在未来 30 天内最可能发生的**具体安全事故**是什么？（如：冒进信号、夹人夹物等）。"""
        },
        {
            "key": "measures",
            "title": "5. 精准帮扶方案",
            "instruction": """针对上述原因，给出具体的帮扶措施（不要给万金油建议）。
- **技能型**：建议重修哪一门具体课程？
- **习惯型**：建议采取何种检查手段（如：加密视频抽查频次、跟车添乘）？"""
        }
    ]

    try:
        cur.executemany(
            """
            INSERT INTO ai_analysis_config (config_key, title, default_instruction, current_instruction)
            VALUES (%s, %s, %s, %s)
            """,
            [(c['key'], c['title'], c['instruction'], c['instruction']) for c in default_configs]
        )
        conn.commit()
        print(f"Initialized {len(default_configs)} AI analysis configs")
    except Exception as e:
        print(f"Error initializing AI analysis configs: {e}")


def bootstrap_stopwords():
    """Initialize default stopwords for NLP text mining"""
    conn = get_db()
    cur = conn.cursor()

    # Check if stopwords already exist
    cur.execute("SELECT COUNT(1) AS cnt FROM stopwords")
    result = cur.fetchone()
    count = result['cnt'] if result else 0

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
        cur.executemany(
            "INSERT IGNORE INTO stopwords (word, category) VALUES (%s, 'builtin')",
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
