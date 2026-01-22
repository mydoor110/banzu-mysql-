#!/usr/bin/env python3
"""
数据库索引检查和性能优化脚本
"""
import pymysql
import sys

# 数据库连接配置
DB_CONFIG = {
    'host': '1Panel-mysql-Io9i',
    'user': 'Banzu',
    'password': 'BR4rpz7XahFHiRpH',
    'database': 'Banzu',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

def check_indexes():
    """检查关键表的索引情况"""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        print("=" * 80)
        print("数据库索引检查报告")
        print("=" * 80)
        
        # 需要检查的表
        tables = [
            'training_records',
            'safety_inspection_records',
            'performance_records',
            'employees'
        ]
        
        for table in tables:
            print(f"\n【{table}】")
            print("-" * 80)
            
            # 查看现有索引
            cur.execute(f"SHOW INDEX FROM {table}")
            indexes = cur.fetchall()
            
            if indexes:
                print("现有索引:")
                for idx in indexes:
                    print(f"  - {idx['Key_name']}: {idx['Column_name']} (Unique: {idx['Non_unique'] == 0})")
            else:
                print("  ⚠️  没有索引!")
            
            # 查看表结构
            cur.execute(f"DESCRIBE {table}")
            columns = cur.fetchall()
            print(f"\n表字段: {', '.join([col['Field'] for col in columns])}")
        
        print("\n" + "=" * 80)
        print("索引优化建议")
        print("=" * 80)
        
        # 检查并给出建议
        suggestions = []
        
        # 检查 training_records
        cur.execute("SHOW INDEX FROM training_records WHERE Column_name IN ('emp_no', 'training_date')")
        if cur.rowcount < 2:
            suggestions.append({
                'table': 'training_records',
                'sql': "CREATE INDEX idx_training_emp_date ON training_records(emp_no, training_date);",
                'reason': '加速按员工和日期查询培训记录'
            })
        
        # 检查 safety_inspection_records  
        cur.execute("SHOW INDEX FROM safety_inspection_records WHERE Column_name IN ('inspected_person', 'inspection_date')")
        if cur.rowcount < 2:
            suggestions.append({
                'table': 'safety_inspection_records',
                'sql': "CREATE INDEX idx_safety_person_date ON safety_inspection_records(inspected_person, inspection_date);",
                'reason': '加速按人员和日期查询安全检查记录'
            })
        
        # 检查 performance_records
        cur.execute("SHOW INDEX FROM performance_records WHERE Column_name = 'emp_no'")
        if cur.rowcount == 0:
            suggestions.append({
                'table': 'performance_records',
                'sql': "CREATE INDEX idx_performance_emp ON performance_records(emp_no);",
                'reason': '加速按员工查询绩效记录'
            })
        
        if suggestions:
            print("\n⚠️  发现缺失的索引,建议添加:\n")
            for i, sug in enumerate(suggestions, 1):
                print(f"{i}. 【{sug['table']}】")
                print(f"   原因: {sug['reason']}")
                print(f"   SQL: {sug['sql']}")
                print()
        else:
            print("\n✅ 所有关键索引都已存在!")
        
        # 查询统计信息
        print("=" * 80)
        print("表数据量统计")
        print("=" * 80)
        for table in tables:
            cur.execute(f"SELECT COUNT(*) as count FROM {table}")
            count = cur.fetchone()['count']
            print(f"{table}: {count:,} 条记录")
        
        cur.close()
        conn.close()
        
        return suggestions
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return None

def apply_indexes(suggestions):
    """应用索引优化"""
    if not suggestions:
        print("没有需要添加的索引")
        return
    
    print("\n" + "=" * 80)
    print("开始添加索引...")
    print("=" * 80)
    
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        for sug in suggestions:
            print(f"\n执行: {sug['sql']}")
            try:
                cur.execute(sug['sql'])
                conn.commit()
                print(f"✅ 成功添加索引到 {sug['table']}")
            except Exception as e:
                print(f"⚠️  跳过 (可能已存在): {e}")
        
        cur.close()
        conn.close()
        
        print("\n✅ 索引优化完成!")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("正在连接数据库...")
    suggestions = check_indexes()
    
    if suggestions:
        print("\n" + "=" * 80)
        response = input("是否立即添加这些索引? (y/n): ")
        if response.lower() == 'y':
            apply_indexes(suggestions)
        else:
            print("已取消,您可以稍后手动执行上述SQL命令")
