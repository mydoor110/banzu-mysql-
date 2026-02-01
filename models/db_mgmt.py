# -*- coding: utf-8 -*-
"""
Database Management Module
Handles initialization, version control, and migrations.
"""
from models.database import get_db, _create_indexes
from models.schema_defs import ALL_TABLES, VIEW_RECENT_IMPORTS

# Current Database Schema Version
# Increment this when making schema changes
CURRENT_DB_VERSION = 2

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
