#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""人员管理 - AI 诊断与风险挖掘路由"""
from flask import render_template, request, redirect, url_for, flash, jsonify, send_file, session, current_app

from config.settings import APP_TITLE, EXPORT_DIR
from models.database import get_db, close_db, get_year_month_concat
from ..decorators import login_required, manager_required
from ..helpers import (
    current_user_id, require_user_id, get_accessible_department_ids,
    get_accessible_departments, calculate_years_from_date, get_user_department,
    validate_employee_access, log_import_operation
)
from . import personnel_bp
from . import (
    list_personnel, get_personnel, _serialize_person,
    _parse_date_string, _normalize_date_to_str,
    _calculate_age, _calculate_years_since,
    calculate_learning_ability_monthly, calculate_learning_ability_longterm,
    calculate_stability_score, calculate_stability_for_employee,
    calculate_stability_score_new, calculate_stability_period_aggregated,
    calculate_inertia_penalty, calculate_learning_ability_new,
    _month_index, _month_shift, _month_range, _resolve_stability_window,
    _load_monthly_safety_violations, _build_monthly_safety_scores,
)
from services.domain.personnel_algo import (
    calculate_performance_score_monthly,
    calculate_performance_score_period,
    calculate_safety_score_dual_track,
    calculate_training_score_with_penalty,
)
from services.domain.safety_utils import extract_score_from_assessment
import json
import re
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from flask import g

