#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步任务服务 — 绩效导入

通过 TaskManager 统一管理异步任务执行。
submit_task() 保持原有 API 签名兼容上层调用。
"""
import os
import json
import logging

from models.database import get_db
from services.domain.pdf_parser import extract_text_from_pdf, parse_pdf_text
from services.task_manager import TaskManager

logger = logging.getLogger(__name__)


def fix_interrupted_tasks():
    """启动时修正异常中断的任务（代理到 TaskManager）"""
    TaskManager.fix_interrupted()


def _run_performance_import(task_tracker, file_path, file_name,
                            user_id, user_info,
                            target_year, target_month, force_import):
    """
    绩效 PDF 导入的纯业务逻辑。

    不再关心线程管理、app_context、状态 SQL，
    只专注于 PDF 解析 → 权限过滤 → 数据写入。
    通过 task_tracker 报告进度。

    Raises:
        RuntimeError: 任何导入失败（自动被 TaskManager 捕获并记录）
    """
    conn = get_db()
    cur = conn.cursor()

    try:
        # 1. Extract Text
        task_tracker.progress = 10
        task_tracker.message = "解析 PDF..."
        try:
            text = extract_text_from_pdf(file_path)
        except Exception as e:
            raise RuntimeError(f"PDF 解析失败: {str(e)}")

        # 2. Parse Text
        task_tracker.progress = 30
        task_tracker.message = "提取数据行..."
        parsed_year, parsed_month, rows = parse_pdf_text(text)

        if not rows:
            raise RuntimeError("PDF 中未找到有效数据行")

        mismatch = (
            parsed_year is not None
            and parsed_month is not None
            and (parsed_year != target_year or parsed_month != target_month)
        )

        # 3. Filter employees (Department Permission Check)
        task_tracker.progress = 50
        task_tracker.message = "权限过滤..."
        valid_emp_nos = set()

        if user_info['role'] == 'admin':
            emp_list = [r['emp_no'] for r in rows]
            if emp_list:
                placeholders = ','.join(['%s'] * len(emp_list))
                cur.execute(
                    f"SELECT emp_no FROM employees WHERE emp_no IN ({placeholders})",
                    emp_list
                )
                valid_emp_nos = {r['emp_no'] for r in cur.fetchall()}
        else:
            dept_id = user_info['department_id']
            if dept_id:
                path = user_info.get('path') or f"/{dept_id}"
                cur.execute(
                    "SELECT id FROM departments WHERE path LIKE %s OR id = %s",
                    (f"{path}/%", dept_id)
                )
                accessible_dept_ids = [row['id'] for row in cur.fetchall()]

                if accessible_dept_ids:
                    emp_list = [r['emp_no'] for r in rows]
                    if emp_list:
                        placeholders = ','.join(['%s'] * len(emp_list))
                        dept_placeholders = ','.join(['%s'] * len(accessible_dept_ids))
                        sql = f"""
                            SELECT emp_no FROM employees
                            WHERE emp_no IN ({placeholders})
                            AND department_id IN ({dept_placeholders})
                        """
                        cur.execute(sql, emp_list + accessible_dept_ids)
                        valid_emp_nos = {r['emp_no'] for r in cur.fetchall()}

        filtered = [r for r in rows if r["emp_no"] in valid_emp_nos]
        skipped_count = len(rows) - len(filtered)

        if not filtered:
            raise RuntimeError("无权限范围内的有效记录（或员工不在花名册中）")

        # 4. Insert Data
        task_tracker.progress = 70
        task_tracker.message = f"写入 {len(filtered)} 条记录..."
        batch_data = [
            (
                r["emp_no"], r["name"], target_year, target_month,
                r["score"], r["grade"], file_name, user_id
            )
            for r in filtered
        ]

        cur.executemany(
            """
            INSERT INTO performance_records(emp_no, name, year, month, score, grade, src_file, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                name=VALUES(name), score=VALUES(score),
                grade=VALUES(grade), src_file=VALUES(src_file)
            """,
            batch_data
        )

        # 5. Log import
        imported_count = len(filtered)
        details = {
            'year': target_year,
            'month': target_month,
            'imported': imported_count,
            'skipped': skipped_count,
            'mismatch_warning': mismatch
        }

        cur.execute("""
            INSERT INTO import_logs (
                module, operation, user_id, username, user_role,
                department_id, department_name, file_name,
                total_rows, success_rows, failed_rows, skipped_rows,
                import_details, created_at
            ) VALUES (%s, 'batch_import_async', %s, %s, %s, %s, %s, %s, %s, %s, 0, %s, %s, NOW())
        """, (
            'performance', user_id, user_info['username'], user_info['role'],
            user_info['department_id'], user_info.get('department_name'), file_name,
            len(rows), imported_count, skipped_count, json.dumps(details)
        ))

        conn.commit()

        # 6. Result
        result_msg = f"已导入 {imported_count} 条，跳过 {skipped_count} 条"
        if mismatch:
            result_msg += f"（注: PDF 日期 {parsed_year}-{parsed_month} 与目标 {target_year}-{target_month} 不一致）"

        return {'message': result_msg, 'imported': imported_count, 'skipped': skipped_count}

    except Exception:
        conn.rollback()
        raise
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


def submit_task(file_path, file_name, user_id, user_info,
                target_year, target_month, force_import=False):
    """提交绩效导入异步任务（API 保持兼容）

    Returns:
        int: 任务 ID（async_tasks 表主键）
    """
    task = TaskManager.submit(
        task_type='performance_import',
        description=f"绩效导入 {file_name} ({target_year}-{target_month})",
        target_func=_run_performance_import,
        user_id=user_id,
        # 以下为透传给 _run_performance_import 的参数
        file_path=file_path,
        file_name=file_name,
        target_year=target_year,
        target_month=target_month,
        force_import=force_import,
        user_info=user_info,
    )
    return int(task.id)
