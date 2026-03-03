# -*- coding: utf-8 -*-
"""
Database Schema Definitions
Stores all CREATE TABLE statements and initial data constants
"""

SYSTEM_METADATA_TABLE = """
CREATE TABLE IF NOT EXISTS system_metadata (
    key_name VARCHAR(50) NOT NULL PRIMARY KEY,
    value VARCHAR(255),
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    dingtalk_userid VARCHAR(128),
    dingtalk_unionid VARCHAR(128),
    display_name VARCHAR(255),
    department_id INT,
    role VARCHAR(50) DEFAULT 'user',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_dingtalk_userid (dingtalk_userid),
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

DINGTALK_TOKEN_TABLE = """
CREATE TABLE IF NOT EXISTS dingtalk_token_cache (
    id INT PRIMARY KEY,
    access_token VARCHAR(512) NOT NULL,
    expires_at DATETIME NOT NULL,
    jsapi_ticket VARCHAR(512),
    ticket_expires_at DATETIME,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

DEPARTMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS departments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    parent_id INT,
    description TEXT,
    manager_user_id INT,
    level INT DEFAULT 1,
    path VARCHAR(500),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES departments(id) ON DELETE SET NULL
    -- manager_user_id 外键约束将在迁移中添加，避免与 users 表的循环依赖
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

EMPLOYEES_TABLE = """
CREATE TABLE IF NOT EXISTS employees (
    id INT AUTO_INCREMENT PRIMARY KEY,
    emp_no VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    created_by INT,
    class_name VARCHAR(255),
    position VARCHAR(255),
    birth_date DATE,
    certification_date DATE,
    marital_status VARCHAR(50),
    hometown VARCHAR(255),
    political_status VARCHAR(100),
    specialty VARCHAR(255),
    education VARCHAR(100),
    graduation_school VARCHAR(255),
    work_start_date DATE,
    entry_date DATE,
    department_id INT,
    solo_driving_date DATE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

PERFORMANCE_RECORDS_TABLE = """
CREATE TABLE IF NOT EXISTS performance_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    emp_no VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    employee_id INT DEFAULT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    score DECIMAL(10,2),
    grade VARCHAR(50),
    src_file VARCHAR(500),
    created_by INT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_perf (emp_no, year, month),
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

TRAINING_RECORDS_TABLE = """
CREATE TABLE IF NOT EXISTS training_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    emp_no VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    employee_id INT DEFAULT NULL,
    team_name VARCHAR(255),
    training_date DATE NOT NULL,
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
    FOREIGN KEY (project_id) REFERENCES training_projects(id) ON DELETE SET NULL,
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

SAFETY_INSPECTION_TABLE = """
CREATE TABLE IF NOT EXISTS safety_inspection_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    category VARCHAR(255) NOT NULL,
    inspection_date DATE NOT NULL,
    location VARCHAR(500),
    hazard_description TEXT,
    corrective_measures TEXT,
    deadline_date DATE,
    inspected_person VARCHAR(255),
    employee_id INT DEFAULT NULL,
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
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

GRADE_MAP_TABLE = """
CREATE TABLE IF NOT EXISTS grade_map (
    grade VARCHAR(50) NOT NULL PRIMARY KEY,
    value DECIMAL(10,2) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

QUARTER_OVERRIDES_TABLE = """
CREATE TABLE IF NOT EXISTS quarter_overrides (
    emp_no VARCHAR(100) NOT NULL,
    year INT NOT NULL,
    quarter INT NOT NULL,
    grade VARCHAR(50) NOT NULL,
    PRIMARY KEY (emp_no, year, quarter)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

QUARTER_GRADE_OPTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS quarter_grade_options (
    grade VARCHAR(50) NOT NULL PRIMARY KEY,
    display_order INT NOT NULL,
    is_default INT NOT NULL DEFAULT 0,
    color VARCHAR(50)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

STOPWORDS_TABLE = """
CREATE TABLE IF NOT EXISTS stopwords (
    id INT AUTO_INCREMENT PRIMARY KEY,
    word VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(100) DEFAULT 'custom',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

AI_PROVIDERS_TABLE = """
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
"""

AI_USAGE_LOGS_TABLE = """
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
"""

AI_ANALYSIS_HISTORY_TABLE = """
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
"""

TRAINING_PROJECTS_TABLE = """
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
"""

AI_ANALYSIS_CONFIG_TABLE = """
CREATE TABLE IF NOT EXISTS ai_analysis_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(50) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    default_instruction TEXT,
    current_instruction TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

AI_PROMPT_CONFIGS_TABLE = """
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

TRAINING_PROJECT_CATEGORIES_TABLE = """
CREATE TABLE IF NOT EXISTS training_project_categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    display_order INT DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

IMPORT_LOGS_TABLE = """
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
"""

ALGORITHM_PRESETS_TABLE = """
CREATE TABLE IF NOT EXISTS algorithm_presets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    preset_name VARCHAR(255) NOT NULL UNIQUE,
    preset_key VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    config_data TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

ALGORITHM_ACTIVE_CONFIG_TABLE = """
CREATE TABLE IF NOT EXISTS algorithm_active_config (
    id INT PRIMARY KEY DEFAULT 1,
    based_on_preset VARCHAR(100),
    is_customized INT DEFAULT 0,
    config_data TEXT NOT NULL,
    config_version INT NOT NULL DEFAULT 1,
    updated_by INT,
    updated_at DATETIME,
    FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL,
    CHECK (id = 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

ALGORITHM_CONFIG_LOGS_TABLE = """
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
    config_version INT DEFAULT NULL,
    FOREIGN KEY (changed_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

ASYNC_TASKS_TABLE = """
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

PPT_EXPORT_CACHE_TABLE = """
CREATE TABLE IF NOT EXISTS ppt_export_cache (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cache_key VARCHAR(128) NOT NULL UNIQUE,
    emp_no VARCHAR(100) NOT NULL,
    start_date VARCHAR(20),
    end_date VARCHAR(20),
    ai_summary TEXT NOT NULL,
    is_ai_generated TINYINT DEFAULT 0,
    tokens_used INT DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    INDEX idx_ppt_cache_key (cache_key),
    INDEX idx_ppt_cache_emp (emp_no),
    INDEX idx_ppt_cache_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

PPT_TEMPLATES_TABLE = """
CREATE TABLE IF NOT EXISTS ppt_templates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    template_name VARCHAR(255) NOT NULL,
    logo_image MEDIUMTEXT,
    end_page_background MEDIUMTEXT,
    primary_color VARCHAR(20) DEFAULT '#1A56DB',
    secondary_color VARCHAR(20) DEFAULT '#DC3545',
    title_color VARCHAR(20),
    footer_color VARCHAR(20),
    font_family VARCHAR(100),
    end_page_title VARCHAR(255),
    end_page_subtitle VARCHAR(255),
    is_default TINYINT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by INT,
    FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

# Recent Imports View
VIEW_RECENT_IMPORTS = """
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
"""

# List of all table creation statements in dependency order
ALL_TABLES = [
    SYSTEM_METADATA_TABLE,
    DEPARTMENTS_TABLE,  # 先创建 departments，因为 users 依赖它
    USERS_TABLE,
    DINGTALK_TOKEN_TABLE,
    EMPLOYEES_TABLE,
    TRAINING_PROJECT_CATEGORIES_TABLE, # Depends on nothing
    TRAINING_PROJECTS_TABLE, # Depends on categories
    TRAINING_RECORDS_TABLE, # Depends on projects
    PERFORMANCE_RECORDS_TABLE,
    SAFETY_INSPECTION_TABLE,
    GRADE_MAP_TABLE,
    QUARTER_OVERRIDES_TABLE,
    QUARTER_GRADE_OPTIONS_TABLE,
    STOPWORDS_TABLE,
    AI_PROVIDERS_TABLE,
    AI_USAGE_LOGS_TABLE,
    AI_ANALYSIS_HISTORY_TABLE,
    AI_ANALYSIS_CONFIG_TABLE,
    AI_PROMPT_CONFIGS_TABLE,
    IMPORT_LOGS_TABLE,
    ALGORITHM_PRESETS_TABLE,
    ALGORITHM_ACTIVE_CONFIG_TABLE,
    ALGORITHM_CONFIG_LOGS_TABLE,
    ASYNC_TASKS_TABLE,
    PPT_EXPORT_CACHE_TABLE,
    PPT_TEMPLATES_TABLE
]
