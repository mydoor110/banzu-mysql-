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
        """
        print("[-] Checking database status...")
        
        # 1. First, ensure base tables exist (idempotent)
        self._ensure_base_tables()
        
        # 2. Check and handle versioning
        self._check_and_migrate()
        
        # 3. Create/Update Views
        self._update_views()
        
        # 4. Ensure Indexes
        self._ensure_indexes()
        
        print("[+] Database initialization complete.")

    def _ensure_base_tables(self):
        """Runs the CREATE TABLE IF NOT EXISTS statements"""
        # Disable foreign keys temporarily to avoid circular dependency issues during creation
        self.cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        for table_sql in ALL_TABLES:
            try:
                self.cur.execute(table_sql)
            except Exception as e:
                print(f"[!] Error ensuring table: {e}")
                # We continue because some errors might be benign in specific contexts, 
                # though ideally we should log them.
                
        self.cur.execute("SET FOREIGN_KEY_CHECKS = 1")

    def _update_views(self):
        """Re-creates views"""
        try:
            self.cur.execute("DROP VIEW IF EXISTS v_recent_imports")
            self.cur.execute(VIEW_RECENT_IMPORTS)
        except Exception as e:
            print(f"[!] Error updating views: {e}")

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
            # Maybe system_metadata doesn't exist yet?
            # It should have been created in _ensure_base_tables
            print(f"[!] Error creating version check: {e}")
            return

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
        Baseline adjustments usually handled by _ensure_base_tables,
        but we put specific column checks here just in case.
        """
        pass

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
