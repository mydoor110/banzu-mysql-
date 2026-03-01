#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database backup and restore module
Comprehensive backup solution with automated scheduling
MySQL backend support
"""
import os
import shutil
import subprocess
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
import json
import logging

from config.settings import DatabaseConfig


# ========== Configuration ==========

class BackupConfig:
    """Backup configuration settings"""

    # Backup directory
    BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backups')

    # Upload directory (if exists)
    UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')

    # Config directory
    CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config')

    # Retention settings
    MAX_BACKUPS = 30  # Keep last 30 backups
    MAX_BACKUP_AGE_DAYS = 90  # Delete backups older than 90 days

    # Auto backup settings
    AUTO_BACKUP_ENABLED = True
    AUTO_BACKUP_HOUR = 2  # 2 AM daily backup

    @classmethod
    def ensure_backup_dir(cls):
        """Ensure backup directory exists"""
        os.makedirs(cls.BACKUP_DIR, exist_ok=True)

        # Create .gitignore to exclude backups from git
        gitignore_path = os.path.join(cls.BACKUP_DIR, '.gitignore')
        if not os.path.exists(gitignore_path):
            with open(gitignore_path, 'w', encoding='utf-8') as f:
                f.write('# Ignore all backup files\n')
                f.write('*.zip\n')
                f.write('*.sql\n')
                f.write('\n')
                f.write('# Keep the directory\n')
                f.write('!.gitignore\n')

                f.write('!.gitignore\n')


# ========== Task Management ==========

import threading
import uuid
import time
from enum import Enum

# 复用统一任务管理器
from services.task_manager import TaskManager, AsyncTask, TaskStatus


class BackupTask(AsyncTask):
    """备份任务（AsyncTask 别名，保持向后兼容）"""
    pass


class BackupTaskManager:
    """备份任务管理器（代理到统一 TaskManager）

    保持原有 create_task / get_task API 不变，
    内部委托给 TaskManager.submit / TaskManager.get_task。
    """

    @classmethod
    def create_task(cls, task_type, task_description, target_func, *args, **kwargs):
        """创建并启动后台任务"""
        task = TaskManager.submit(
            task_type=task_type,
            description=task_description,
            target_func=target_func,
            *args,
            **kwargs
        )
        return task

    @classmethod
    def get_task(cls, task_id):
        """查询任务状态"""
        return TaskManager.get_task(task_id)


# ========== Backup Manager ==========

class BackupManager:
    """Database backup and restore manager"""

    def __init__(self):
        self.logger = logging.getLogger('app')
        BackupConfig.ensure_backup_dir()

    def create_backup(self, backup_type='full', description='', task_tracker=None):
        """
        Create a database backup
        
        Args:
            backup_type: 'full' or 'incremental'
            description: Optional backup description
            task_tracker: Optional BackupTask object for progress reporting
        
        Returns:
            dict: Backup information (path, size, timestamp)
        """
        try:
            if task_tracker:
                task_tracker.progress = 5
                task_tracker.message = "Initializing backup..."
                
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"backup_{backup_type}_{timestamp}.zip"
            backup_path = os.path.join(BackupConfig.BACKUP_DIR, backup_name)

            # Create backup metadata
            metadata = {
                'timestamp': datetime.now().isoformat(),
                'type': backup_type,
                'description': description,
                'files': []
            }

            # Create ZIP archive
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as backup_zip:
                # Backup database
                if task_tracker:
                    task_tracker.progress = 10
                    task_tracker.message = "Backing up database..."
                    
                db_backup = self._backup_database(timestamp)
                if db_backup:
                    backup_zip.write(db_backup, os.path.basename(db_backup))
                    metadata['files'].append({
                        'name': os.path.basename(db_backup),
                        'type': 'database',
                        'size': os.path.getsize(db_backup)
                    })
                    # Clean up temp database backup
                    os.remove(db_backup)

                # Backup configuration files
                if task_tracker:
                    task_tracker.progress = 50
                    task_tracker.message = "Backing up configuration..."
                    
                if os.path.exists(BackupConfig.CONFIG_DIR):
                    for config_file in Path(BackupConfig.CONFIG_DIR).rglob('*.py'):
                        rel_path = os.path.relpath(config_file, os.path.dirname(BackupConfig.CONFIG_DIR))
                        backup_zip.write(config_file, f"config/{rel_path}")
                        metadata['files'].append({
                            'name': f"config/{rel_path}",
                            'type': 'config',
                            'size': os.path.getsize(config_file)
                        })

                # Backup uploads directory (if exists and not too large)
                if task_tracker:
                    task_tracker.progress = 70
                    task_tracker.message = "Backing up uploads..."
                    
                if os.path.exists(BackupConfig.UPLOAD_DIR):
                    upload_size = sum(f.stat().st_size for f in Path(BackupConfig.UPLOAD_DIR).rglob('*') if f.is_file())
                    # Only backup uploads if total size < 100MB
                    if upload_size < 100 * 1024 * 1024:
                        for upload_file in Path(BackupConfig.UPLOAD_DIR).rglob('*'):
                            if upload_file.is_file():
                                rel_path = os.path.relpath(upload_file, os.path.dirname(BackupConfig.UPLOAD_DIR))
                                backup_zip.write(upload_file, f"uploads/{rel_path}")
                                metadata['files'].append({
                                    'name': f"uploads/{rel_path}",
                                    'type': 'upload',
                                    'size': os.path.getsize(upload_file)
                                })

                # Add metadata file
                if task_tracker:
                    task_tracker.progress = 90
                    task_tracker.message = "Finalizing backup..."
                    
                metadata_json = json.dumps(metadata, ensure_ascii=False, indent=2)
                backup_zip.writestr('backup_metadata.json', metadata_json)

            # Get final backup info
            backup_info = {
                'name': backup_name,
                'path': backup_path,
                'size': os.path.getsize(backup_path),
                'timestamp': metadata['timestamp'],
                'type': backup_type,
                'description': description,
                'file_count': len(metadata['files'])
            }

            self.logger.info(f"Backup created successfully: {backup_name} ({self._format_size(backup_info['size'])})")

            # Clean old backups
            self._cleanup_old_backups()

            return backup_info

        except Exception as e:
            self.logger.error(f"Failed to create backup: {e}", exc_info=True)
            raise

    def _backup_database(self, timestamp):
        """
        Create database backup using mysqldump (或纯 Python 后备方案)

        Args:
            timestamp: Backup timestamp string

        Returns:
            str: Path to backup SQL file
        """
        backup_sql_path = os.path.join(BackupConfig.BACKUP_DIR, f"db_backup_{timestamp}.sql")

        # 优先尝试使用 mysqldump
        if shutil.which('mysqldump'):
            try:
                return self._backup_database_mysqldump(backup_sql_path)
            except Exception as e:
                self.logger.warning(f"mysqldump backup failed: {e}, falling back to Python backup")

        # 降级到纯 Python 备份方案
        self.logger.info("Using pure Python backup (mysqldump not available)")
        return self._backup_database_python(backup_sql_path)

    def _backup_database_mysqldump(self, backup_sql_path):
        """
        使用 mysqldump 创建备份（首选方案）

        Args:
            backup_sql_path: 备份文件路径

        Returns:
            str: 备份文件路径
        """
        try:
            # Prepare environment for mysqldump (pass password safely)
            env = os.environ.copy()
            env['MYSQL_PWD'] = DatabaseConfig.MYSQL_PASSWORD

            # Build mysqldump command
            cmd = [
                'mysqldump',
                f'--host={DatabaseConfig.MYSQL_HOST}',
                f'--port={str(DatabaseConfig.MYSQL_PORT)}',
                f'--user={DatabaseConfig.MYSQL_USER}',
                # Password passed via env
                '--single-transaction',
                '--routines',
                '--triggers',
                '--events',
                '--default-character-set=utf8mb4',
                DatabaseConfig.MYSQL_DATABASE
            ]

            # Execute mysqldump
            with open(backup_sql_path, 'w', encoding='utf-8') as f:
                result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True, env=env)

            if result.returncode != 0:
                self.logger.error(f"mysqldump failed: {result.stderr}")
                if os.path.exists(backup_sql_path):
                    os.remove(backup_sql_path)
                raise RuntimeError(f"mysqldump failed: {result.stderr}")

            self.logger.info(f"Database backed up (mysqldump): {backup_sql_path}")
            return backup_sql_path

        except Exception as e:
            self.logger.error(f"mysqldump backup failed: {e}")
            raise

    def _backup_database_python(self, backup_sql_path):
        """
        使用纯 Python 创建备份（后备方案）

        注意: 此方案不包括存储过程、触发器、事件等，仅备份表结构和数据

        Args:
            backup_sql_path: 备份文件路径

        Returns:
            str: 备份文件路径
        """
        try:
            from models.database import get_db

            conn = get_db()
            cur = conn.cursor()

            with open(backup_sql_path, 'w', encoding='utf-8') as f:
                # 写入备份头部
                f.write("-- MySQL Database Backup (Pure Python)\n")
                f.write(f"-- Database: {DatabaseConfig.MYSQL_DATABASE}\n")
                f.write(f"-- Backup Time: {datetime.now().isoformat()}\n")
                f.write("-- Generated by: Pure Python Backup Module\n")
                f.write("-- Note: This backup does not include routines, triggers, or events\n\n")
                f.write("SET FOREIGN_KEY_CHECKS=0;\n\n")

                # 获取所有表
                cur.execute("SHOW TABLES")
                tables = [row[f'Tables_in_{DatabaseConfig.MYSQL_DATABASE}'] for row in cur.fetchall()]

                self.logger.info(f"Backing up {len(tables)} tables using Python...")

                for table_name in tables:
                    # 跳过视图
                    cur.execute(f"SHOW FULL TABLES WHERE Tables_in_{DatabaseConfig.MYSQL_DATABASE} = '{table_name}' AND Table_type = 'BASE TABLE'")
                    if not cur.fetchone():
                        continue

                    f.write(f"\n-- Table: {table_name}\n")

                    # 导出表结构
                    cur.execute(f"SHOW CREATE TABLE `{table_name}`")
                    create_table = cur.fetchone()
                    if create_table:
                        f.write(f"DROP TABLE IF EXISTS `{table_name}`;\n")
                        f.write(create_table['Create Table'] + ";\n\n")

                    # 导出表数据
                    cur.execute(f"SELECT * FROM `{table_name}`")
                    rows = cur.fetchall()

                    if rows:
                        # 获取列名
                        columns = list(rows[0].keys())
                        columns_str = ', '.join([f'`{col}`' for col in columns])

                        f.write(f"-- Data for table {table_name}\n")
                        f.write(f"INSERT INTO `{table_name}` ({columns_str}) VALUES\n")

                        for i, row in enumerate(rows):
                            values = []
                            for col in columns:
                                val = row[col]
                                if val is None:
                                    values.append('NULL')
                                elif isinstance(val, (int, float)):
                                    values.append(str(val))
                                elif isinstance(val, datetime):
                                    values.append(f"'{val.strftime('%Y-%m-%d %H:%M:%S')}'")
                                else:
                                    # 转义字符串
                                    escaped = str(val).replace('\\', '\\\\').replace("'", "\\'")
                                    values.append(f"'{escaped}'")

                            values_str = ', '.join(values)
                            if i < len(rows) - 1:
                                f.write(f"  ({values_str}),\n")
                            else:
                                f.write(f"  ({values_str});\n\n")

                # 恢复外键检查
                f.write("\nSET FOREIGN_KEY_CHECKS=1;\n")

            self.logger.info(f"Database backed up (Python): {backup_sql_path}")
            return backup_sql_path

        except Exception as e:
            self.logger.error(f"Python backup failed: {e}", exc_info=True)
            if os.path.exists(backup_sql_path):
                os.remove(backup_sql_path)
            return None

    def list_backups(self):
        """
        List all available backups

        Returns:
            list: List of backup information dictionaries
        """
        backups = []

        try:
            if not os.path.exists(BackupConfig.BACKUP_DIR):
                return backups

            for backup_file in sorted(Path(BackupConfig.BACKUP_DIR).glob('backup_*.zip'), reverse=True):
                backup_info = self._get_backup_info(backup_file)
                if backup_info:
                    backups.append(backup_info)

            return backups

        except Exception as e:
            self.logger.error(f"Failed to list backups: {e}", exc_info=True)
            return []

    def _get_backup_info(self, backup_path):
        """
        Extract backup information from backup file

        Args:
            backup_path: Path to backup ZIP file

        Returns:
            dict: Backup information
        """
        try:
            stat_info = os.stat(backup_path)

            # Try to read metadata from ZIP
            metadata = {}
            try:
                with zipfile.ZipFile(backup_path, 'r') as backup_zip:
                    if 'backup_metadata.json' in backup_zip.namelist():
                        metadata_content = backup_zip.read('backup_metadata.json').decode('utf-8')
                        metadata = json.loads(metadata_content)
            except Exception:
                pass

            return {
                'name': os.path.basename(backup_path),
                'path': str(backup_path),
                'size': stat_info.st_size,
                'size_formatted': self._format_size(stat_info.st_size),
                'created': datetime.fromtimestamp(stat_info.st_ctime).isoformat(),
                'created_formatted': datetime.fromtimestamp(stat_info.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                'type': metadata.get('type', 'unknown'),
                'description': metadata.get('description', ''),
                'file_count': len(metadata.get('files', []))
            }

        except Exception as e:
            self.logger.error(f"Failed to get backup info for {backup_path}: {e}")
            return None

    def restore_backup(self, backup_name, restore_database=True, restore_config=True, restore_uploads=True, task_tracker=None):
        """
        Restore from backup
        
        Args:
            backup_name: Name of backup file to restore
            restore_database: Whether to restore database
            restore_config: Whether to restore config files
            restore_uploads: Whether to restore upload files
            task_tracker: Optional BackupTask object for progress reporting
        
        Returns:
            dict: Restore result information
        """
        try:
            if task_tracker:
                task_tracker.progress = 5
                task_tracker.message = "Initializing restore..."
                
            backup_path = os.path.join(BackupConfig.BACKUP_DIR, backup_name)

            if not os.path.exists(backup_path):
                raise FileNotFoundError(f"Backup not found: {backup_name}")

            restore_info = {
                'timestamp': datetime.now().isoformat(),
                'backup_name': backup_name,
                'restored_files': []
            }

            # Create a safety backup before restore
            if task_tracker:
                task_tracker.message = "Creating safety backup..."
                
            safety_backup = self.create_backup('full', 'Pre-restore safety backup')
            restore_info['safety_backup'] = safety_backup['name']

            with zipfile.ZipFile(backup_path, 'r') as backup_zip:
                base_dir = Path(BackupConfig.BACKUP_DIR).resolve()

                def safe_extract(member):
                    target_path = (base_dir / member).resolve()
                    if not str(target_path).startswith(str(base_dir) + os.sep):
                        raise ValueError(f"Unsafe path in backup: {member}")
                    backup_zip.extract(member, base_dir)
                    return str(target_path)

                # Restore database
                if restore_database:
                    if task_tracker:
                        task_tracker.progress = 20
                        task_tracker.message = "Restoring database..."
                        
                    sql_files = [f for f in backup_zip.namelist() if f.endswith('.sql')]
                    for sql_file in sql_files:
                        extracted_path = safe_extract(sql_file)

                        # Restore database using mysql command
                        success = self._restore_database(extracted_path)
                        if success:
                            restore_info['restored_files'].append({
                                'name': sql_file,
                                'type': 'database',
                                'target': 'MySQL database'
                            })
                            self.logger.info(f"Database restored from: {sql_file}")
                        
                        # Clean up extracted SQL file
                        os.remove(extracted_path)

                # Restore config files
                if restore_config:
                    if task_tracker:
                        task_tracker.progress = 50
                        task_tracker.message = "Restoring configuration..."
                        
                    config_files = [f for f in backup_zip.namelist() if f.startswith('config/')]
                    for config_file in config_files:
                        extracted_path = safe_extract(config_file)

                        target_path = os.path.join(os.path.dirname(BackupConfig.CONFIG_DIR), config_file)
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)

                        if os.path.exists(target_path):
                            os.remove(target_path)
                        shutil.move(extracted_path, target_path)

                        restore_info['restored_files'].append({
                            'name': config_file,
                            'type': 'config',
                            'target': target_path
                        })

                # Restore uploads
                if restore_uploads:
                    if task_tracker:
                        task_tracker.progress = 70
                        task_tracker.message = "Restoring uploads..."
                    
                    upload_files = [f for f in backup_zip.namelist() if f.startswith('uploads/')]
                    for upload_file in upload_files:
                        extracted_path = safe_extract(upload_file)

                        target_path = os.path.join(os.path.dirname(BackupConfig.UPLOAD_DIR), upload_file)
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)

                        shutil.move(extracted_path, target_path)

                        restore_info['restored_files'].append({
                            'name': upload_file,
                            'type': 'upload',
                            'target': target_path
                        })

            if task_tracker:
                task_tracker.progress = 95
                task_tracker.message = "Finalizing restore..."
                
            self.logger.info(f"Restore completed: {len(restore_info['restored_files'])} files restored")

            return restore_info

        except Exception as e:
            self.logger.error(f"Restore failed: {e}", exc_info=True)
            raise

    def _restore_database(self, sql_file_path):
        """
        Restore database from SQL dump file (使用 mysql 命令或纯 Python)

        Args:
            sql_file_path: Path to SQL dump file

        Returns:
            bool: True if restore successful
        """
        # 优先尝试使用 mysql 命令
        if shutil.which('mysql'):
            try:
                return self._restore_database_mysql(sql_file_path)
            except Exception as e:
                self.logger.warning(f"mysql restore failed: {e}, falling back to Python restore")

        # 降级到纯 Python 恢复方案
        self.logger.info("Using pure Python restore (mysql command not available)")
        return self._restore_database_python(sql_file_path)

    def _restore_database_mysql(self, sql_file_path):
        """
        使用 mysql 命令恢复数据库（首选方案）

        Args:
            sql_file_path: SQL 文件路径

        Returns:
            bool: 恢复是否成功
        """
        try:
            # Prepare environment for mysql (pass password safely)
            env = os.environ.copy()
            env['MYSQL_PWD'] = DatabaseConfig.MYSQL_PASSWORD

            # Build mysql command
            cmd = [
                'mysql',
                f'--host={DatabaseConfig.MYSQL_HOST}',
                f'--port={str(DatabaseConfig.MYSQL_PORT)}',
                f'--user={DatabaseConfig.MYSQL_USER}',
                # Password passed via env
                '--default-character-set=utf8mb4',
                DatabaseConfig.MYSQL_DATABASE
            ]

            # Execute mysql to restore
            with open(sql_file_path, 'r', encoding='utf-8') as f:
                result = subprocess.run(cmd, stdin=f, stderr=subprocess.PIPE, text=True, env=env)

            if result.returncode != 0:
                self.logger.error(f"mysql restore failed: {result.stderr}")
                raise RuntimeError(f"mysql restore failed: {result.stderr}")

            self.logger.info(f"Database restored (mysql): {sql_file_path}")
            return True

        except Exception as e:
            self.logger.error(f"mysql restore failed: {e}")
            raise

    def _restore_database_python(self, sql_file_path):
        """
        使用纯 Python 恢复数据库（后备方案）

        Args:
            sql_file_path: SQL 文件路径

        Returns:
            bool: 恢复是否成功
        """
        try:
            from models.database import get_db

            conn = get_db()
            cur = conn.cursor()

            self.logger.info("Restoring database using Python...")

            # 读取 SQL 文件并执行
            with open(sql_file_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()

            # 分割 SQL 语句（简单分割，不处理复杂情况）
            statements = []
            current_statement = []

            for line in sql_content.split('\n'):
                # 跳过注释
                stripped = line.strip()
                if stripped.startswith('--') or stripped.startswith('/*') or not stripped:
                    continue

                current_statement.append(line)

                # 如果行以分号结束，认为是一个完整语句
                if stripped.endswith(';'):
                    statement = '\n'.join(current_statement)
                    if statement.strip():
                        statements.append(statement)
                    current_statement = []

            # 执行所有语句
            for i, statement in enumerate(statements):
                try:
                    cur.execute(statement)
                    if i % 100 == 0:  # 每100条语句提交一次
                        conn.commit()
                except Exception as e:
                    self.logger.warning(f"Failed to execute statement (continuing): {str(e)[:100]}")
                    continue

            # 最终提交
            conn.commit()

            self.logger.info(f"Database restored (Python): {len(statements)} statements executed")
            return True

        except Exception as e:
            self.logger.error(f"Python restore failed: {e}", exc_info=True)
            try:
                conn.rollback()
            except Exception:
                pass
            return False

    def delete_backup(self, backup_name):
        """
        Delete a backup file

        Args:
            backup_name: Name of backup file to delete

        Returns:
            bool: True if deleted successfully
        """
        try:
            backup_path = os.path.join(BackupConfig.BACKUP_DIR, backup_name)

            if not os.path.exists(backup_path):
                return False

            os.remove(backup_path)
            self.logger.info(f"Backup deleted: {backup_name}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to delete backup {backup_name}: {e}")
            return False

    def _cleanup_old_backups(self):
        """Clean up old backups based on retention policy"""
        try:
            backups = self.list_backups()

            # Delete backups exceeding MAX_BACKUPS
            if len(backups) > BackupConfig.MAX_BACKUPS:
                excess_backups = backups[BackupConfig.MAX_BACKUPS:]
                for backup in excess_backups:
                    self.delete_backup(backup['name'])
                    self.logger.info(f"Deleted excess backup: {backup['name']}")

            # Delete backups older than MAX_BACKUP_AGE_DAYS
            cutoff_date = datetime.now() - timedelta(days=BackupConfig.MAX_BACKUP_AGE_DAYS)
            for backup in backups:
                created_date = datetime.fromisoformat(backup['created'])
                if created_date < cutoff_date:
                    self.delete_backup(backup['name'])
                    self.logger.info(f"Deleted old backup: {backup['name']}")

        except Exception as e:
            self.logger.error(f"Backup cleanup failed: {e}")

    @staticmethod
    def _format_size(size_bytes):
        """Format file size in human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"


