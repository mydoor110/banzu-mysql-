-- 能力画像性能优化 - 添加复合索引
-- 这些索引将显著提升综合能力画像API的查询性能

USE banzu;

-- 1. training_records 复合索引
-- 用于: WHERE emp_no = ? AND training_date >= ? AND training_date < ?
CREATE INDEX IF NOT EXISTS idx_training_emp_date_composite 
ON training_records(emp_no, training_date);

-- 2. safety_inspection_records 复合索引  
-- 用于: WHERE inspected_person = ? AND inspection_date >= ? AND inspection_date < ?
CREATE INDEX IF NOT EXISTS idx_safety_person_date_composite
ON safety_inspection_records(inspected_person, inspection_date);

-- 3. performance_records 年月复合索引优化
-- 用于: WHERE emp_no = ? AND year = ? AND month = ?
CREATE INDEX IF NOT EXISTS idx_performance_emp_year_month
ON performance_records(emp_no, year, month);

-- 查看索引创建结果
SHOW INDEX FROM training_records WHERE Key_name LIKE '%composite%';
SHOW INDEX FROM safety_inspection_records WHERE Key_name LIKE '%composite%';
SHOW INDEX FROM performance_records WHERE Key_name LIKE '%emp_year_month%';

-- 分析表以更新统计信息
ANALYZE TABLE training_records;
ANALYZE TABLE safety_inspection_records;
ANALYZE TABLE performance_records;

SELECT '索引优化完成!' as status;
