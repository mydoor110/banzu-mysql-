#!/bin/bash
# 数据库索引检查脚本

echo "================================================================================"
echo "数据库索引检查报告"
echo "================================================================================"

mysql -h 192.168.1.99 -u Banzu -pBR4rpz7XahFHiRpH banzu << 'EOF'

-- 检查 training_records 表
SELECT '【training_records】' as '';
SELECT '现有索引:' as '';
SHOW INDEX FROM training_records;

SELECT '' as '';
SELECT '表结构:' as '';
DESCRIBE training_records;

-- 检查 safety_inspection_records 表
SELECT '' as '';
SELECT '【safety_inspection_records】' as '';
SELECT '现有索引:' as '';
SHOW INDEX FROM safety_inspection_records;

SELECT '' as '';
SELECT '表结构:' as '';
DESCRIBE safety_inspection_records;

-- 检查 performance_records 表
SELECT '' as '';
SELECT '【performance_records】' as '';
SELECT '现有索引:' as '';
SHOW INDEX FROM performance_records;

SELECT '' as '';
SELECT '表结构:' as '';
DESCRIBE performance_records;

-- 检查 employees 表
SELECT '' as '';
SELECT '【employees】' as '';
SELECT '现有索引:' as '';
SHOW INDEX FROM employees;

-- 数据量统计
SELECT '' as '';
SELECT '================================================================================' as '';
SELECT '表数据量统计' as '';
SELECT '================================================================================' as '';

SELECT 'training_records' as 表名, COUNT(*) as 记录数 FROM training_records;
SELECT 'safety_inspection_records' as 表名, COUNT(*) as 记录数 FROM safety_inspection_records;
SELECT 'performance_records' as 表名, COUNT(*) as 记录数 FROM performance_records;
SELECT 'employees' as 表名, COUNT(*) as 记录数 FROM employees;

EOF

echo ""
echo "================================================================================"
echo "索引优化建议"
echo "================================================================================"
echo ""
echo "如果上述表缺少以下索引,建议添加:"
echo ""
echo "1. training_records:"
echo "   CREATE INDEX idx_training_emp_date ON training_records(emp_no, training_date);"
echo ""
echo "2. safety_inspection_records:"
echo "   CREATE INDEX idx_safety_person_date ON safety_inspection_records(inspected_person, inspection_date);"
echo ""
echo "3. performance_records:"
echo "   CREATE INDEX idx_performance_emp ON performance_records(emp_no);"
echo ""
