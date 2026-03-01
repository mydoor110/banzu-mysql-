# -*- coding: utf-8 -*-
"""
Database Management Module
Handles initialization, version control, and migrations.
"""
from models.database import get_db, _create_indexes
from models.schema_defs import ALL_TABLES, VIEW_RECENT_IMPORTS

# Current Database Schema Version
# Increment this when making schema changes
CURRENT_DB_VERSION = 5

class DBVersionManager:
    def __init__(self, cursor=None):
        self.conn = get_db()
        self.cur = cursor if cursor else self.conn.cursor()

    def initialize(self):
        """
        Main entry point for DB initialization.
        Checks version, creates tables, runs migrations.

        注意: DDL 语句(CREATE/ALTER TABLE)在 MySQL 中会隐式提交，无法回滚。
        但版本信息更新等 DML 语句可以通过调用者的 commit/rollback 控制。
        """
        print("[-] Checking database status...")

        try:
            # 1. First, ensure base tables exist (idempotent)
            print("[-] Step 1/4: Ensuring base tables...")
            self._ensure_base_tables()
            print("[+] Base tables ready")

            # 2. Check and handle versioning
            print("[-] Step 2/4: Checking version and migrations...")
            self._check_and_migrate()
            print("[+] Version check complete")

            # 3. Create/Update Views
            print("[-] Step 3/4: Updating views...")
            self._update_views()
            print("[+] Views updated")

            # 4. Ensure Indexes
            print("[-] Step 4/4: Ensuring indexes...")
            self._ensure_indexes()
            print("[+] Indexes ready")

            print("[+] Database initialization complete successfully.")

        except Exception as e:
            print(f"\n[!] Database initialization FAILED at step: {e}")
            print(f"[!] Error details: {str(e)}")
            print("[!] Rolling back transaction...")
            self.conn.rollback()
            raise  # 重新抛出异常，让调用者知道初始化失败

    def _ensure_base_tables(self):
        """Runs the CREATE TABLE IF NOT EXISTS statements"""
        # Disable foreign keys temporarily to avoid issues during table creation
        self.cur.execute("SET FOREIGN_KEY_CHECKS = 0")

        try:
            for table_sql in ALL_TABLES:
                try:
                    self.cur.execute(table_sql)
                except Exception as e:
                    print(f"[!] Error ensuring table: {e}")
                    print(f"[!] SQL: {table_sql[:100]}...")
                    raise  # 抛出异常，表创建失败是致命错误
        finally:
            # 确保无论如何都恢复外键检查
            self.cur.execute("SET FOREIGN_KEY_CHECKS = 1")

    def _update_views(self):
        """Re-creates views"""
        try:
            self.cur.execute("DROP VIEW IF EXISTS v_recent_imports")
            self.cur.execute(VIEW_RECENT_IMPORTS)
            print("    + View v_recent_imports created/updated")
        except Exception as e:
            print(f"[!] Warning: Could not update views: {e}")
            # 视图创建失败不是致命错误，记录警告但继续

    def _ensure_indexes(self):
        """Ensure performance indexes"""
        _create_indexes(self.cur)

    def _check_and_migrate(self):
        """
        Checks current DB version and applies migrations if needed.
        采用逐版本写号策略：每完成一个版本的迁移后立即写入版本号，
        确保迁移失败时版本号停在最后成功的位置。
        """
        # Check system_metadata for version
        db_version = 0
        try:
            self.cur.execute("SELECT value FROM system_metadata WHERE key_name = 'db_version'")
            row = self.cur.fetchone()
            if row:
                db_version = int(row['value'])
            else:
                # Table exists but no version row? Possibly v1 or fresh v0
                # If users table exists, it's likely v1
                self.cur.execute("SHOW TABLES LIKE 'users'")
                if self.cur.fetchone():
                    db_version = 1
                    # Initialize version record
                    self.cur.execute(
                        "INSERT INTO system_metadata (key_name, value) VALUES ('db_version', '1')"
                    )
        except Exception as e:
            # system_metadata 表应该在 _ensure_base_tables 中已创建
            # 如果这里出错，说明有严重问题
            print(f"[!] Critical Error in version check: {e}")
            raise  # 抛出异常而不是静默失败

        print(f"[*] Current DB Version: {db_version}, Target Version: {CURRENT_DB_VERSION}")

        if db_version < CURRENT_DB_VERSION:
            self._run_migrations(db_version, CURRENT_DB_VERSION)

    def _update_version(self, version):
        """将数据库版本号更新到指定版本"""
        self.cur.execute(
            "INSERT INTO system_metadata (key_name, value) VALUES ('db_version', %s) "
            "ON DUPLICATE KEY UPDATE value = %s",
            (str(version), str(version))
        )
        print(f"[+] Database version updated to {version}")

    def _run_migrations(self, start_ver, target_ver):
        """
        Executes specific migration logic based on version path.
        采用逐版本写号：每完成一个版本迁移后立即写入该版本号。
        如果某版本迁移失败，异常上抛，版本号停在最后成功的位置。
        """
        # Migration from 0 -> 1 (Fresh Install or Pre-versioning state)
        if start_ver < 1:
            print("[-] Running Migration v1 (Baseline Schema)...")
            self._migration_v1_baseline()
            self._update_version(1)
            
        # Migration from 1 -> 2 (Current Updates)
        if start_ver < 2 and target_ver >= 2:
            print("[-] Running Migration v2 (Schema Updates)...")
            self._migration_v2_updates()
            self._update_version(2)

        # Migration from 2 -> 3 (PPT Export Cache)
        if start_ver < 3 and target_ver >= 3:
            print("[-] Running Migration v3 (PPT Export Cache)...")
            self._migration_v3_ppt_cache()
            self._update_version(3)

        # Migration from 3 -> 4 (Data Model Governance)
        if start_ver < 4 and target_ver >= 4:
            print("[-] Running Migration v4 (Data Model Governance)...")
            self._migration_v4_data_model()
            self._update_version(4)

        # Migration from 4 -> 5 (Config Version Governance)
        if start_ver < 5 and target_ver >= 5:
            print("[-] Running Migration v5 (Config Version Governance)...")
            self._migration_v5_config_version()
            self._update_version(5)

    def _migration_v1_baseline(self):
        """
        Baseline adjustments for v1 schema.
        添加 departments.manager_user_id 的外键约束（避免初始创建时的循环依赖）
        """
        print("    + Adding foreign key constraint for departments.manager_user_id")
        self._ensure_foreign_key(
            table_name="departments",
            constraint_name="fk_departments_manager",
            foreign_key="manager_user_id",
            references="users(id)",
            on_delete="SET NULL"
        )

    def _migration_v2_updates(self):
        """
        Apply recent schema updates
        """
        # Users table updates (DingTalk)
        self._ensure_column("users", "dingtalk_userid", "VARCHAR(128)")
        self._ensure_column("users", "dingtalk_unionid", "VARCHAR(128)")
        self._ensure_column("users", "display_name", "VARCHAR(255)")
        self._ensure_unique_index("users", "uk_dingtalk_userid", "dingtalk_userid")
        
        # DingTalk Token Cache updates
        self._ensure_column("dingtalk_token_cache", "jsapi_ticket", "VARCHAR(512)")
        self._ensure_column("dingtalk_token_cache", "ticket_expires_at", "DATETIME")

    # Helper methods for migrations
    def _ensure_column(self, table_name, column_name, column_def):
        """确保列存在，失败时抛出异常（致命错误）"""
        try:
            self.cur.execute(f"SHOW COLUMNS FROM {table_name} LIKE %s", (column_name,))
            if self.cur.fetchone() is None:
                print(f"    + Adding column {table_name}.{column_name}")
                self.cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
        except Exception as e:
            print(f"[!] FATAL: Failed to ensure column {table_name}.{column_name}: {e}")
            raise  # 列新增失败是致命错误，不允许继续升级版本

    def _ensure_unique_index(self, table_name, index_name, columns):
        """确保唯一索引存在，失败时抛出异常（致命错误）"""
        try:
            self.cur.execute(f"SHOW INDEX FROM {table_name} WHERE Key_name = %s", (index_name,))
            if self.cur.fetchone() is None:
                print(f"    + Creating unique index {index_name} on {table_name}")
                self.cur.execute(f"CREATE UNIQUE INDEX {index_name} ON {table_name}({columns})")
        except Exception as e:
            print(f"[!] FATAL: Failed to ensure index {index_name} on {table_name}: {e}")
            raise  # 索引创建失败是致命错误，不允许继续升级版本

    def _ensure_foreign_key(self, table_name, constraint_name, foreign_key, references, on_delete="CASCADE"):
        """确保外键约束存在"""
        try:
            # 检查外键约束是否已存在
            self.cur.execute(f"""
                SELECT CONSTRAINT_NAME
                FROM information_schema.TABLE_CONSTRAINTS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %s
                  AND CONSTRAINT_NAME = %s
                  AND CONSTRAINT_TYPE = 'FOREIGN KEY'
            """, (table_name, constraint_name))

            if self.cur.fetchone() is None:
                print(f"    + Adding foreign key {constraint_name} on {table_name}")
                self.cur.execute(f"""
                    ALTER TABLE {table_name}
                    ADD CONSTRAINT {constraint_name}
                    FOREIGN KEY ({foreign_key})
                    REFERENCES {references}
                    ON DELETE {on_delete}
                """)
            else:
                print(f"    - Foreign key {constraint_name} already exists")
        except Exception as e:
            print(f"[!] Error ensuring foreign key {constraint_name}: {e}")
            # 外键约束失败不是致命错误，记录但继续

    def _ensure_table(self, table_name, create_sql):
        """幂等建表：若不存在则创建，失败时抛出异常"""
        try:
            self.cur.execute(create_sql)
            print(f"    + Table {table_name} ensured")
        except Exception as e:
            print(f"[!] FATAL: Failed to ensure table {table_name}: {e}")
            raise  # 建表失败是致命错误

    def _migration_v3_ppt_cache(self):
        """Add PPT export AI summary cache table"""
        from models.schema_defs import PPT_EXPORT_CACHE_TABLE
        self._ensure_table("ppt_export_cache", PPT_EXPORT_CACHE_TABLE)
        # 同时添加performance index（若表已存在也安全）
        try:
            self.cur.execute(
                "SHOW INDEX FROM ppt_export_cache WHERE Key_name = 'idx_ppt_cache_expires'"
            )
            if not self.cur.fetchone():
                self.cur.execute(
                    "ALTER TABLE ppt_export_cache ADD INDEX idx_ppt_cache_expires (expires_at)"
                )
        except Exception:
            pass  # 索引已存在或建表包含则忽略

    def _migration_v4_data_model(self):
        """数据模型治理：employee_id 外键 + 日期字段结构化"""
        # === 1. 为业务表添加 employee_id 列 ===
        for table in ['performance_records', 'training_records', 'safety_inspection_records']:
            self._ensure_column(table, 'employee_id', 'INT DEFAULT NULL')
            self._ensure_foreign_key(
                table_name=table,
                constraint_name=f'fk_{table}_employee_id',
                foreign_key='employee_id',
                references='employees(id)',
                on_delete='SET NULL'
            )

        # === 2. 回填 employee_id（基于 emp_no / name 匹配）===
        print("    + Backfilling employee_id...")
        try:
            # performance_records / training_records 通过 emp_no 匹配
            for table in ['performance_records', 'training_records']:
                self.cur.execute(f"""
                    UPDATE {table} t
                    INNER JOIN employees e ON t.emp_no = e.emp_no
                    SET t.employee_id = e.id
                    WHERE t.employee_id IS NULL
                """)
                print(f"      {table}: {self.cur.rowcount} rows backfilled")

            # safety_inspection_records 通过 inspected_person (name) 匹配
            self.cur.execute("""
                UPDATE safety_inspection_records t
                INNER JOIN employees e ON t.inspected_person = e.name
                SET t.employee_id = e.id
                WHERE t.employee_id IS NULL
            """)
            print(f"      safety_inspection_records: {self.cur.rowcount} rows backfilled")
        except Exception as e:
            print(f"    [!] Backfill warning: {e}")

        # === 3. 日期字段结构化（Python 端逐行解析，避免 SQL 一刀切丢数据） ===
        date_migrations = [
            ('employees', 'birth_date'),
            ('employees', 'certification_date'),
            ('employees', 'work_start_date'),
            ('employees', 'entry_date'),
            ('employees', 'solo_driving_date'),
            ('training_records', 'training_date'),
            ('safety_inspection_records', 'inspection_date'),
            ('safety_inspection_records', 'deadline_date'),
        ]

        import re

        def _try_parse_date(val):
            """将各种日期字符串标准化为 YYYY-MM-DD（与 scripts/migrate_date_fields.py 一致）"""
            if not val:
                return None
            val = str(val).strip()
            if not val:
                return None
            # 已是标准格式
            if re.match(r'^\d{4}-\d{2}-\d{2}$', val):
                return val
            # yyyy-m-d / yyyy/m/d / yyyy.m.d / yyyy年m月d日
            m = re.match(r'^(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})[日]?$', val)
            if m:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if 1900 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31:
                    return f"{y:04d}-{mo:02d}-{d:02d}"
            # yyyy年m月 / yyyy-m / yyyy/m（缺日，默认1号）
            m = re.match(r'^(\d{4})[-/.年](\d{1,2})[月]?$', val)
            if m:
                y, mo = int(m.group(1)), int(m.group(2))
                if 1900 <= y <= 2100 and 1 <= mo <= 12:
                    return f"{y:04d}-{mo:02d}-01"
            return None

        for table, field in date_migrations:
            try:
                # 检查当前类型，已是 DATE 则跳过
                self.cur.execute("""
                    SELECT DATA_TYPE FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                    AND TABLE_NAME = %s AND COLUMN_NAME = %s
                """, (table, field))
                row = self.cur.fetchone()
                if row and row['DATA_TYPE'] == 'date':
                    continue  # 已是 DATE，跳过

                # Python 端逐行解析，而非 SQL 一刀切
                self.cur.execute(f"""
                    SELECT id, {field} as val FROM {table}
                    WHERE {field} IS NOT NULL AND {field} != ''
                """)
                rows = self.cur.fetchall()

                cleaned = 0
                nulled = 0
                for r in rows:
                    parsed = _try_parse_date(r['val'])
                    if parsed:
                        if parsed != str(r['val']).strip():
                            self.cur.execute(
                                f"UPDATE {table} SET {field} = %s WHERE id = %s",
                                (parsed, r['id'])
                            )
                            cleaned += 1
                    else:
                        self.cur.execute(
                            f"UPDATE {table} SET {field} = NULL WHERE id = %s",
                            (r['id'],)
                        )
                        nulled += 1

                # 执行 ALTER TABLE
                not_null = ' NOT NULL' if field in ('training_date', 'inspection_date') else ''
                self.cur.execute(f"ALTER TABLE {table} MODIFY COLUMN {field} DATE{not_null}")
                print(f"    + {table}.{field}: VARCHAR → DATE (标准化 {cleaned}, 置NULL {nulled})")
            except Exception as e:
                print(f"    [!] {table}.{field} migration failed: {e}")

    def _migration_v5_config_version(self):
        """P1.4 配置版本治理：algorithm_active_config / algorithm_config_logs 新增 config_version"""
        self._ensure_column(
            'algorithm_active_config', 'config_version', 'INT NOT NULL DEFAULT 1'
        )
        self._ensure_column(
            'algorithm_config_logs', 'config_version', 'INT DEFAULT NULL'
        )
        # 初始化版本号（基于现有日志数量推算）
        try:
            self.cur.execute("""
                UPDATE algorithm_active_config
                SET config_version = COALESCE(
                    (SELECT COUNT(*) FROM algorithm_config_logs), 1
                )
                WHERE id = 1 AND config_version = 1
            """)
            print(f"    + config_version 初始化完成 (affected={self.cur.rowcount})")
        except Exception as e:
            print(f"    [!] config_version 初始化警告: {e}")

