#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试战力雷达图数据
用于诊断雷达图不显示的问题
"""
from models.database import get_db
from blueprints.personnel import list_personnel
from blueprints.helpers import calculate_years_from_date

def test_radar_data():
    print("=== 测试战力雷达图数据 ===\n")
    
    # 1. 测试人员列表
    rows = list_personnel()
    print(f"1. 总人员数: {len(rows)}")
    
    # 2. 筛选司机
    drivers = [r for r in rows if '司机' in (r.get('position') or '') and '队长' not in (r.get('position') or '')]
    print(f"2. 司机数: {len(drivers)}")
    
    # 3. 检查日期字段
    has_solo_date = sum(1 for r in drivers if r.get('solo_driving_date'))
    has_cert_date = sum(1 for r in drivers if r.get('certification_date'))
    has_entry_date = sum(1 for r in drivers if r.get('entry_date'))
    
    print(f"3. 有单驾日期: {has_solo_date}/{len(drivers)}")
    print(f"   有取证日期: {has_cert_date}/{len(drivers)}")
    print(f"   有入职日期: {has_entry_date}/{len(drivers)}")
    
    # 4. 检查年限计算
    if drivers:
        sample = drivers[0]
        print(f"\n4. 示例数据 ({sample.get('name')}):")
        print(f"   单驾日期: {sample.get('solo_driving_date')}")
        print(f"   单驾年限: {sample.get('solo_driving_years')}")
        print(f"   取证日期: {sample.get('certification_date')}")
        print(f"   取证年限: {sample.get('certification_years')}")
        print(f"   入职日期: {sample.get('entry_date')}")
        print(f"   司龄: {sample.get('tenure_years')}")
    
    # 5. 检查部门统计
    dept_stats = {}
    for r in drivers:
        dept_id = r.get('department_id')
        if dept_id:
            if dept_id not in dept_stats:
                dept_stats[dept_id] = {'count': 0, 'with_data': 0}
            dept_stats[dept_id]['count'] += 1
            if r.get('solo_driving_years') and r.get('certification_years') and r.get('tenure_years'):
                dept_stats[dept_id]['with_data'] += 1
    
    print(f"\n5. 部门统计:")
    for dept_id, stats in dept_stats.items():
        print(f"   部门{dept_id}: {stats['count']}人, {stats['with_data']}人有完整数据")
    
    # 6. 检查数据库字段类型
    print(f"\n6. 数据库字段类型检查:")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SHOW COLUMNS FROM employees LIKE '%date%'")
    for row in cur.fetchall():
        print(f"   {row['Field']}: {row['Type']}")
    
    print("\n=== 测试完成 ===")

if __name__ == '__main__':
    test_radar_data()
