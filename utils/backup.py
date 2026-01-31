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

class TaskStatus(Enum):
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'

class BackupTask:
    """Background task for backup/restore operations"""
    
    def __init__(self, task_type, description=''):
        self.id = str(uuid.uuid4())
        self.type = task_type
        self.description = description
        self.status = TaskStatus.PENDING.value
        self.progress = 0
        self.message = "Queued..."
        self.result = None
        self.error = None
        self.created_at = datetime.now()
        self.completed_at = None
        self._thread = None
    
    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'description': self.description,
            'status': self.status,
            'progress': self.progress,
            'message': self.message,
            'result': self.result,
            'error': self.error,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

class BackupTaskManager:
    """Manages background backup/restore tasks"""
    
    _tasks = {}
    _lock = threading.Lock()
    
    @classmethod
    def create_task(cls, task_type, task_description, target_func, *args, **kwargs):
        """Create and start a new background task"""
        task = BackupTask(task_type, task_description)
        
        with cls._lock:
            cls._tasks[task.id] = task
        
        # Define wrapper to update task status
        def task_wrapper():
            task.status = TaskStatus.RUNNING.value
            task.message = "Starting..."
            try:
                # Pass task object to function if it accepts 'task_tracker'
                # otherwise just run it
                result = target_func(*args, task_tracker=task, **kwargs)
                
                task.status = TaskStatus.COMPLETED.value
                task.progress = 100
                task.message = "Completed successfully"
                task.result = result
            except Exception as e:
                import traceback
                traceback.print_exc()
                task.status = TaskStatus.FAILED.value
                task.error = str(e)
                task.message = f"Error: {str(e)}"
            finally:
                task.completed_at = datetime.now()
                
        # Start thread
        thread = threading.Thread(target=task_wrapper)
        thread.daemon = True
        thread.start()
        task._thread = thread
        
        return task
        
    @classmethod
    def get_task(cls, task_id):
        """Get task by ID"""
        return cls._tasks.get(task_id)
        
    @classmethod
    def cleanup_old_tasks(cls, max_age_seconds=3600):
        """Clean up old completed tasks"""
        with cls._lock:
            now = datetime.now()
            to_remove = []
            for tid, task in cls._tasks.items():
                if task.completed_at:
                    age = (now - task.completed_at).total_seconds()
                    if age > max_age_seconds:
                        to_remove.append(tid)
            
            for tid in to_remove:
                del cls._tasks[tid]


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
        Create database backup using mysqldump

        Args:
            timestamp: Backup timestamp string

        Returns:
            str: Path to backup SQL file
        """
        try:
            backup_sql_path = os.path.join(BackupConfig.BACKUP_DIR, f"db_backup_{timestamp}.sql")

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
                return None

            self.logger.info(f"Database backed up to: {backup_sql_path}")
            return backup_sql_path

        except FileNotFoundError:
            self.logger.error("mysqldump command not found. Please ensure MySQL client tools are installed.")
            return None
        except Exception as e:
            self.logger.error(f"Database backup failed: {e}", exc_info=True)
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
            except:
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
        Restore database from SQL dump file

        Args:
            sql_file_path: Path to SQL dump file

        Returns:
            bool: True if restore successful
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
                return False

            return True

        except FileNotFoundError:
            self.logger.error("mysql command not found. Please ensure MySQL client tools are installed.")
            return False
        except Exception as e:
            self.logger.error(f"Database restore failed: {e}", exc_info=True)
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