@personnel_bp.route('/api/comprehensive-profile/<emp_no>')
@login_required
def api_comprehensive_profile(emp_no):
    """API: 获取个人综合能力画像（人员+培训+安全+绩效）"""
    from datetime import datetime, timedelta
    from services.domain.safety_utils import extract_score_from_assessment

    # 读取算法配置
    from services.algorithm_config_service import AlgorithmConfigService
    algo_config = AlgorithmConfigService.get_active_config()
    score_weights = algo_config['comprehensive']['score_weights']

    conn = get_db()
    cur = conn.cursor()

    # 1. 获取员工基本信息
    cur.execute("""
        SELECT
            name, department_id, position, education, entry_date,
            birth_date, work_start_date, certification_date, solo_driving_date
        FROM employees
        WHERE emp_no = %s
    """, (emp_no,))
    employee = cur.fetchone()

    if not employee:
        return jsonify({'error': '员工不存在'}), 404

    # 验证权限
    if not validate_employee_access(emp_no):
        return jsonify({'error': '无权限查看此员工'}), 403

    # DictCursor返回字典，使用字典访问方式
    emp_name = employee['name']
    dept_id = employee['department_id']
    position = employee['position']
    education = employee['education']
    entry_date = employee['entry_date']
    birth_date = employee['birth_date']
    work_start_date = employee['work_start_date']
    cert_date = employee['certification_date']
    solo_date = employee['solo_driving_date']

    # 计算各项年限
    working_years = calculate_years_from_date(work_start_date) if work_start_date else None
    tenure_years = calculate_years_from_date(entry_date) if entry_date else None
    cert_years = calculate_years_from_date(cert_date) if cert_date else None
    solo_years = calculate_years_from_date(solo_date) if solo_date else None

    # 获取日期筛选参数（如果有）
    start_date = request.args.get('start_date')  # 格式：YYYY-MM
    end_date = request.args.get('end_date')      # 格式：YYYY-MM

    # DEBUG: 打印接收到的日期参数
    current_app.logger.debug(f" [comprehensive-profile]: 原始参数 - start_date='{start_date}', end_date='{end_date}'")
    current_app.logger.debug(f" [comprehensive-profile]: 参数类型 - start_date type={type(start_date)}, end_date type={type(end_date)}")
    current_app.logger.debug(f" [comprehensive-profile]: 参数布尔值 - bool(start_date)={bool(start_date)}, bool(end_date)={bool(end_date)}")

    # 如果没有指定日期，默认使用当月
    if not start_date and not end_date:
        current_month = datetime.now().strftime('%Y-%m')
        start_date = current_month
        end_date = current_month
        current_app.logger.debug(f" [comprehensive-profile]: 无日期参数，使用默认当月: {current_month}")

    # 2. 培训能力分析（使用高级评分算法 - 包含毒性惩罚和动态年化）
    training_query = """
        SELECT
            score,
            is_qualified,
            is_disqualified,
            training_date
        FROM training_records
        WHERE emp_no = %s
    """
    training_params = [emp_no]

    if start_date:
        training_query += " AND training_date >= %s"
        training_params.append(start_date + '-01')

    if end_date:
        # 计算下个月1号作为上限（开区间 <）
        try:
            curr = datetime.strptime(end_date + '-01', '%Y-%m-%d')
            # 简单处理：加上32天然后设为1号
            next_month = (curr + timedelta(days=32)).replace(day=1)
            training_query += " AND training_date < %s"
            training_params.append(next_month.strftime('%Y-%m-%d'))
        except Exception:
            # 回退方案
            training_query += " AND training_date <= %s"
            training_params.append(end_date + '-31')

    training_query += " ORDER BY training_date ASC"
    cur.execute(training_query, training_params)
    training_records = cur.fetchall()

    # 计算统计周期天数
    if start_date and end_date and start_date == end_date:
        # 单月统计，按30天计算
        duration_days = 30
    elif start_date and end_date:
        # 多月统计，计算实际天数
        try:
            start_dt = datetime.strptime(start_date + '-01', '%Y-%m-%d')
            end_dt = datetime.strptime(end_date + '-01', '%Y-%m-%d')
            # 计算到月末
            import calendar
            end_year, end_month = int(end_date.split('-')[0]), int(end_date.split('-')[1])
            last_day = calendar.monthrange(end_year, end_month)[1]
            end_dt = end_dt.replace(day=last_day)
            duration_days = max(1, (end_dt - start_dt).days + 1)
        except Exception:
            duration_days = 30
    else:
        # 默认按30天计算
        duration_days = 30

    # 使用新的评分算法
    training_result = calculate_training_score_with_penalty(training_records, duration_days, cert_years, algo_config)
    training_score = training_result['radar_score']
    training_status_color = training_result['status_color']
    training_alert_tag = training_result['alert_tag']
    training_original_score = training_result['original_score']
    training_penalty_coeff = training_result['penalty_coefficient']
    total_training_count = training_result['stats']['total_ops']
    training_fail_count = training_result['stats']['fail_count']

    # 3. 安全能力分析（使用双轨评分模型，应用日期筛选）
    safety_query = """
        SELECT
            inspection_date,
            assessment,
            inspected_person,
            rectifier
        FROM safety_inspection_records
        WHERE (inspected_person = %s OR rectifier = %s)
    """
    safety_params = [emp_name, emp_name]

    if start_date:
        safety_query += " AND inspection_date >= %s"
        safety_params.append(start_date + '-01')

    if end_date:
        try:
            curr = datetime.strptime(end_date + '-01', '%Y-%m-%d')
            next_month = (curr + timedelta(days=32)).replace(day=1)
            safety_query += " AND inspection_date < %s"
            safety_params.append(next_month.strftime('%Y-%m-%d'))
        except Exception:
            safety_query += " AND inspection_date <= %s"
            safety_params.append(end_date + '-31')

    safety_query += " ORDER BY inspection_date ASC"
    cur.execute(safety_query, safety_params)
    
    safety_rows = cur.fetchall()

    violations_list = []
    safety_as_inspector = 0
    safety_as_rectifier = 0

    for row in safety_rows:
        assessment = row['assessment']
        inspected = row['inspected_person']
        rectifier = row['rectifier']
        score = extract_score_from_assessment(assessment)

        if inspected == emp_name and score > 0:
            violations_list.append(float(score))

        if inspected == emp_name:
            safety_as_inspector += 1
        if rectifier == emp_name:
            safety_as_rectifier += 1

    # 计算统计周期月数（使用筛选日期范围的月数）
    months_active = 1
    if start_date and end_date:
        # 如果指定了日期范围，计算该范围的月数
        try:
            start_dt = datetime.strptime(start_date + '-01', '%Y-%m-%d')
            end_dt = datetime.strptime(end_date + '-01', '%Y-%m-%d')
            months_active = max(1, int((end_dt - start_dt).days / 30) + 1)
        except Exception:
            months_active = 1
    elif start_date:
        # 只指定了开始日期，从开始日期到现在
        try:
            start_dt = datetime.strptime(start_date + '-01', '%Y-%m-%d')
            months_active = max(1, int((datetime.now() - start_dt).days / 30) + 1)
        except Exception:
            months_active = 1
    elif entry_date:
        # 没有日期筛选，使用入职以来的月数
        try:
            entry = datetime.strptime(entry_date, '%Y-%m-%d')
            months_active = max(1, int((datetime.now() - entry).days / 30))
        except Exception:
            months_active = 1

    # 使用双轨评分模型
    safety_result = calculate_safety_score_dual_track(violations_list, months_active, algo_config)
    safety_score = safety_result['final_score']
    safety_status_color = safety_result['status_color']
    safety_alert_tag = safety_result['alert_tag']
    safety_violations = len(violations_list)
    safety_total_score = sum(violations_list)

    # 4. 绩效能力分析（使用双算法系统）
    # 判断是月度还是周期（使用前面已经设置的 start_date 和 end_date）
    is_monthly = (start_date == end_date) if start_date and end_date else True
    current_app.logger.debug(f" [comprehensive-profile]: is_monthly={is_monthly}, start_date={start_date}, end_date={end_date}")

    # 构建绩效查询
    perf_query = """
        SELECT score, grade, year, month
        FROM performance_records
        WHERE emp_no = %s
    """
    perf_params = [emp_no]

    if start_date:
        s_year, s_month = map(int, start_date.split('-'))
        # 性能优化: 避免函数索引失效,使用元组比较 (year, month) >= (s_year, s_month)
        perf_query += " AND (year > %s OR (year = %s AND month >= %s))"
        perf_params.extend([s_year, s_year, s_month])

    if end_date:
        e_year, e_month = map(int, end_date.split('-'))
        perf_query += " AND (year < %s OR (year = %s AND month <= %s))"
        perf_params.extend([e_year, e_year, e_month])

    perf_query += " ORDER BY year, month"
    cur.execute(perf_query, perf_params)
    perf_rows = cur.fetchall()

    if perf_rows:
        if is_monthly and len(perf_rows) == 1:
            # 月度快照算法
            perf_row = perf_rows[0]
            raw_score = float(perf_row['score']) if perf_row['score'] else 95
            grade = perf_row['grade'] if perf_row['grade'] else 'B+'
            perf_result = calculate_performance_score_monthly(grade, raw_score, algo_config)
            performance_score = perf_result['radar_value']
            performance_status_color = perf_result['status_color']
            performance_alert_tag = perf_result['alert_tag']
            performance_display_label = perf_result['display_label']
            performance_mode = 'MONTHLY'
        else:
            # 周期加权算法（带时间衰减）
            grade_list = [row['grade'] if row['grade'] else 'B+' for row in perf_rows]
            grade_dates = [f"{row['year']}-{row['month']:02d}" for row in perf_rows]  # 构建日期列表
            perf_result = calculate_performance_score_period(grade_list, grade_dates, algo_config)
            performance_score = perf_result['radar_value']
            performance_status_color = perf_result['status_color']
            performance_alert_tag = perf_result['alert_tag']
            performance_display_label = perf_result['display_label']
            performance_mode = 'PERIOD'
        performance_count = len(perf_rows)
    else:
        # 没有绩效数据
        performance_score = 0
        performance_count = 0
        performance_status_color = 'GREEN'
        performance_alert_tag = '暂无数据'
        performance_display_label = '暂无数据'
        performance_mode = 'MONTHLY'

    # 计算三维综合分（用于返回数据）
    current_comprehensive = (
        performance_score * score_weights.get('performance', 0.35) +
        safety_score * score_weights.get('safety', 0.30) +
        training_score * score_weights.get('training', 0.20)
    )
    
    # 5. 学习能力评估（新版：基于违规数量变化趋势）
    current_violations = 0
    previous_violations = None
    
    # 判断是否为长周期（跨月）
    is_long_term = False
    if start_date and end_date and start_date != end_date:
        is_long_term = True
        
    learning_result = None
    
    if is_long_term:
        # 长周期模式：V5.0 风险惯性模型
        try:
            # 1. 初始化每月计数
            monthly_counts = {}
            start_dt = datetime.strptime(start_date + '-01', '%Y-%m-%d')
            end_dt = datetime.strptime(end_date + '-01', '%Y-%m-%d')
            
            # 预先查询周期前一个月的数据
            pre_period_month = (start_dt.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
            pre_period_count = 0
            try:
                cur.execute("""
                    SELECT assessment FROM safety_inspection_records 
                    WHERE inspected_person = %s AND DATE_FORMAT(inspection_date, '%%Y-%%m') = %s
                """, [emp_name, pre_period_month])
                pre_rows = cur.fetchall()
                pre_period_count = sum(1 for r in pre_rows if extract_score_from_assessment(r['assessment']) > 0)
            except Exception:
                pre_period_count = None

            curr = start_dt
            months_seq = []
            while curr <= end_dt:
                m_str = curr.strftime('%Y-%m')
                monthly_counts[m_str] = 0
                months_seq.append(m_str)
                curr = (curr.replace(day=1) + timedelta(days=32)).replace(day=1)
            
            # 2. 填充数据
            for row in safety_rows:
                if row['inspected_person'] == emp_name and extract_score_from_assessment(row['assessment']) > 0:
                    insp_date = row['inspection_date']
                    m_str = insp_date.strftime('%Y-%m') if hasattr(insp_date, 'strftime') else str(insp_date)[:7]
                    
                    if m_str in monthly_counts:
                        monthly_counts[m_str] += 1
                        
            # 3. 准备参数调用核心算法
            score_list = [monthly_counts[m] for m in months_seq]
            
            # 获取班组平均（周期整体）
            period_group_avg = 1.0 
            if dept_id:
                 try:
                    cur.execute("""
                        SELECT COUNT(*) / COUNT(DISTINCT e.name) / %s as avg_viol
                        FROM safety_inspection_records s
                        JOIN employees e ON s.inspected_person = e.name
                        WHERE e.department_id = %s
                        AND DATE_FORMAT(s.inspection_date, '%%Y-%%m') >= %s
                        AND DATE_FORMAT(s.inspection_date, '%%Y-%%m') <= %s
                    """, [max(1, len(months_seq)), dept_id, start_date, end_date])
                    avg_res = cur.fetchone()
                    if avg_res and avg_res['avg_viol']:
                        period_group_avg = float(avg_res['avg_viol'])
                        group_avg_violations = period_group_avg  # 更新外部变量
                 except Exception:
                    pass

            # 4. 调用 calculate_learning_ability_longterm (V5.0 核心)
            # 注意：此函数已更新接受 initial_prev_viol
            learning_result = calculate_learning_ability_longterm(
                score_list=score_list,
                config=algo_config,
                group_avg=period_group_avg,
                initial_prev_viol=pre_period_count
            )
            
            # 补全部分前端需要的字段（如果 missed）
            # long-term函数返回了 risk_level, inertia_penalty_rate, max_consecutive_danger 等关键字段
            # 我们只需要补充 trend_type 供兼容旧代码逻辑判断
            if learning_result['risk_level'] == 'SAFE':
                learning_result['trend_type'] = 'safe'
            elif learning_result['risk_level'] in ['HIGH_RISK', 'PRE_ACCIDENT']:
                learning_result['trend_type'] = 'deterioration'
            elif learning_result['risk_level'] == 'WATCH_LIST':
                 learning_result['trend_type'] = 'yellow_alert'
            else:
                 learning_result['trend_type'] = 'fluctuation'
                 
            # 兼容设置
            current_violations = monthly_counts[months_seq[-1]]
            if len(months_seq) >= 2:
                previous_violations = monthly_counts[months_seq[-2]]
            else:
                previous_violations = pre_period_count
                
            monthly_scores = [0] * len(months_seq) # 标记为非空列表以触发 learning_months 计算

        except Exception as e:
            current_app.logger.error(f": 长周期学习能力计算异常: {e}")
            is_long_term = False

    if not learning_result:
        # 单月模式或降级
        # 单月模式：本月 vs 上月
        if end_date:
            try:
                # 统计end_date当月的违规数
                end_target = end_date
                # 注意：safety_rows中包含筛选范围内的数据，如果范围仅为单月，这里直接统计
                current_violations = sum(1 for r in safety_rows if r['inspected_person'] == emp_name and r['inspection_date'].strftime('%Y-%m') == end_target and extract_score_from_assessment(r['assessment']) > 0)
            except Exception:
                current_violations = len(violations_list)
        else:
            current_violations = len(violations_list)

        # 获取上月违规数
        if start_date:
            try:
                current_dt = datetime.strptime(start_date + '-01', '%Y-%m-%d')
                prev_dt = current_dt.replace(day=1) - timedelta(days=1)
                prev_month = prev_dt.strftime('%Y-%m')
                
                cur.execute("""
                    SELECT assessment FROM safety_inspection_records
                    WHERE inspected_person = %s
                    AND DATE_FORMAT(inspection_date, '%%Y-%%m') = %s
                """, [emp_name, prev_month])
                prev_rows = cur.fetchall()
                previous_violations = sum(1 for r in prev_rows if extract_score_from_assessment(r['assessment']) > 0)
            except Exception:
                previous_violations = None            

    
        # 获取班组平均违规数
        group_avg_violations = 1.0
        if dept_id and start_date:
            try:
                cur.execute("""
                    SELECT COUNT(*) / COUNT(DISTINCT e.name) as avg_viol
                    FROM safety_inspection_records s
                    JOIN employees e ON s.inspected_person = e.name
                    WHERE e.department_id = %s
                    AND DATE_FORMAT(s.inspection_date, '%%Y-%%m') = %s
                """, [dept_id, start_date])
                avg_result = cur.fetchone()
                if avg_result and avg_result['avg_viol']:
                    group_avg_violations = float(avg_result['avg_viol'])
            except Exception:
                pass
        
        # 调用新算法
        learning_result = calculate_learning_ability_new(
            current_violations=current_violations,
            previous_violations=previous_violations,
            group_avg_violations=group_avg_violations,
            config=algo_config
        )
    
    # 提取学习能力分值和详情
    learning_score = learning_result['learning_score']
    learning_status_color = learning_result['status_color']
    learning_alert_tag = learning_result['alert_tag']
    
    # [V5.0 补全] 确保 risk_level 等关键字段存在 (兼容单月/短周期模式)
    if 'risk_level' not in learning_result:
        zone = learning_result.get('zone', 'SAFE')
        if zone == 'CRITICAL':
             learning_result['risk_level'] = 'PRE_ACCIDENT'
        elif zone == 'DANGER':
             learning_result['risk_level'] = 'HIGH_RISK'
        elif zone == 'SAFE':
             learning_result['risk_level'] = 'SAFE'
        else:
             learning_result['risk_level'] = zone
             
    if 'inertia_penalty_rate' not in learning_result:
        learning_result['inertia_penalty_rate'] = 0.0
        
    if 'max_consecutive_danger' not in learning_result:
        learning_result['max_consecutive_danger'] = 0

    raw_trend_type = learning_result.get('trend_type', '未知')
    if raw_trend_type == 'high_improvement':
        learning_tier = 'improvement'
    elif raw_trend_type in ['deterioration_mild', 'meltdown']:
        learning_tier = 'deterioration'
    else:
        learning_tier = raw_trend_type
    
    # 获取新算法的详细指标
    learning_warning_line = learning_result.get('warning_line', 0)
    learning_critical_line = learning_result.get('critical_line', 0)
    
    # 尝试获取统计周期月数（如果是长周期模式）
    # 注意：在前面的代码中我们可能定义了 monthly_scores
    if 'monthly_scores' in locals() and monthly_scores:
        learning_months = len(monthly_scores)
    elif 'learning_result' in locals() and 'months' in learning_result:
        learning_months = learning_result['months']
    else:
        learning_months = 1


    # 6. 稳定性评估（波动型）
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
    if stability_window_months:
        perf_scores_by_month = {}
        train_scores_by_month = {}

        perf_start_year, perf_start_month = map(int, stability_window_months[0].split('-'))
        perf_end_year, perf_end_month = map(int, stability_window_months[-1].split('-'))

        cur.execute("""
            SELECT score, grade, year, month
            FROM performance_records
            WHERE emp_no = %s
            AND (year > %s OR (year = %s AND month >= %s))
            AND (year < %s OR (year = %s AND month <= %s))
        """, [emp_no, perf_start_year, perf_start_year, perf_start_month,
              perf_end_year, perf_end_year, perf_end_month])
        perf_rows_window = cur.fetchall()

        for row in perf_rows_window:
            m_str = f"{int(row['year']):04d}-{int(row['month']):02d}"
            raw_score = float(row['score']) if row['score'] else 95
            grade = row['grade'] if row['grade'] else 'B+'
            perf_score = calculate_performance_score_monthly(grade, raw_score, algo_config)['radar_value']
            perf_scores_by_month.setdefault(m_str, []).append(perf_score)

        for m_str, scores in perf_scores_by_month.items():
            if scores:
                perf_scores_by_month[m_str] = sum(scores) / len(scores)

        train_start_date = f"{stability_window_months[0]}-01"
        train_end_date = f"{_month_shift(stability_window_months[-1], 1)}-01"
        cur.execute("""
            SELECT score, is_qualified, is_disqualified, training_date
            FROM training_records
            WHERE emp_no = %s
            AND training_date >= %s
            AND training_date < %s
        """, [emp_no, train_start_date, train_end_date])
        train_rows_window = cur.fetchall()

        train_by_month = {}
        for row in train_rows_window:
            t_date = row['training_date']
            m_str = t_date.strftime('%Y-%m') if hasattr(t_date, 'strftime') else str(t_date)[:7]
            train_by_month.setdefault(m_str, []).append(row)

        for m_str, records in train_by_month.items():
            if records:
                train_score = calculate_training_score_with_penalty(records, 30, cert_years, algo_config)['radar_score']
                train_scores_by_month[m_str] = train_score

        for m_str in stability_window_months:
            components = {}
            if m_str in monthly_safety_scores:
                components['safety'] = monthly_safety_scores[m_str]
            if m_str in perf_scores_by_month:
                components['performance'] = perf_scores_by_month[m_str]
            if m_str in train_scores_by_month:
                components['training'] = train_scores_by_month[m_str]

            if components:
                weight_sum = 0.0
                weighted_sum = 0.0
                for key, value in components.items():
                    w = score_weights.get(key, 0)
                    weight_sum += w
                    weighted_sum += value * w
                if weight_sum > 0:
                    monthly_comprehensive_scores[m_str] = weighted_sum / weight_sum

    stability_result = calculate_stability_score_new(
        window_months=stability_window_months,
        monthly_safety_scores=monthly_safety_scores,
        monthly_issue_counts=monthly_issue_counts,
        issue_counts_last_12=issue_counts_last_12,
        monthly_comprehensive_scores=monthly_comprehensive_scores,
        safety_score_for_tip=safety_score,
        config=algo_config
    )
    stability_score = stability_result.get('stability_score', 50)
    if not isinstance(stability_score, (int, float)):
        stability_score = 50




    # 7. 计算综合能力分数（加权平均 - 使用配置权重）
    comprehensive_score = round(
        performance_score * score_weights['performance'] +
        safety_score * score_weights['safety'] +
        training_score * score_weights['training'] +
        stability_score * score_weights['stability'] +
        learning_score * score_weights['learning'],
        1
    )

    # 格式化日期为字符串（MySQL返回date对象，JSON无法直接序列化）
    def format_date(d):
        if d is None:
            return None
        if isinstance(d, str):
            return d
        if hasattr(d, 'strftime'):
            return d.strftime('%Y-%m-%d')
        return str(d)

    return jsonify({
        'employee': {
            'emp_no': emp_no,
            'name': emp_name,
            'position': position,
            'education': education,
            'entry_date': format_date(entry_date)
        },
        'scores': {
            'comprehensive': round(comprehensive_score, 1),
            'training': round(training_score, 1),
            'safety': round(safety_score, 1),
            'performance': round(performance_score, 1),
            'learning': round(learning_score, 1),
            'stability': round(stability_score, 1)
        },
        'personnel_details': {
            'working_years': round(working_years, 1) if working_years else None,
            'tenure_years': round(tenure_years, 1) if tenure_years else None,
            'certification_years': round(cert_years, 1) if cert_years else None,
            'solo_driving_years': round(solo_years, 1) if solo_years else None,
            'education': education
        },
        'safety_details': {
            'violations': safety_violations,
            'total_deduction': safety_total_score,
            'as_inspector': safety_as_inspector,
            'as_rectifier': safety_as_rectifier,
            'status_color': safety_status_color,
            'alert_tag': safety_alert_tag,
            'score_a': safety_result['score_a'],
            'score_b': safety_result['score_b'],
            'avg_freq': safety_result['avg_freq']
        },
        'statistics': {
            'total_trainings': total_training_count,
            'avg_training_score': training_score,
            'recent_trainings': len(training_records) if training_records else 0
        },
        'training_details': {
            'radar_score': training_score,
            'original_score': training_original_score,
            'penalty_coefficient': training_penalty_coeff,
            'status_color': training_status_color,
            'alert_tag': training_alert_tag,
            'total_ops': total_training_count,
            'fail_count': training_fail_count,
            'duration_days': duration_days
        },
        'performance_details': {
            'recent_avg': performance_score,
            'range': f'{"当月" if is_monthly else "统计周期"}',
            'count': performance_count,
            'status_color': performance_status_color,
            'alert_tag': performance_alert_tag,
            'display_label': performance_display_label,
            'mode': performance_mode
        },
        'learning_details': {
            'learning_score': round(learning_score, 1),
            'status_color': learning_status_color,
            'alert_tag': learning_alert_tag,
            'tier': learning_tier,
            'current_violations': current_violations,
            'previous_violations': previous_violations if previous_violations is not None else -1,  # -1表示无记录(冷启动)
            'group_avg': round(group_avg_violations, 1),
            'warning_line': learning_warning_line,
            'critical_line': learning_critical_line,
            'months': learning_months,
            # V5.0 新增字段
            'risk_level': learning_result.get('risk_level', 'UNKNOWN'),
            'inertia_penalty_rate': learning_result.get('inertia_penalty_rate', 0),
            'max_consecutive_danger': learning_result.get('max_consecutive_danger', 0),
            'base_score': learning_result.get('base_score', 0),  # 基础加权分（惯性扣减前）
            'has_meltdown': learning_result.get('has_meltdown', False),  # 是否曾触发熔断
            'zone': learning_result.get('zone', 'UNKNOWN'),  # 当前区域状态
            'slope': learning_result.get('slope', 0)
        },
        'stability_details': {
            'stability_score': round(stability_score, 1),
            'status_color': stability_result.get('status_color', 'GRAY'),
            'alert_tag': stability_result.get('alert_tag', '暂无数据'),
            'stability_label': stability_result.get('stability_label'),
            'volatility_metric': stability_result.get('volatility_metric'),
            'volatility_metric_label': stability_result.get('volatility_metric_label'),
            'volatility_value': stability_result.get('volatility_value'),
            'coverage': stability_result.get('coverage'),
            'confidence': stability_result.get('confidence'),
            'volatility_tip': stability_result.get('volatility_tip'),
            'low_level_tip': stability_result.get('low_level_tip'),
            'sample_tip': stability_result.get('sample_tip'),
            'safety_cv': stability_result.get('safety_cv'),
            'comprehensive_cv': stability_result.get('comprehensive_cv'),
            'mean_safety': stability_result.get('mean_safety')
        }
    })


@personnel_bp.route('/api/risk-mining')
@login_required
def api_risk_mining():
    """
    API: 高风险人员挖掘分析

    Query Parameters:
        start_date: 开始日期 (YYYY-MM), 默认12个月前
        end_date: 结束日期 (YYYY-MM), 默认当前月
        enable_ai: 是否启用AI诊断 (true/false), 默认true

    Returns:
        {
            high_risk_list: [...],   # 按风险分排序的员工列表
            keyword_cloud: [...],     # 关键词词云数据
            survival_curve: [...],    # 生存曲线数据
            summary: {...}            # 统计摘要
        }
    """
    try:
        from services.risk_mining_service import RiskMiningService

        # Parse parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        enable_ai = request.args.get('enable_ai', 'true').lower() == 'true'

        # 使用标准权限控制函数进行安全过滤
        from flask import g
        ctx = getattr(g, 'user_ctx', None)
        role = ctx.get('role') if ctx else session.get('role')
        department_path = None

        if role != 'admin':
            # 非管理员用户需要检查部门权限
            accessible_dept_ids = get_accessible_department_ids()

            if not accessible_dept_ids:
                # 用户没有可访问的部门，返回空结果（安全保护）
                return jsonify({
                    'success': True,
                    'high_risk_list': [],
                    'keyword_cloud': [],
                    'survival_curve': [],
                    'summary': {
                        'total_employees': 0,
                        'high_risk_count': 0,
                        'anomaly_count': 0,
                        'analysis_period': f'{start_date} ~ {end_date}' if start_date and end_date else '最近12个月'
                    },
                    'message': '您未被分配到任何部门，无法查看风险数据'
                })

            # 获取用户部门路径用于过滤
            conn = get_db()
            cur = conn.cursor()
            user_id = session.get('user_id')
            cur.execute("""
                SELECT d.path FROM users u
                JOIN departments d ON u.department_id = d.id
                WHERE u.id = %s
            """, (user_id,))
            row = cur.fetchone()
            if row:
                department_path = row['path']
            else:
                # 用户有可访问部门但没有自己的部门路径（异常情况），返回空结果
                return jsonify({
                    'success': True,
                    'high_risk_list': [],
                    'keyword_cloud': [],
                    'survival_curve': [],
                    'summary': {
                        'total_employees': 0,
                        'high_risk_count': 0,
                        'anomaly_count': 0,
                        'analysis_period': f'{start_date} ~ {end_date}' if start_date and end_date else '最近12个月'
                    },
                    'message': '您的用户账户未关联部门，无法查看风险数据'
                })

        # Perform risk analysis
        result = RiskMiningService.analyze_all(
            start_date=start_date,
            end_date=end_date,
            department_path=department_path,
            enable_ai_diagnosis=enable_ai
        )

        return jsonify({
            'success': True,
            **result
        })

    except ImportError as e:
        return jsonify({
            'success': False,
            'error': f'缺少必要的依赖库: {str(e)}。请运行 pip install pandas scikit-learn jieba lifelines httpx'
        }), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'风险分析失败: {str(e)}'
        }), 500


