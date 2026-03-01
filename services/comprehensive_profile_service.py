#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合能力画像 Service

将 routes_ai.py 中 api_comprehensive_profile 的业务逻辑抽取到此处，
使 PPT 导出等内部调用无需通过 test_client 发 HTTP 请求。
"""
import calendar
import logging
from datetime import datetime, timedelta

from models.database import get_db
from services.algorithm_config_service import AlgorithmConfigService
from services.domain.personnel_algo import (
    calculate_performance_score_monthly,
    calculate_performance_score_period,
    calculate_safety_score_dual_track,
    calculate_training_score_with_penalty,
)
from services.domain.safety_utils import extract_score_from_assessment

logger = logging.getLogger('banzu')


def _calculate_years_from_date(d):
    """计算从某个日期到现在的年数"""
    if d is None:
        return None
    try:
        if isinstance(d, str):
            d = datetime.strptime(d, '%Y-%m-%d')
        delta = datetime.now() - datetime(d.year, d.month, d.day)
        return round(delta.days / 365.25, 1)
    except Exception:
        return None


def _format_date(d):
    """格式化日期为字符串"""
    if d is None:
        return None
    if isinstance(d, str):
        return d
    if hasattr(d, 'strftime'):
        return d.strftime('%Y-%m-%d')
    return str(d)


class ComprehensiveProfileService:
    """综合能力画像核心计算服务（无 Flask 上下文依赖）"""

    @staticmethod
    def get_profile(emp_no: str, start_date: str = None, end_date: str = None) -> dict:
        """
        获取个人综合能力画像数据。

        Args:
            emp_no: 员工编号
            start_date: 开始日期 (YYYY-MM-DD 格式)，默认当月
            end_date: 结束日期 (YYYY-MM-DD 格式)，默认当月

        Returns:
            dict: 综合画像数据（与原 API 返回格式一致）
            如果员工不存在返回 None
        """
        # 导入稳定性相关函数（P1.2：直接从 service 领域层导入，不再反向依赖 Blueprint）
        from services.domain.personnel_algo import (
            calculate_learning_ability_longterm,
            calculate_learning_ability_new,
            calculate_stability_score_new,
            _month_index, _month_shift, _month_range,
            _resolve_stability_window,
            _load_monthly_safety_violations,
            _build_monthly_safety_scores,
        )

        # 读取算法配置
        algo_config = AlgorithmConfigService.get_active_config()
        score_weights = algo_config['comprehensive']['score_weights']

        conn = get_db()
        cur = conn.cursor()

        # 1. 获取员工基本信息（含 id，用于 employee_id 关联）
        cur.execute("""
            SELECT
                id, name, department_id, position, education, entry_date,
                birth_date, work_start_date, certification_date, solo_driving_date
            FROM employees
            WHERE emp_no = %s
        """, (emp_no,))
        employee = cur.fetchone()

        if not employee:
            return None

        emp_id = employee['id']
        emp_name = employee['name']
        dept_id = employee['department_id']
        position = employee['position']
        education = employee['education']
        entry_date = employee['entry_date']
        work_start_date = employee['work_start_date']
        cert_date = employee['certification_date']
        solo_date = employee['solo_driving_date']

        # 计算各项年限
        working_years = _calculate_years_from_date(work_start_date)
        tenure_years = _calculate_years_from_date(entry_date)
        cert_years = _calculate_years_from_date(cert_date)
        solo_years = _calculate_years_from_date(solo_date)

        # 日期处理：接收 YYYY-MM-DD，衍生月份变量
        if not start_date and not end_date:
            now = datetime.now()
            last_day = calendar.monthrange(now.year, now.month)[1]
            start_date = datetime(now.year, now.month, 1).strftime('%Y-%m-%d')
            end_date = datetime(now.year, now.month, last_day).strftime('%Y-%m-%d')
        # 衍生 YYYY-MM 格式（用于绩效/学习能力/稳定性等月级分析）
        start_month_str = start_date[:7] if start_date else None
        end_month_str = end_date[:7] if end_date else None

        # 2. 培训能力分析（直接用标准日期）
        training_query = """
            SELECT score, is_qualified, is_disqualified, training_date
            FROM training_records WHERE emp_no = %s
        """
        training_params = [emp_no]

        if start_date:
            training_query += " AND training_date >= %s"
            training_params.append(start_date)
        if end_date:
            training_query += " AND training_date <= %s"
            training_params.append(end_date)

        training_query += " ORDER BY training_date ASC"
        cur.execute(training_query, training_params)
        training_records = cur.fetchall()

        # 计算统计周期天数（直接从标准日期计算）
        if start_date and end_date and start_month_str == end_month_str:
            duration_days = 30
        elif start_date and end_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                duration_days = max(1, (end_dt - start_dt).days + 1)
            except Exception:
                duration_days = 30
        else:
            duration_days = 30

        training_result = calculate_training_score_with_penalty(
            training_records, duration_days, cert_years, algo_config
        )
        training_score = training_result['radar_score']
        training_status_color = training_result['status_color']
        training_alert_tag = training_result['alert_tag']
        training_original_score = training_result['original_score']
        training_penalty_coeff = training_result['penalty_coefficient']
        total_training_count = training_result['stats']['total_ops']
        training_fail_count = training_result['stats']['fail_count']

        # 3. 安全能力分析（直接用标准日期）
        # [4B] employee_id 主路径，inspected_person 仅历史兼容 fallback
        safety_query = """
            SELECT inspection_date, assessment, inspected_person, rectifier, employee_id
            FROM safety_inspection_records
            WHERE (
                (employee_id = %s)
                OR (employee_id IS NULL AND inspected_person = %s)
                OR rectifier = %s
            )
        """
        safety_params = [emp_id, emp_name, emp_name]

        if start_date:
            safety_query += " AND inspection_date >= %s"
            safety_params.append(start_date)
        if end_date:
            safety_query += " AND inspection_date <= %s"
            safety_params.append(end_date)

        safety_query += " ORDER BY inspection_date ASC"
        cur.execute(safety_query, safety_params)
        safety_rows = cur.fetchall()

        violations_list = []
        safety_as_inspector = 0
        safety_as_rectifier = 0

        for row in safety_rows:
            assessment = row['assessment']
            rectifier = row['rectifier']
            # [4B] employee_id 主路径：优先用 employee_id 判断是否为本人被检查记录
            # [4B-FALLBACK] inspected_person 仅历史兼容
            is_inspected = (row['employee_id'] == emp_id) if row['employee_id'] else (row['inspected_person'] == emp_name)
            score = extract_score_from_assessment(assessment)
            if is_inspected and score > 0:
                violations_list.append(float(score))
            if is_inspected:
                safety_as_inspector += 1
            if rectifier == emp_name:
                safety_as_rectifier += 1

        # 统计周期月数
        months_active = 1
        if start_date and end_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                months_active = max(1, int((end_dt - start_dt).days / 30) + 1)
            except Exception:
                months_active = 1
        elif start_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                months_active = max(1, int((datetime.now() - start_dt).days / 30) + 1)
            except Exception:
                months_active = 1
        elif entry_date:
            try:
                entry = datetime.strptime(str(entry_date)[:10], '%Y-%m-%d')
                months_active = max(1, int((datetime.now() - entry).days / 30))
            except Exception:
                months_active = 1

        safety_result = calculate_safety_score_dual_track(violations_list, months_active, algo_config)
        safety_score = safety_result['final_score']
        safety_status_color = safety_result['status_color']
        safety_alert_tag = safety_result['alert_tag']
        safety_violations = len(violations_list)
        safety_total_score = sum(violations_list)

        # 4. 绩效能力分析（用 YYYY-MM 格式查询 year/month 列）
        is_monthly = (start_month_str == end_month_str) if start_month_str and end_month_str else True

        perf_query = """
            SELECT score, grade, year, month
            FROM performance_records WHERE emp_no = %s
        """
        perf_params = [emp_no]

        if start_month_str:
            s_year, s_month = map(int, start_month_str.split('-'))
            perf_query += " AND (year > %s OR (year = %s AND month >= %s))"
            perf_params.extend([s_year, s_year, s_month])
        if end_month_str:
            e_year, e_month = map(int, end_month_str.split('-'))
            perf_query += " AND (year < %s OR (year = %s AND month <= %s))"
            perf_params.extend([e_year, e_year, e_month])

        perf_query += " ORDER BY year, month"
        cur.execute(perf_query, perf_params)
        perf_rows = cur.fetchall()

        if perf_rows:
            if is_monthly and len(perf_rows) == 1:
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
                grade_list = [row['grade'] if row['grade'] else 'B+' for row in perf_rows]
                grade_dates = [f"{row['year']}-{row['month']:02d}" for row in perf_rows]
                perf_result = calculate_performance_score_period(grade_list, grade_dates, algo_config)
                performance_score = perf_result['radar_value']
                performance_status_color = perf_result['status_color']
                performance_alert_tag = perf_result['alert_tag']
                performance_display_label = perf_result['display_label']
                performance_mode = 'PERIOD'
            performance_count = len(perf_rows)
        else:
            performance_score = 0
            performance_count = 0
            performance_status_color = 'GREEN'
            performance_alert_tag = '暂无数据'
            performance_display_label = '暂无数据'
            performance_mode = 'MONTHLY'

        # 5. 学习能力评估
        current_violations = 0
        previous_violations = None
        group_avg_violations = 1.0

        is_long_term = start_date and end_date and start_date != end_date
        learning_result = None

        if is_long_term:
            try:
                monthly_counts = {}
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date[:7] + '-01', '%Y-%m-%d')

                pre_period_month = (start_dt.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
                pre_period_count = 0
                try:
                    cur.execute("""
                        SELECT assessment FROM safety_inspection_records
                        WHERE (employee_id = %s OR (employee_id IS NULL AND inspected_person = %s))
                        AND DATE_FORMAT(inspection_date, '%%Y-%%m') = %s
                    """, [emp_id, emp_name, pre_period_month])
                    pre_rows = cur.fetchall()
                    pre_period_count = sum(
                        1 for r in pre_rows if extract_score_from_assessment(r['assessment']) > 0
                    )
                except Exception:
                    pre_period_count = None

                curr_dt = start_dt
                months_seq = []
                while curr_dt <= end_dt:
                    m_str = curr_dt.strftime('%Y-%m')
                    monthly_counts[m_str] = 0
                    months_seq.append(m_str)
                    curr_dt = (curr_dt.replace(day=1) + timedelta(days=32)).replace(day=1)

                for row in safety_rows:
                    # [4B] employee_id 主路径：优先用 employee_id 判断
                    is_inspected = (row['employee_id'] == emp_id) if row.get('employee_id') else (row['inspected_person'] == emp_name)
                    if is_inspected and extract_score_from_assessment(row['assessment']) > 0:
                        insp_date = row['inspection_date']
                        m_str = insp_date.strftime('%Y-%m') if hasattr(insp_date, 'strftime') else str(insp_date)[:7]
                        if m_str in monthly_counts:
                            monthly_counts[m_str] += 1

                score_list = [monthly_counts[m] for m in months_seq]

                period_group_avg = 1.0
                if dept_id:
                    # [4B] employee_id 主路径，inspected_person 仅历史兼容 fallback
                    try:
                        cur.execute("""
                            SELECT COUNT(*) / COUNT(DISTINCT e.id) / %s as avg_viol
                            FROM safety_inspection_records s
                            JOIN employees e ON s.employee_id = e.id
                            WHERE e.department_id = %s
                            AND DATE_FORMAT(s.inspection_date, '%%Y-%%m') >= %s
                            AND DATE_FORMAT(s.inspection_date, '%%Y-%%m') <= %s
                        """, [max(1, len(months_seq)), dept_id, start_month_str, end_month_str])
                        avg_res = cur.fetchone()
                        if avg_res and avg_res['avg_viol']:
                            period_group_avg = float(avg_res['avg_viol'])
                            group_avg_violations = period_group_avg
                    except Exception:
                        pass

                learning_result = calculate_learning_ability_longterm(
                    score_list=score_list,
                    config=algo_config,
                    group_avg=period_group_avg,
                    initial_prev_viol=pre_period_count
                )

                if learning_result['risk_level'] == 'SAFE':
                    learning_result['trend_type'] = 'safe'
                elif learning_result['risk_level'] in ['HIGH_RISK', 'PRE_ACCIDENT']:
                    learning_result['trend_type'] = 'deterioration'
                elif learning_result['risk_level'] == 'WATCH_LIST':
                    learning_result['trend_type'] = 'yellow_alert'
                else:
                    learning_result['trend_type'] = 'fluctuation'

                current_violations = monthly_counts[months_seq[-1]]
                if len(months_seq) >= 2:
                    previous_violations = monthly_counts[months_seq[-2]]
                else:
                    previous_violations = pre_period_count

                monthly_scores = [0] * len(months_seq)

            except Exception as e:
                logger.error(f": 长周期学习能力计算异常: {e}")
                is_long_term = False

        if not learning_result:
            if end_date:
                try:
                    end_target = end_month_str
                    current_violations = sum(
                        1 for r in safety_rows
                        # [4B] employee_id 主路径：优先用 employee_id 判断
                        if ((r.get('employee_id') == emp_id) if r.get('employee_id') else (r['inspected_person'] == emp_name))
                        and r['inspection_date'].strftime('%Y-%m') == end_target
                        and extract_score_from_assessment(r['assessment']) > 0
                    )
                except Exception:
                    current_violations = len(violations_list)
            else:
                current_violations = len(violations_list)

            if start_date:
                try:
                    current_dt = datetime.strptime(start_date, '%Y-%m-%d')
                    prev_dt = current_dt.replace(day=1) - timedelta(days=1)
                    prev_month = prev_dt.strftime('%Y-%m')
                    # [4B] employee_id 主路径，inspected_person 仅历史兼容 fallback
                    cur.execute("""
                        SELECT assessment FROM safety_inspection_records
                        WHERE (employee_id = %s OR (employee_id IS NULL AND inspected_person = %s))
                        AND DATE_FORMAT(inspection_date, '%%Y-%%m') = %s
                    """, [emp_id, emp_name, prev_month])
                    prev_rows = cur.fetchall()
                    previous_violations = sum(
                        1 for r in prev_rows if extract_score_from_assessment(r['assessment']) > 0
                    )
                except Exception:
                    previous_violations = None

            if dept_id and start_date:
                try:
                    cur.execute("""
                        SELECT COUNT(*) / COUNT(DISTINCT e.id) as avg_viol
                        FROM safety_inspection_records s
                        JOIN employees e ON s.employee_id = e.id
                        WHERE e.department_id = %s
                        AND DATE_FORMAT(s.inspection_date, '%%Y-%%m') = %s
                    """, [dept_id, start_month_str])
                    avg_result = cur.fetchone()
                    if avg_result and avg_result['avg_viol']:
                        group_avg_violations = float(avg_result['avg_viol'])
                except Exception:
                    pass

            learning_result = calculate_learning_ability_new(
                current_violations=current_violations,
                previous_violations=previous_violations,
                group_avg_violations=group_avg_violations,
                config=algo_config
            )

        learning_score = learning_result['learning_score']
        learning_status_color = learning_result['status_color']
        learning_alert_tag = learning_result['alert_tag']

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

        learning_warning_line = learning_result.get('warning_line', 0)
        learning_critical_line = learning_result.get('critical_line', 0)

        if 'monthly_scores' in locals() and monthly_scores:
            learning_months = len(monthly_scores)
        elif 'months' in learning_result:
            learning_months = learning_result['months']
        else:
            learning_months = 1

        # 6. 稳定性评估
        stability_window_start, stability_window_end = _resolve_stability_window(
            start_month_str, end_month_str, algo_config
        )
        stability_window_months = _month_range(stability_window_start, stability_window_end)
        last_12_start = _month_shift(stability_window_end, -11)
        stability_query_start = (
            stability_window_start
            if _month_index(stability_window_start) <= _month_index(last_12_start)
            else last_12_start
        )

        violations_by_month = _load_monthly_safety_violations(
            cur, emp_id, emp_name, stability_query_start, stability_window_end
        )
        monthly_safety_scores, monthly_issue_counts = _build_monthly_safety_scores(
            violations_by_month, stability_window_months, algo_config
        )
        issue_counts_last_12 = [
            len(violations_by_month.get(m, []))
            for m in _month_range(last_12_start, stability_window_end)
        ]

        monthly_comprehensive_scores = {}
        if stability_window_months:
            perf_scores_by_month = {}
            train_scores_by_month = {}

            perf_start_year, perf_start_month = map(int, stability_window_months[0].split('-'))
            perf_end_year, perf_end_month = map(int, stability_window_months[-1].split('-'))

            cur.execute("""
                SELECT score, grade, year, month
                FROM performance_records WHERE emp_no = %s
                AND (year > %s OR (year = %s AND month >= %s))
                AND (year < %s OR (year = %s AND month <= %s))
            """, [emp_no, perf_start_year, perf_start_year, perf_start_month,
                  perf_end_year, perf_end_year, perf_end_month])
            perf_rows_window = cur.fetchall()

            for row in perf_rows_window:
                m_str = f"{int(row['year']):04d}-{int(row['month']):02d}"
                raw_s = float(row['score']) if row['score'] else 95
                g = row['grade'] if row['grade'] else 'B+'
                ps = calculate_performance_score_monthly(g, raw_s, algo_config)['radar_value']
                perf_scores_by_month.setdefault(m_str, []).append(ps)

            for m_str, scores in perf_scores_by_month.items():
                if scores:
                    perf_scores_by_month[m_str] = sum(scores) / len(scores)

            train_start_date = f"{stability_window_months[0]}-01"
            train_end_date = f"{_month_shift(stability_window_months[-1], 1)}-01"
            cur.execute("""
                SELECT score, is_qualified, is_disqualified, training_date
                FROM training_records WHERE emp_no = %s
                AND training_date >= %s AND training_date < %s
            """, [emp_no, train_start_date, train_end_date])
            train_rows_window = cur.fetchall()

            train_by_month = {}
            for row in train_rows_window:
                t_date = row['training_date']
                m_str = t_date.strftime('%Y-%m') if hasattr(t_date, 'strftime') else str(t_date)[:7]
                train_by_month.setdefault(m_str, []).append(row)

            for m_str, records in train_by_month.items():
                if records:
                    ts = calculate_training_score_with_penalty(
                        records, 30, cert_years, algo_config
                    )['radar_score']
                    train_scores_by_month[m_str] = ts

            from services.domain.personnel_algo import calculate_stability_score_new as calc_stab
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

        from services.domain.personnel_algo import calculate_stability_score_new as calc_stability_new
        stability_result = calc_stability_new(
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

        # 7. 综合能力分数
        comprehensive_score = round(
            performance_score * score_weights['performance'] +
            safety_score * score_weights['safety'] +
            training_score * score_weights['training'] +
            stability_score * score_weights['stability'] +
            learning_score * score_weights['learning'],
            1
        )

        return {
            'employee': {
                'emp_no': emp_no,
                'name': emp_name,
                'position': position,
                'education': education,
                'entry_date': _format_date(entry_date)
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
                'previous_violations': previous_violations if previous_violations is not None else -1,
                'group_avg': round(group_avg_violations, 1),
                'warning_line': learning_warning_line,
                'critical_line': learning_critical_line,
                'months': learning_months,
                'risk_level': learning_result.get('risk_level', 'UNKNOWN'),
                'inertia_penalty_rate': learning_result.get('inertia_penalty_rate', 0),
                'max_consecutive_danger': learning_result.get('max_consecutive_danger', 0),
                'base_score': learning_result.get('base_score', 0),
                'has_meltdown': learning_result.get('has_meltdown', False),
                'zone': learning_result.get('zone', 'UNKNOWN'),
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
        }