# ========== Scheduled Backup ==========

class BackupScheduler:
    """Automated backup scheduler"""

    def __init__(self):
        self.logger = logging.getLogger('app')
        self.backup_manager = BackupManager()

    def should_run_backup(self):
        """
        Check if automated backup should run

        Returns:
            bool: True if backup should run
        """
        if not BackupConfig.AUTO_BACKUP_ENABLED:
            return False

        try:
            # Check last backup time
            backups = self.backup_manager.list_backups()

            if not backups:
                # No backups exist, should create one
                return True

            # Get most recent backup
            last_backup = backups[0]
            last_backup_time = datetime.fromisoformat(last_backup['created'])

            # Check if last backup was more than 24 hours ago
            time_since_backup = datetime.now() - last_backup_time

            if time_since_backup.total_seconds() > 24 * 3600:
                # Check if current hour matches scheduled hour
                current_hour = datetime.now().hour
                if current_hour == BackupConfig.AUTO_BACKUP_HOUR:
                    return True

            return False

        except Exception as e:
            self.logger.error(f"Failed to check backup schedule: {e}")
            return False

    def run_scheduled_backup(self):
        """Run scheduled backup if needed"""
        try:
            if self.should_run_backup():
                self.logger.info("Running scheduled backup...")
                backup_info = self.backup_manager.create_backup('full', 'Automated daily backup')
                self.logger.info(f"Scheduled backup completed: {backup_info['name']}")
                return backup_info

            return None

        except Exception as e:
            self.logger.error(f"Scheduled backup failed: {e}", exc_info=True)
            return None


# ========== Backup Statistics ==========

def get_backup_statistics():
    """
    Get backup statistics

    Returns:
        dict: Backup statistics
    """
    try:
        manager = BackupManager()
        backups = manager.list_backups()

        if not backups:
            return {
                'total_backups': 0,
                'total_size': 0,
                'total_size_formatted': '0 B',
                'oldest_backup': None,
                'newest_backup': None,
                'backup_types': {}
            }

        total_size = sum(b['size'] for b in backups)
        backup_types = {}

        for backup in backups:
            backup_type = backup.get('type', 'unknown')
            if backup_type not in backup_types:
                backup_types[backup_type] = 0
            backup_types[backup_type] += 1

        return {
            'total_backups': len(backups),
            'total_size': total_size,
            'total_size_formatted': BackupManager._format_size(total_size),
            'oldest_backup': backups[-1] if backups else None,
            'newest_backup': backups[0] if backups else None,
            'backup_types': backup_types
        }

    except Exception as e:
        logging.getLogger('app').error(f"Failed to get backup statistics: {e}")
        return None
