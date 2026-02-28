#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
迁移脚本：将 employees 表日期字段从 VARCHAR(20) 迁移到 DATE

使用方式：
    flask --app app migrate-dates               # 执行迁移
    flask --app app migrate-dates --dry-run      # 仅预览
    
或直接运行：
    python scripts/migrate_date_fields.py

迁移内容：
    1. 尝试解析现有文本日期数据
    2. 对无法解析的记录置 NULL 并记录
    3. ALTER TABLE MODIFY COLUMN 为 DATE 类型
"""
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import get_db, close_db


DATE_FIELDS = [
    'birth_date',
    'certification_date',
    'work_start_date',
    'entry_date',
    'solo_driving_date',
]

# 支持的日期格式
DATE_PATTERNS = [
    (r'^\d{4}-\d{1,2}-\d{1,2}$', '%Y-%m-%d'),            # 2024-01-15
    (r'^\d{4}/\d{1,2}/\d{1,2}$', '%Y/%m/%d'),             # 2024/01/15
    (r'^\d{4}\.\d{1,2}\.\d{1,2}$', '%Y.%m.%d'),           # 2024.01.15
    (r'^\d{4}年\d{1,2}月\d{1,2}日$', '%Y年%m月%d日'),       # 2024年1月15日
    (r'^\d{4}年\d{1,2}月$', None),                         # 2024年1月 (需特殊处理)
    (r'^\d{4}-\d{1,2}$', None),                            # 2024-01 (需特殊处理)
]


def migrate_date_fields(dry_run=False):
    """将 employees 表日期字段迁移为 DATE 类型
    
    Args:
        dry_run: 仅预览，不执行写入
    """
    conn = get_db()
    cur = conn.cursor()
    
    try:
        # 检查当前字段类型
        cur.execute("""
            SELECT COLUMN_NAME, DATA_TYPE 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'employees' 
            AND COLUMN_NAME IN (%s, %s, %s, %s, %s)
        """, tuple(DATE_FIELDS))
        
        current_types = {row['COLUMN_NAME']: row['DATA_TYPE'] for row in cur.fetchall()}
        
        fields_to_migrate = [f for f in DATE_FIELDS if current_types.get(f, 'varchar') != 'date']
        
        if not fields_to_migrate:
            print("✅ 所有日期字段已经是 DATE 类型，无需迁移")
            return
        
        print(f"📋 需要迁移的字段: {', '.join(fields_to_migrate)}")
        
        # ===== 阶段 1：清洗数据 =====
        print("\n🔧 阶段 1：清洗日期数据...")
        
        total_cleaned = 0
        total_nulled = 0
        
        for field in fields_to_migrate:
            if current_types.get(field) == 'date':
                print(f"  ⏭️  {field}: 已是 DATE 类型")
                continue
            
            # 获取所有非空且非标准格式的记录
            cur.execute(f"""
                SELECT id, {field} as val FROM employees 
                WHERE {field} IS NOT NULL AND {field} != ''
            """)
            rows = cur.fetchall()
            
            cleaned = 0
            nulled = 0
            null_samples = []
            
            for row in rows:
                val = str(row['val']).strip()
                if not val:
                    continue
                
                # 尝试标准化日期格式
                standardized = _try_parse_date(val)
                
                if standardized:
                    if standardized != val:
                        if not dry_run:
                            cur.execute(
                                f"UPDATE employees SET {field} = %s WHERE id = %s",
                                (standardized, row['id'])
                            )
                        cleaned += 1
                else:
                    # 无法解析，置 NULL
                    if not dry_run:
                        cur.execute(
                            f"UPDATE employees SET {field} = NULL WHERE id = %s",
                            (row['id'],)
                        )
                    nulled += 1
                    if len(null_samples) < 3:
                        null_samples.append(f"id={row['id']}: '{val}'")
            
            status = "🔍" if dry_run else "✅"
            print(f"  {status} {field}: 标准化 {cleaned} 条, 置NULL {nulled} 条"
                  + (f" (共 {len(rows)} 条)" if rows else " (无数据)"))
            
            if null_samples:
                print(f"       无法解析样例: {', '.join(null_samples)}")
            
            total_cleaned += cleaned
            total_nulled += nulled
        
        if not dry_run:
            conn.commit()
        
        # ===== 阶段 2：ALTER TABLE =====
        print(f"\n🔧 阶段 2：修改字段类型...")
        
        for field in fields_to_migrate:
            if current_types.get(field) == 'date':
                continue
            
            if dry_run:
                print(f"  🔍 {field}: 将从 VARCHAR → DATE")
            else:
                try:
                    cur.execute(f"ALTER TABLE employees MODIFY COLUMN {field} DATE DEFAULT NULL")
                    conn.commit()
                    print(f"  ✅ {field}: VARCHAR → DATE")
                except Exception as e:
                    print(f"  ❌ {field}: 迁移失败 - {e}")
                    print(f"       请检查是否仍有非法日期数据")
        
        # 总结
        print(f"\n{'🔍 dry-run 预览' if dry_run else '✅ 迁移完成'}")
        print(f"   标准化: {total_cleaned} 条, 置NULL: {total_nulled} 条")
        
    finally:
        close_db()


def _try_parse_date(val):
    """尝试将各种日期字符串标准化为 YYYY-MM-DD 格式
    
    Returns:
        str: 标准化后的日期字符串，或 None（无法解析）
    """
    val = val.strip()
    
    # 已经是标准格式
    if re.match(r'^\d{4}-\d{2}-\d{2}$', val):
        return val
    
    # 尝试各种格式
    # yyyy-m-d / yyyy/m/d / yyyy.m.d
    m = re.match(r'^(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})[日]?$', val)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1900 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{mo:02d}-{d:02d}"
    
    # yyyy年m月 / yyyy-m （缺日，默认1号）
    m = re.match(r'^(\d{4})[-/.年](\d{1,2})[月]?$', val)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        if 1900 <= y <= 2100 and 1 <= mo <= 12:
            return f"{y:04d}-{mo:02d}-01"
    
    return None


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='将 employees 表日期字段迁移为 DATE 类型')
    parser.add_argument('--dry-run', action='store_true', help='仅预览，不执行')
    args = parser.parse_args()
    migrate_date_fields(dry_run=args.dry_run)
