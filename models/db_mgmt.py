# -*- coding: utf-8 -*-
"""
Database Management Module
Handles initialization, version control, and migrations.
"""
from models.database import get_db, _create_indexes
from models.schema_defs import ALL_TABLES, VIEW_RECENT_IMPORTS

# Current Database Schema Version
# Increment this when making schema changes
CURRENT_DB_VERSION = 4

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
            
            # Update version
            self.cur.execute(
                "INSERT INTO system_metadata (key_name, value) VALUES ('db_version', %s) "
                "ON DUPLICATE KEY UPDATE value = %s",
                (str(CURRENT_DB_VERSION), str(CURRENT_DB_VERSION))
            )
            print(f"[+] Database upgraded to version {CURRENT_DB_VERSION}")

    def _run_migrations(self, start_ver, target_ver):
        """
        Executes specific migration logic based on version path.
        """
        # Migration from 0 -> 1 (Fresh Install or Pre-versioning state)
        if start_ver < 1:
            print("[-] Running Migration v1 (Baseline Schema)...")
            self._migration_v1_baseline()
            
        # Migration from 1 -> 2 (Current Updates)
        if start_ver < 2 and target_ver >= 2:
            print("[-] Running Migration v2 (Schema Updates)...")
            self._migration_v2_updates()

        # Migration from 2 -> 3 (PPT Export Cache)
        if start_ver < 3 and target_ver >= 3:
            print("[-] Running Migration v3 (PPT Export Cache)...")
            self._migration_v3_ppt_cache()

        # Migration from 3 -> 4 (Data Model Governance)
        if start_ver < 4 and target_ver >= 4:
            print("[-] Running Migration v4 (Data Model Governance)...")
            self._migration_v4_data_model()

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
        try:
            self.cur.execute(f"SHOW COLUMNS FROM {table_name} LIKE %s", (column_name,))
            if self.cur.fetchone() is None:
                print(f"    + Adding column {table_name}.{column_name}")
                self.cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
        except Exception as e:
            print(f"[!] Error ensuring column {column_name}: {e}")

    def _ensure_unique_index(self, table_name, index_name, columns):
        try:
            self.cur.execute(f"SHOW INDEX FROM {table_name} WHERE Key_name = %s", (index_name,))
            if self.cur.fetchone() is None:
                print(f"    + Creating unique index {index_name} on {table_name}")
                self.cur.execute(f"CREATE UNIQUE INDEX {index_name} ON {table_name}({columns})")
        except Exception as e:
            print(f"[!] Error ensuring index {index_name}: {e}")

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
        """幂等建表：若不存在则创建，完全安全可重复运行"""
        try:
            self.cur.execute(create_sql)
            print(f"    + Table {table_name} ensured")
        except Exception as e:
            print(f"[!] Error ensuring table {table_name}: {e}")

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

        # === 3. 日期字段结构化 ===
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

        for table, field in date_migrations:
            try:
                # 检查当前类型
                self.cur.execute("""
                    SELECT DATA_TYPE FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                    AND TABLE_NAME = %s AND COLUMN_NAME = %s
                """, (table, field))
                row = self.cur.fetchone()
                if row and row['DATA_TYPE'] == 'date':
                    continue  # 已是 DATE，跳过

                # 先清洗：标准化日期格式
                # 处理 yyyy年mm月dd日 → yyyy-mm-dd
                self.cur.execute(f"""
                    UPDATE {table}
                    SET {field} = NULL
                    WHERE {field} IS NOT NULL
                    AND {field} != ''
                    AND {field} NOT REGEXP '^[0-9]{{4}}-[0-9]{{1,2}}-[0-9]{{1,2}}$'
                    AND {field} NOT REGEXP '^[0-9]{{4}}/[0-9]{{1,2}}/[0-9]{{1,2}}$'
                """)
                nulled = self.cur.rowcount

                # 将 yyyy/mm/dd 格式统一为 yyyy-mm-dd
                self.cur.execute(f"""
                    UPDATE {table}
                    SET {field} = REPLACE({field}, '/', '-')
                    WHERE {field} LIKE '%%/%%'
                """)

                # 执行 ALTER TABLE
                not_null = ' NOT NULL' if field == 'training_date' or field == 'inspection_date' else ''
                self.cur.execute(f"ALTER TABLE {table} MODIFY COLUMN {field} DATE{not_null}")
                print(f"    + {table}.{field}: VARCHAR → DATE (cleared {nulled} unparseable)")
            except Exception as e:
                print(f"    [!] {table}.{field} migration failed: {e}")