@personnel_bp.route('/risk-mining')
@login_required
def risk_mining_page():
    """风险挖掘分析页面"""
    return render_template('personnel_risk_mining.html', title='高风险人员挖掘')


@personnel_bp.route('/api/ai-diagnosis', methods=['POST'])
@login_required
def api_ai_diagnosis():
    """
    API: 单个员工AI诊断（带缓存机制）

    Request Body (JSON):
        emp_no: 员工工号
        name: 员工姓名
        risk_score: 风险评分
        risk_data: 风险数据（基础统计信息，详细记录由后端重新获取）
        start_date: 开始日期 (YYYY-MM 格式，用于过滤详细记录)
        end_date: 结束日期 (YYYY-MM 格式，用于过滤详细记录)

    Returns:
        {
            success: true/false,
            diagnosis: {...},  # 诊断结果
            source: "cache" | "api",  # 数据来源（节省token的关键指标）
            tokens_used: 0  # 如果命中缓存则为0
        }
    """
    try:
        from services.ai_diagnosis_service import AIDiagnosisService
        from services.risk_mining_service import RiskMiningService

        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据为空'
            }), 400

        emp_no = data.get('emp_no')
        name = data.get('name', '未知')
        risk_score = data.get('risk_score', 0)
        basic_risk_data = data.get('risk_data', {})
        # 新增：获取日期范围参数，用于过滤详细记录
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        if not emp_no:
            return jsonify({
                'success': False,
                'error': '缺少员工工号'
            }), 400

        # 检查AI是否已配置
        if not AIDiagnosisService.is_configured():
            return jsonify({
                'success': False,
                'error': 'AI未配置。请在系统设置中添加AI提供商配置。'
            }), 400

        # 关键：从数据库重新获取详细记录，确保与批量分析时的数据一致
        # 这样才能命中缓存！使用日期范围过滤，确保AI诊断的数据与用户筛选一致
        risk_data = {
            # 基础统计数据（来自前端）
            'performance_slope': basic_risk_data.get('performance_slope', 0),
            'performance_mean': basic_risk_data.get('performance_score', 0),
            'safety_count': basic_risk_data.get('safety_count', 0),
            'training_disqualified_count': basic_risk_data.get('training_disqualified_count', 0),
            'is_anomaly': basic_risk_data.get('is_anomaly', False),
            'anomaly_score': basic_risk_data.get('anomaly_score', 0),
            'risk_factors': basic_risk_data.get('risk_factors', []),
            # 详细记录（从数据库重新获取，使用日期范围过滤，与批量分析保持一致）
            'recent_violations': RiskMiningService._get_recent_violations(emp_no, 10, start_date, end_date),
            'severe_violations': RiskMiningService._get_severe_violations(emp_no, start_date, end_date),
            'failed_training': RiskMiningService._get_failed_training(emp_no, start_date, end_date)
        }

        # 调用AI诊断（内置缓存逻辑）
        result = AIDiagnosisService.diagnose_sync(
            emp_no=emp_no,
            name=name,
            risk_score=risk_score,
            risk_data=risk_data
        )

        if result.success:
            return jsonify({
                'success': True,
                'diagnosis': result.parsed_result or result.diagnosis,
                'raw_diagnosis': result.diagnosis,
                'source': result.source,  # "cache" 或 "api"
                'tokens_used': result.tokens_used or 0,
                'model_used': result.model_used,
                'provider_name': result.provider_name
            })
        else:
            return jsonify({
                'success': False,
                'error': result.error
            }), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'AI诊断失败: {str(e)}'
        }), 500
