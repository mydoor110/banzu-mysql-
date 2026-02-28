#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
迁移脚本：为业务表添加 employee_id 外键并回填

使用方式：
    flask --app app migrate-employee-id          # 执行迁移
    flask --app app migrate-employee-id --dry-run # 仅预览
    
或直接运行：
    python scripts/migrate_employee_id.py

迁移内容：
    1. ALTER TABLE: 为三张表添加 employee_id 列（幂等）
    2. UPDATE: 基于 emp_no/name 回填 employee_id
    3. 输出回填统计
"""
import sys
import os

# 支持直接运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import get_db, close_db


def migrate_employee_id(dry_run=False):
    """为业务表添加 employee_id 并回填
    
    Args:
        dry_run: 仅预览，不执行写入
    """
    conn = get_db()
    cur = conn.cursor()
    
    try:
        # ===== 阶段 1：ALTER TABLE 添加列（幂等） =====
        tables_config = [
            {
                'table': 'performance_records',
                'match_field': 'emp_no',  # 通过 emp_no 匹配
                'match_type': 'emp_no',
            },
            {
                'table': 'training_records',
                'match_field': 'emp_no',
                'match_type': 'emp_no',
            },
            {
                'table': 'safety_inspection_records',
                'match_field': 'inspected_person',  # 通过姓名匹配
                'match_type': 'name',
            },
        ]
        
        for config in tables_config:
            table = config['table']
            # 检查列是否已存在
            cur.execute(f"""
                SELECT COUNT(*) AS cnt 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = '{table}' 
                AND COLUMN_NAME = 'employee_id'
            """)
            exists = cur.fetchone()['cnt'] > 0
            
            if exists:
                print(f"  ⏭️  {table}.employee_id 列已存在")
            elif dry_run:
                print(f"  🔍 {table}: 将添加 employee_id 列")
            else:
                cur.execute(f"""
                    ALTER TABLE {table} 
                    ADD COLUMN employee_id INT DEFAULT NULL,
                    ADD CONSTRAINT fk_{table}_employee_id 
                    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE SET NULL
                """)
                print(f"  ✅ {table}: 已添加 employee_id 列")
        
        if not dry_run:
            conn.commit()
        
        # ===== 阶段 2：回填 employee_id =====
        print("\n📊 回填 employee_id...")
        
        for config in tables_config:
            table = config['table']
            match_field = config['match_field']
            match_type = config['match_type']
            
            # 统计总记录数
            cur.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
            total = cur.fetchone()['cnt']
            
            # 统计已回填的记录数
            cur.execute(f"SELECT COUNT(*) AS cnt FROM {table} WHERE employee_id IS NOT NULL")
            already_filled = cur.fetchone()['cnt']
            
            # 统计待回填的记录数
            cur.execute(f"SELECT COUNT(*) AS cnt FROM {table} WHERE employee_id IS NULL")
            to_fill = cur.fetchone()['cnt']
            
            if to_fill == 0:
                print(f"  ⏭️  {table}: 全部已回填 ({total} 条)")
                continue
            
            # 根据匹配方式构建 UPDATE
            if match_type == 'emp_no':
                update_sql = f"""
                    UPDATE {table} t
                    INNER JOIN employees e ON t.{match_field} = e.emp_no
                    SET t.employee_id = e.id
                    WHERE t.employee_id IS NULL
                """
            else:  # name
                update_sql = f"""
                    UPDATE {table} t
                    INNER JOIN employees e ON t.{match_field} = e.name
                    SET t.employee_id = e.id
                    WHERE t.employee_id IS NULL
                """
            
            if dry_run:
                print(f"  🔍 {table}: 总 {total} 条, 已回填 {already_filled}, 待回填 {to_fill}")
            else:
                cur.execute(update_sql)
                affected = cur.rowcount
                remaining = to_fill - affected
                print(f"  ✅ {table}: 回填 {affected}/{to_fill} 条"
                      + (f"（{remaining} 条无法匹配）" if remaining > 0 else ""))
        
        if not dry_run:
            conn.commit()
            print("\n✅ employee_id 迁移完成")
        else:
            print("\n🔍 dry-run 模式，未做任何修改")
            
    finally:
        close_db()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='为业务表添加 employee_id 并回填')
    parser.add_argument('--dry-run', action='store_true', help='仅预览，不执行')
    args = parser.parse_args()
    migrate_employee_id(dry_run=args.dry_run)
