#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试脚本：对比人员列表API和详情API返回的分数差异
"""
import json
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, '.env'))

from flask import Flask
from models.database import get_db

# 创建Flask应用上下文
app = Flask(__name__)
app.config['SECRET_KEY'] = 'debug'

def compare_scores(emp_no: str, start_date: str = None, end_date: str = None):
    """对比两个API计算的各维度分数"""
    from datetime import datetime
    from blueprints.personnel import (
        calculate_training_score_with_penalty,
        calculate_safety_score_dual_track,
        calculate_performance_score_monthly,
        calculate_performance_score_period,
        calculate_learning_ability_new,
        calculate_stability_for_employee,
        calculate_stability_score_new,
        calculate_years_from_date,
        get_year_month_concat,
        _resolve_stability_window,
        _month_range,
        _month_shift,
        _month_index,
        _load_monthly_safety_violations,
        _build_monthly_safety_scores
    )
    from blueprints.safety import extract_score_from_assessment
    from services.algorithm_config_service import AlgorithmConfigService

    algo_config = AlgorithmConfigService.get_active_config()
    score_weights = algo_config['comprehensive']['score_weights']

    # 默认使用当月
    if not start_date and not end_date:
        current_month = datetime.now().strftime('%Y-%m')
        start_date = current_month
        end_date = current_month

    conn = get_db()
    cur = conn.cursor()

    # 获取员工信息
    cur.execute("SELECT * FROM employees WHERE emp_no = %s", (emp_no,))
    emp = cur.fetchone()
    if not emp:
        print(f"找不到员工: {emp_no}")
        return

    emp_name = emp['name']
    cert_date = emp.get('certification_date')
    cert_years = calculate_years_from_date(cert_date) if cert_date else None
    dept_id = emp.get('department_id')

    print(f"\n{'='*60}")
    print(f"员工: {emp_name} ({emp_no})")
    print(f"日期范围: {start_date} ~ {end_date}")
    print(f"{'='*60}")

    # ========== 方式1: 简化版（类似api_students_list） ==========
    print(f"\n【方式1: 简化版计算（类似人员列表）】")

    # 培训
    training_query = """
        SELECT score, is_qualified, is_disqualified, training_date
        FROM training_records WHERE emp_no = %s
    """
    params = [emp_no]
    if start_date:
        training_query += " AND DATE_FORMAT(training_date, '%%Y-%%m') >= %s"
        params.append(start_date)
    if end_date:
        training_query += " AND DATE_FORMAT(training_date, '%%Y-%%m') <= %s"
        params.append(end_date)
    cur.execute(training_query, params)
    training_records = cur.fetchall()

    duration_days = 30 if start_date == end_date else 180
    training_result1 = calculate_training_score_with_penalty(training_records, duration_days, cert_years, algo_config)
    training_score1 = training_result1['radar_score']

    # 安全
    safety_query = "SELECT assessment, inspection_date FROM safety_inspection_records WHERE inspected_person = %s"
    params = [emp_name]
    if start_date:
        safety_query += " AND DATE_FORMAT(inspection_date, '%%Y-%%m') >= %s"
        params.append(start_date)
    if end_date:
        safety_query += " AND DATE_FORMAT(inspection_date, '%%Y-%%m') <= %s"
        params.append(end_date)
    cur.execute(safety_query, params)
    safety_rows = cur.fetchall()

    violations_list = [float(extract_score_from_assessment(r['assessment']))
                      for r in safety_rows if extract_score_from_assessment(r['assessment']) > 0]
    months_active = 1
    safety_result1 = calculate_safety_score_dual_track(violations_list, months_active, algo_config)
    safety_score1 = safety_result1['final_score']

    # 绩效
    is_monthly = (start_date == end_date) if start_date and end_date else True
    perf_query = f"""
        SELECT score, grade, year, month FROM performance_records
        WHERE emp_no = %s AND ({get_year_month_concat()}) >= %s AND ({get_year_month_concat()}) <= %s
        ORDER BY year, month
    """
    cur.execute(perf_query, [emp_no, start_date, end_date])
    perf_rows = cur.fetchall()

    if perf_rows:
        if is_monthly and len(perf_rows) == 1:
            perf_result1 = calculate_performance_score_monthly(
                perf_rows[0]['grade'] or 'B+',
                float(perf_rows[0]['score'] or 95),
                algo_config
            )
            performance_score1 = perf_result1['radar_value']
        else:
            grade_list = [r['grade'] or 'B+' for r in perf_rows]
            grade_dates = [f"{r['year']}-{r['month']:02d}" for r in perf_rows]
            perf_result1 = calculate_performance_score_period(grade_list, grade_dates, algo_config)
            performance_score1 = perf_result1['radar_value']
    else:
        performance_score1 = 0

    # 学习能力（简化）
    current_violations = len(violations_list)
    learning_result1 = calculate_learning_ability_new(current_violations, None, 1.0, algo_config)
    learning_score1 = learning_result1['learning_score']

    # 稳定度（使用 calculate_stability_for_employee）
    stability_result1 = calculate_stability_for_employee(
        emp_name, start_date, end_date, algo_config, cur, safety_score_for_tip=safety_score1
    )
    stability_score1 = stability_result1.get('stability_score', 50)

    comprehensive1 = round(
        performance_score1 * score_weights['performance'] +
        safety_score1 * score_weights['safety'] +
        training_score1 * score_weights['training'] +
        stability_score1 * score_weights['stability'] +
        learning_score1 * score_weights['learning'],
        1
    )

    print(f"  绩效: {performance_score1:.1f}")
    print(f"  安全: {safety_score1:.1f}")
    print(f"  培训: {training_score1:.1f}")
    print(f"  稳定度: {stability_score1:.1f}")
    print(f"  学习能力: {learning_score1:.1f}")
    print(f"  综合分: {comprehensive1:.1f}")

    # ========== 方式2: 完整版（类似api_comprehensive_profile） ==========
    print(f"\n【方式2: 完整版计算（类似详情页）】")

    # 稳定度（直接使用 calculate_stability_score_new，并计算 monthly_comprehensive_scores）
    stability_window_start, stability_window_end = _resolve_stability_window(start_date, end_date, algo_config)
    stability_window_months = _month_range(stability_window_start, stability_window_end)
    last_12_start = _month_shift(stability_window_end, -11)
    stability_query_start = (
        stability_window_start
        if _month_index(stability_window_start) <= _month_index(last_12_start)
        else last_12_start
    )

    violations_by_month = _load_monthly_safety_violations(cur, emp_name, stability_query_start, stability_window_end)
    monthly_safety_scores, monthly_issue_counts = _build_monthly_safety_scores(
        violations_by_month, stability_window_months, algo_config
    )
    issue_counts_last_12 = [
        len(violations_by_month.get(m, []))
        for m in _month_range(last_12_start, stability_window_end)
    ]

    # 计算月度综合分（用于CV对比提示）
    monthly_comprehensive_scores = {}
    # 简化：不计算月度综合分，因为这只影响提示信息

    stability_result2 = calculate_stability_score_new(
        window_months=stability_window_months,
        monthly_safety_scores=monthly_safety_scores,
        monthly_issue_counts=monthly_issue_counts,
        issue_counts_last_12=issue_counts_last_12,
        monthly_comprehensive_scores=monthly_comprehensive_scores,
        safety_score_for_tip=safety_score1,
        config=algo_config
    )
    stability_score2 = stability_result2.get('stability_score', 50)

    comprehensive2 = round(
        performance_score1 * score_weights['performance'] +
        safety_score1 * score_weights['safety'] +
        training_score1 * score_weights['training'] +
        stability_score2 * score_weights['stability'] +
        learning_score1 * score_weights['learning'],
        1
    )

    print(f"  绩效: {performance_score1:.1f}")
    print(f"  安全: {safety_score1:.1f}")
    print(f"  培训: {training_score1:.1f}")
    print(f"  稳定度: {stability_score2:.1f}")
    print(f"  学习能力: {learning_score1:.1f}")
    print(f"  综合分: {comprehensive2:.1f}")

    # ========== 差异分析 ==========
    print(f"\n【差异分析】")
    diff = abs(stability_score1 - stability_score2)
    if diff > 0.01:
        print(f"  ⚠️ 稳定度差异: {stability_score1:.1f} vs {stability_score2:.1f} (差: {diff:.2f})")
    else:
        print(f"  ✅ 稳定度一致: {stability_score1:.1f}")

    comprehensive_diff = abs(comprehensive1 - comprehensive2)
    if comprehensive_diff > 0.01:
        print(f"  ⚠️ 综合分差异: {comprehensive1:.1f} vs {comprehensive2:.1f} (差: {comprehensive_diff:.2f})")
    else:
        print(f"  ✅ 综合分一致: {comprehensive1:.1f}")


if __name__ == '__main__':
    with app.app_context():
        # 可以修改这里的员工号和日期
        emp_no = input("请输入要检查的员工号（如 EMP001）: ").strip()
        if not emp_no:
            print("未输入员工号，退出")
            sys.exit(1)

        compare_scores(emp_no)
