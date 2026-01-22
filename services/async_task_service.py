
import threading
import os
import json
import time
from datetime import datetime
from flask import current_app
from models.database import get_db
from blueprints.performance import extract_text_from_pdf, parse_pdf_text
# Note: We need to import log_import_operation but it also depends on usage.
# We might need to implement a custom logger or pass enough context.

def run_performance_import_task(app, task_id, file_path, file_name, user_id, user_info, target_year, target_month, force_import):
    """
    Background worker for performance PDF import.
    """
    with app.app_context():
        conn = get_db()
        cur = conn.cursor()
        
        try:
            # Update task status to processing
            cur.execute("UPDATE async_tasks SET status='processing', updated_at=NOW() WHERE id=%s", (task_id,))
            conn.commit()

            # 1. Extract Text
            try:
                text = extract_text_from_pdf(file_path)
            except Exception as e:
                raise RuntimeError(f"PDF extraction failed: {str(e)}")

            # 2. Parse Text
            parsed_year, parsed_month, rows = parse_pdf_text(text)
            
            if not rows:
                raise RuntimeError("No valid rows found in PDF.")

            # Check year/month mismatch if not forced
            mismatch = (
                parsed_year is not None
                and parsed_month is not None
                and (parsed_year != target_year or parsed_month != target_month)
            )
            
            # If mismatch and NOT force_import, we should technically stop or warn.
            # But in async mode, "confirm" is hard. 
            # Strategy: If force_import is False, fail if mismatch. 
            # The frontend should probably ask for confirmation BEFORE async submission if possible (parse header first?), 
            # BUT efficient async usually means "fire and forget".
            # User requirement: "Just upload".
            # Compromise: Record warning in result but proceed if close enough? 
            # Or better: Just use the parsed year/month if confident?
            # Let's stick to user selected year/month as primary truth unless it's way off?
            # Actually, standard behavior: Import using the SELECTED year/month (target), 
            # maybe log the mismatch.
            
            # 3. Filter employees (Department Permission Check)
            # Re-implement department filter logic manually since no session
            # user_info dict should contain: {'role': ..., 'department_id': ..., 'path': ...}
            
            valid_emp_nos = set()
            
            if user_info['role'] == 'admin':
                # Admin sees all - get all emp_nos in rows that exist in DB
                emp_list = [r['emp_no'] for r in rows]
                if emp_list:
                    placeholders = ','.join(['%s'] * len(emp_list))
                    cur.execute(f"SELECT emp_no FROM employees WHERE emp_no IN ({placeholders})", emp_list)
                    valid_emp_nos = {r['emp_no'] for r in cur.fetchall()}
            else:
                # Normal logic: Filter by accessible departments
                # We need to find accessible department IDs for this user
                # Query departments table
                
                # Logic from helpers.get_accessible_departments
                dept_id = user_info['department_id']
                if not dept_id:
                     valid_emp_nos = set() # No dept, no access
                else:
                    path = user_info.get('path') or f"/{dept_id}"
                    cur.execute(
                        "SELECT id FROM departments WHERE path LIKE %s OR id = %s", 
                        (f"{path}/%", dept_id)
                    )
                    accessible_dept_ids = [row['id'] for row in cur.fetchall()]
                    
                    if not accessible_dept_ids:
                        valid_emp_nos = set()
                    else:
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
                raise RuntimeError("No valid records found for your permissions (or employee not found in roster).")

            # 4. Insert Data
            batch_data = [
                (
                    r["emp_no"],
                    r["name"],
                    target_year,
                    target_month,
                    r["score"],
                    r["grade"],
                    file_name,
                    user_id
                )
                for r in filtered
            ]
            
            cur.executemany(
                """
                INSERT INTO performance_records(emp_no, name, year, month, score, grade, src_file, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    name=VALUES(name),
                    score=VALUES(score),
                    grade=VALUES(grade),
                    src_file=VALUES(src_file)
                """,
                batch_data
            )
            
            # Log successful import (Manual insertion to import_logs because helpers.log relies on session)
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

            # 5. Success
            result_msg = f"Imported {imported_count} records. Skipped {skipped_count}."
            if mismatch:
                result_msg += f" (Note: PDF date {parsed_year}-{parsed_month} differed from target {target_year}-{target_month})"

            cur.execute("""
                UPDATE async_tasks 
                SET status='completed', completed_at=NOW(), result_message=%s 
                WHERE id=%s
            """, (result_msg, task_id))
            conn.commit()

        except Exception as e:
            conn.rollback()
            cur.execute("""
                UPDATE async_tasks 
                SET status='failed', completed_at=NOW(), error_message=%s 
                WHERE id=%s
            """, (str(e), task_id))
            conn.commit()
            print(f"Task {task_id} failed: {e}")
        finally:
            # Clean up file
            if os.path.exists(file_path):
                os.remove(file_path)

def submit_task(file_path, file_name, user_id, user_info, target_year, target_month, force_import=False):
    conn = get_db()
    cur = conn.cursor()
    
    meta = {
        'target_year': target_year,
        'target_month': target_month,
        'force_import': force_import
    }
    
    cur.execute("""
        INSERT INTO async_tasks (task_type, status, user_id, file_name, file_path, meta_data, created_at)
        VALUES ('performance_import', 'pending', %s, %s, %s, %s, NOW())
    """, (user_id, file_name, file_path, json.dumps(meta)))
    
    task_id = cur.lastrowid
    conn.commit()
    
    # Identify app for context
    # Usually passed from view, but here we capture 'current_app._get_current_object()'
    app = current_app._get_current_object()
    
    t = threading.Thread(
        target=run_performance_import_task,
        args=(app, task_id, file_path, file_name, user_id, user_info, target_year, target_month, force_import)
    )
    t.start()
    
    return task_id
