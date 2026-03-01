#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一异步任务管理器

P2.4：将散落在 async_task_service / backup 中的两套异步执行模式
收敛为统一的 TaskManager，提供：
  - 统一的任务提交接口
  - DB 持久化（async_tasks 表）
  - 内存级实时进度追踪
  - 线程自动管理和清理
  - 启动时中断任务修正

业务代码只需提供一个纯函数 target_func(task_tracker=..., **kwargs)，
不再关心线程管理、状态流转、DB 同步等框架层逻辑。
"""
import json
import logging
import threading
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, Callable, Any

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = 'pending'
    PROCESSING = 'processing'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'


class AsyncTask:
    """异步任务实例

    既作为 DB 行的内存映射，也作为线程内的进度追踪器。
    业务函数通过 task_tracker 参数接收此对象，
    可以设置 progress / message 来报告进度。
    """

    def __init__(self, task_type: str, description: str = '',
                 db_id: Optional[int] = None, user_id: Optional[int] = None):
        self.id = str(db_id) if db_id else str(uuid.uuid4())
        self.db_id = db_id
        self.type = task_type
        self.description = description
        self.user_id = user_id
        self.status = TaskStatus.PENDING.value
        self.progress = 0
        self.message = "排队中..."
        self.result = None
        self.error = None
        self.created_at = datetime.now()
        self.completed_at = None
        self._thread = None

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'type': self.type,
            'description': self.description,
            'status': self.status,
            'progress': self.progress,
            'message': self.message,
            'result': self.result,
            'error': self.error,
            'created_at': (self.created_at.isoformat()
                           if isinstance(self.created_at, datetime) else str(self.created_at)),
            'completed_at': (self.completed_at.isoformat()
                             if isinstance(self.completed_at, datetime) and self.completed_at
                             else None),
        }


class TaskManager:
    """统一异步任务管理器

    任务状态持久化到 async_tasks 表。
    活跃任务同时保留内存引用用于线程内进度追踪。
    """

    _tasks: dict = {}
    _lock = threading.Lock()

    # ==================== DB 持久化 ====================

    @classmethod
    def _persist_create(cls, task: AsyncTask):
        """将新任务写入 async_tasks 表"""
        try:
            from models.database import get_db
            conn = get_db()
            cur = conn.cursor()
            meta = json.dumps({
                'description': task.description,
                'uuid': task.id,
            }, ensure_ascii=False)
            cur.execute("""
                INSERT INTO async_tasks
                    (task_type, status, user_id, meta_data, created_at)
                VALUES (%s, 'pending', %s, %s, NOW())
            """, (task.type, task.user_id, meta))
            task.db_id = cur.lastrowid
            task.id = str(task.db_id)
            conn.commit()
        except Exception as e:
            logger.warning("任务持久化创建失败: %s", e)

    @classmethod
    def _persist_status(cls, task: AsyncTask, status: str):
        """同步任务状态到数据库"""
        try:
            from models.database import get_db
            conn = get_db()
            cur = conn.cursor()
            if status in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value):
                result_msg = None
                if task.result:
                    try:
                        result_msg = json.dumps(task.result, ensure_ascii=False, default=str)
                    except (TypeError, ValueError):
                        result_msg = str(task.result)
                cur.execute("""
                    UPDATE async_tasks
                    SET status=%s, completed_at=NOW(), result_message=%s, error_message=%s
                    WHERE id=%s
                """, (status, result_msg, task.error, task.db_id))
            else:
                cur.execute("""
                    UPDATE async_tasks SET status=%s, updated_at=NOW() WHERE id=%s
                """, (status, task.db_id))
            conn.commit()
        except Exception as e:
            logger.warning("任务状态持久化失败 task=%s status=%s: %s", task.db_id, status, e)

    # ==================== 任务提交 ====================

    @classmethod
    def submit(cls, task_type: str, description: str,
               target_func: Callable, *args,
               user_id: Optional[int] = None,
               **kwargs) -> AsyncTask:
        """提交异步任务（统一入口）

        Args:
            task_type: 任务类型标识（如 'performance_import', 'backup'）
            description: 人类可读描述
            target_func: 业务执行函数，签名 func(*args, task_tracker=AsyncTask, **kwargs)
            user_id: 可选，提交者用户 ID
            *args, **kwargs: 透传给 target_func

        Returns:
            AsyncTask: 任务实例（含 id，可用于轮询进度）
        """
        task = AsyncTask(task_type, description, user_id=user_id)

        # 持久化到数据库
        cls._persist_create(task)

        with cls._lock:
            cls._tasks[task.id] = task

        def _worker():
            task.status = TaskStatus.RUNNING.value
            task.message = "执行中..."
            cls._persist_status(task, TaskStatus.RUNNING.value)
            try:
                result = target_func(*args, task_tracker=task, **kwargs)
                task.status = TaskStatus.COMPLETED.value
                task.progress = 100
                task.message = "执行完成"
                task.result = result
            except Exception as e:
                logger.error("异步任务 %s(%s) 失败: %s", task.type, task.db_id, e)
                task.status = TaskStatus.FAILED.value
                task.error = str(e)
                task.message = f"错误: {str(e)}"
            finally:
                task.completed_at = datetime.now()
                cls._persist_status(task, task.status)
                with cls._lock:
                    cls._tasks.pop(task.id, None)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        task._thread = thread

        logger.info("异步任务已提交 type=%s id=%s desc=%s",
                     task_type, task.id, description)
        return task

    # ==================== 任务查询 ====================

    @classmethod
    def get_task(cls, task_id) -> Optional[AsyncTask]:
        """查询任务状态（内存优先，DB 降级）"""
        task_id_str = str(task_id)

        # 优先从内存读（活跃任务有实时进度）
        with cls._lock:
            if task_id_str in cls._tasks:
                return cls._tasks[task_id_str]

        # Fallback 到数据库（历史任务）
        try:
            from models.database import get_db
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                SELECT id, task_type, status, user_id, result_message,
                       error_message, created_at, completed_at, meta_data
                FROM async_tasks WHERE id = %s
            """, (task_id,))
            row = cur.fetchone()
            if row:
                meta = {}
                if row.get('meta_data'):
                    try:
                        meta = json.loads(row['meta_data'])
                    except (json.JSONDecodeError, TypeError):
                        pass
                task = AsyncTask(
                    task_type=row['task_type'],
                    description=meta.get('description', ''),
                    db_id=row['id'],
                    user_id=row.get('user_id'),
                )
                task.status = row['status']
                task.created_at = row['created_at']
                task.completed_at = row['completed_at']
                task.error = row.get('error_message')
                if row.get('result_message'):
                    try:
                        task.result = json.loads(row['result_message'])
                    except (json.JSONDecodeError, TypeError):
                        task.result = row['result_message']
                if task.status == 'completed':
                    task.progress = 100
                    task.message = "执行完成"
                elif task.status == 'failed':
                    task.message = f"错误: {task.error}" if task.error else "失败"
                return task
        except Exception as e:
            logger.warning("任务查询失败 task_id=%s: %s", task_id, e)

        return None

    # ==================== 启动修正 ====================

    @classmethod
    def fix_interrupted(cls):
        """启动时修正异常中断的任务

        将所有处于 pending/processing/running 状态的任务标记为 failed。
        """
        try:
            from models.database import get_db
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                UPDATE async_tasks
                SET status = 'failed',
                    completed_at = NOW(),
                    error_message = '进程中断：任务在服务重启前未完成'
                WHERE status IN ('pending', 'processing', 'running')
            """)
            affected = cur.rowcount
            conn.commit()
            if affected > 0:
                logger.warning("启动修正：标记 %d 个中断任务为 failed", affected)
        except Exception as e:
            logger.warning("修正中断任务失败: %s", e)
