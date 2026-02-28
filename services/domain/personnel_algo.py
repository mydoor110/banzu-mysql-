#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人员算法领域函数
从 blueprints/personnel.py 提取，供 services 和 blueprints 共同引用。
消除 services -> blueprints 的反向依赖。

提取函数：
  - calculate_performance_score_monthly
  - calculate_performance_score_period
  - calculate_safety_score_dual_track
  - calculate_training_score_with_penalty
"""
import math
from typing import Dict, List, Optional


def calculate_performance_score_monthly(grade: str, raw_score: float, config: dict = None) -> Dict:
    """
    绩效月度快照算法（参数化版本）

    Args:
        grade: 绩效等级 (A, B+, B, C, D)
        raw_score: 原始计算分 (100 + 加分 - 扣分)
        config: 算法配置（可选，默认从数据库读取）

    Returns:
        {
            'radar_value': 雷达图显示值,
            'display_label': 显示标签,
            'status_color': 状态颜色 (RED/ORANGE/GREEN),
            'alert_tag': 警示标签,
            'grade': 等级
        }
    """
    # 读取配置
    if config is None:
        from services.algorithm_config_service import AlgorithmConfigService
        config = AlgorithmConfigService.get_active_config()

    grade_coefficients = config['performance']['grade_coefficients']
    grade_ranges = config['performance']['grade_ranges']

    grade = grade.upper() if grade else 'B+'

    # 等级锁定规则（使用配置参数）
    if grade == 'D':
        radar_value = grade_ranges['D']['radar_override']  # 从配置读取
        status_color = 'RED'
        alert_tag = '⛔ 绩效不合格'
        display_label = f'D级 (系数{grade_coefficients["D"]})'
    elif grade == 'C':
        radar_value = min(max(raw_score, grade_ranges['C']['min']), grade_ranges['C']['max'])
        status_color = 'ORANGE'
        alert_tag = '⚠️ 绩效预警'
        display_label = f'C级 (系数{grade_coefficients["C"]})'
    elif grade == 'B':
        radar_value = min(max(raw_score, grade_ranges['B']['min']), grade_ranges['B']['max'])
        status_color = 'ORANGE'
        alert_tag = '⚠️ 未达基准'
        display_label = f'B级 (系数{grade_coefficients["B"]})'
    elif grade == 'B+':
        radar_value = min(max(raw_score, grade_ranges['B+']['min']), grade_ranges['B+']['max'])
        status_color = 'GREEN'
        alert_tag = '✅ 达标'
        display_label = f'B+级 (系数{grade_coefficients["B+"]})'
    elif grade == 'A':
        radar_value = min(max(raw_score, grade_ranges['A']['min']), grade_ranges['A']['max'])
        status_color = 'GREEN'
        alert_tag = '✅ 优秀'
        display_label = f'A级 (系数{grade_coefficients["A"]})'
    else:  # 默认B+
        radar_value = min(max(raw_score, grade_ranges['B+']['min']), grade_ranges['B+']['max'])
        status_color = 'GREEN'
        alert_tag = '✅ 达标'
        display_label = f'B+级 (系数{grade_coefficients["B+"]})'

    return {
        'radar_value': round(radar_value, 1),
        'display_label': display_label,
        'status_color': status_color,
        'alert_tag': alert_tag,
        'grade': grade,
        'mode': 'MONTHLY'
    }


def calculate_performance_score_period(grade_list: List[str], grade_dates: Optional[List[str]] = None, config: dict = None) -> Dict:
    """
    绩效周期加权算法（跨月、季度、年度）（参数化版本）

    新增时间衰减机制：D级和C级的影响会随时间推移而减弱

    Args:
        grade_list: 周期内所有月份的等级列表，如 ['A', 'B+', 'B', 'C']
        grade_dates: 每个等级对应的日期列表（可选），如 ['2024-01', '2024-02', ...]
                     如果提供，将启用时间衰减机制
        config: 算法配置（可选，默认从数据库读取）

    Returns:
        {
            'radar_value': 雷达图显示值,
            'display_label': 显示标签,
            'status_color': 状态颜色,
            'alert_tag': 警示标签
        }
    """
    if not grade_list:
        return {
            'radar_value': 95.0,
            'display_label': '暂无数据',
            'status_color': 'GREEN',
            'alert_tag': '✅ 暂无数据',
            'mode': 'PERIOD'
        }

    # 读取配置
    if config is None:
        from services.algorithm_config_service import AlgorithmConfigService
        config = AlgorithmConfigService.get_active_config()

    grade_coefficients = config['performance']['grade_coefficients']
    contamination_rules = config['performance']['contamination_rules']
    time_decay = config['performance'].get('time_decay', {
        'enabled': True,
        'decay_months': 6,
        'decay_rate': 0.9
    })

    # Step 1: 系数映射（使用配置）
    coeff_map = grade_coefficients

    coeffs = []
    d_count = 0
    c_count = 0
    d_count_effective = 0.0  # 带时间衰减的有效D级计数
    c_count_effective = 0.0  # 带时间衰减的有效C级计数

    # 如果启用时间衰减且提供了日期信息
    use_time_decay = time_decay.get('enabled', True) and grade_dates and len(grade_dates) == len(grade_list)

    if use_time_decay:
        from datetime import datetime

        now = datetime.now()
        decay_months_threshold = time_decay.get('decay_months', 6)
        decay_rate_per_month = time_decay.get('decay_rate', 0.9)

        for i, (grade, date_str) in enumerate(zip(grade_list, grade_dates)):
            grade = grade.upper() if grade else 'B+'
            coeffs.append(coeff_map.get(grade, 1.0))

            try:
                # 解析日期（支持 YYYY-MM 或 YYYY-MM-DD 格式）
                if len(date_str) == 7:  # YYYY-MM
                    grade_date = datetime.strptime(date_str, '%Y-%m')
                else:  # YYYY-MM-DD
                    grade_date = datetime.strptime(date_str[:7], '%Y-%m')

                # 计算距今月数
                months_ago = (now.year - grade_date.year) * 12 + (now.month - grade_date.month)

                if grade == 'D':
                    d_count += 1
                    if months_ago <= decay_months_threshold:
                        decay_weight = (decay_rate_per_month ** months_ago)
                        d_count_effective += decay_weight
                elif grade == 'C':
                    c_count += 1
                    if months_ago <= decay_months_threshold:
                        decay_weight = (decay_rate_per_month ** months_ago)
                        c_count_effective += decay_weight

            except Exception:
                # 日期解析失败，按原逻辑计数
                if grade == 'D':
                    d_count += 1
                    d_count_effective += 1
                elif grade == 'C':
                    c_count += 1
                    c_count_effective += 1
    else:
        # 不使用时间衰减，按原逻辑
        for grade in grade_list:
            grade = grade.upper() if grade else 'B+'
            coeffs.append(coeff_map.get(grade, 1.0))
            if grade == 'D':
                d_count += 1
                d_count_effective = d_count
            elif grade == 'C':
                c_count += 1
                c_count_effective = c_count

    # Step 2: 计算平均系数
    avg_coeff = sum(coeffs) / len(coeffs) if coeffs else 1.0

    # Step 3: 还原基础分 (系数1.0对应95分)
    base_score = avg_coeff * 95

    # Step 4: 执行"污点熔断"规则（使用时间衰减后的计数）
    d_threshold = contamination_rules['d_count_threshold']
    c_threshold = contamination_rules['c_count_threshold']
    d_cap = contamination_rules['d_cap_score']
    c_cap = contamination_rules['c_cap_score']

    if d_count_effective >= d_threshold:
        # D级熔断规则（使用衰减后的计数）
        final_score = min(base_score, d_cap)
        status_color = 'RED'
        if use_time_decay and d_count_effective < d_count:
            alert_tag = f'⛔ 存在D级考核 (有效{d_count_effective:.1f}次)'
        else:
            alert_tag = '⛔ 存在D级考核'
    elif c_count_effective >= c_threshold:
        # C级熔断规则（使用衰减后的计数）
        final_score = min(base_score, c_cap)
        status_color = 'ORANGE'
        if use_time_decay and c_count_effective < c_count:
            alert_tag = f'⚠️ 多次C级预警 (有效{c_count_effective:.1f}次)'
        else:
            alert_tag = '⚠️ 多次C级预警'
    else:
        # 正常输出
        final_score = min(base_score, 110)
        if final_score >= 95:
            status_color = 'GREEN'
            alert_tag = '✅ 综合达标'
        elif final_score >= 80:
            status_color = 'ORANGE'
            alert_tag = '⚠️ 未达基准'
        else:
            status_color = 'RED'
            alert_tag = '⛔ 综合不合格'

    # 生成显示标签
    display_label = f'平均系数{avg_coeff:.2f}'

    return {
        'radar_value': round(final_score, 1),
        'display_label': display_label,
        'status_color': status_color,
        'alert_tag': alert_tag,
        'mode': 'PERIOD',
        'd_count_raw': d_count,  # 原始D级次数
        'd_count_effective': round(d_count_effective, 2),  # 时间衰减后有效次数
        'time_decay_applied': use_time_decay
    }


def calculate_safety_score_dual_track(violations_list: List[float], months_active: int = 1, config: dict = None) -> Dict:
    """
    安全意识双轨评分模型（参数化版本）

    Args:
        violations_list: 违规扣分值列表，例如 [1, 3, 6]
        months_active: 统计周期包含的月份数（月度传1，年度传12或实际在职月数）
        config: 算法配置（可选，默认从数据库读取）

    Returns:
        {
            'score_a': 行为分（习惯维度）,
            'score_b': 严重性分（后果维度）,
            'final_score': 最终分数（取两者最低）,
            'status_color': 状态颜色（RED/ORANGE/GREEN）,
            'alert_tag': 警示标签
        }
    """
    # 读取配置
    if config is None:
        from services.algorithm_config_service import AlgorithmConfigService
        config = AlgorithmConfigService.get_active_config()

    behavior_track = config['safety']['behavior_track']
    severity_track = config['safety']['severity_track']
    thresholds = config['safety']['thresholds']

    # 维度A：行为习惯（捉拿惯犯）
    violation_count = len(violations_list)
    avg_freq = math.ceil(violation_count / months_active) if months_active > 0 else 0

    # 根据月均频次扣分（使用配置参数）
    freq_thresholds = behavior_track['freq_thresholds']  # [2, 5, 6]
    freq_multipliers = behavior_track['freq_multipliers']  # [2, 5, 10]

    if avg_freq <= freq_thresholds[0]:
        score_a_deduction = avg_freq * freq_multipliers[0]
    elif freq_thresholds[0] < avg_freq <= freq_thresholds[1]:
        score_a_deduction = avg_freq * freq_multipliers[1]
    else:  # avg_freq >= freq_thresholds[2]
        score_a_deduction = avg_freq * freq_multipliers[2]

    score_a = max(0, 100 - score_a_deduction)

    # 维度B：后果严重性（精准打击）（使用配置参数）
    score_b_deduction = 0
    critical_threshold = severity_track['critical_threshold']
    has_critical_violation = False

    for score_value in violations_list:
        # 根据配置的score_ranges确定系数
        multiplier = 1.0
        for range_rule in severity_track['score_ranges']:
            if 'max' in range_rule and 'min' not in range_rule:
                # 只有max，表示 < max
                if score_value < range_rule['max']:
                    multiplier = range_rule['multiplier']
                    break
            elif 'min' in range_rule and 'max' in range_rule:
                # 有min和max，表示范围
                if range_rule['min'] <= score_value < range_rule['max']:
                    multiplier = range_rule['multiplier']
                    break
            elif 'min' in range_rule and 'max' not in range_rule:
                # 只有min，表示 >= min
                if score_value >= range_rule['min']:
                    multiplier = range_rule['multiplier']
                    break

        score_b_deduction += score_value * multiplier

        if score_value >= critical_threshold:
            has_critical_violation = True

    score_b = max(0, 100 - score_b_deduction)

    # 最终分数：取两者最低
    final_score = min(score_a, score_b)

    # 警示逻辑（使用配置阈值）
    fail_score = thresholds['fail_score']
    warning_score = thresholds['warning_score']

    if final_score < fail_score or has_critical_violation:
        # 红线熔断
        status_color = "RED"
        alert_tag = "⛔ 重大红线（存在高扣分）" if has_critical_violation else "⛔ 安全不合格"
    elif fail_score <= final_score < warning_score:
        # 黄色预警
        status_color = "ORANGE"
        if score_a < score_b:
            alert_tag = "⚠️ 高频违规风险"
        else:
            alert_tag = "⚠️ 扣分过多风险"
    else:  # final_score >= warning_score
        # 绿色安全
        status_color = "GREEN"
        alert_tag = "✅ 安全"

    return {
        'score_a': round(score_a, 1),
        'score_b': round(score_b, 1),
        'final_score': round(final_score, 1),
        'status_color': status_color,
        'alert_tag': alert_tag,
        'violation_count': violation_count,
        'avg_freq': avg_freq
    }


def calculate_training_score_with_penalty(
    training_records: List[tuple],
    duration_days: int = 30,
    cert_years: Optional[float] = None,
    config: dict = None
) -> Dict:
    """
    培训/实操能力高级评分算法 - 包含毒性惩罚和动态年化（参数化版本）

    新增动态AFR阈值：根据取证年限区分新老员工，使用不同的评判标准

    Args:
        training_records: 培训记录列表，每条记录为 (score, is_qualified, is_disqualified, training_date)
        duration_days: 统计周期天数（用于年化计算）
        cert_years: 取证年限（可选），用于判断新老员工。
                    None 或 <1年 为新员工，>=1年为老员工
        config: 算法配置（可选，默认从数据库读取）

    Returns:
        dict: {
            'radar_score': 最终雷达图分数（已惩罚）,
            'original_score': 原始基础分,
            'penalty_coefficient': 惩罚系数,
            'stats': {'total_ops', 'fail_count', 'duration_days'},
            'risk_alert': {'show', 'level', 'text', 'description'},
            'status_color': 状态颜色（用于前端显示）
        }
    """
    # 读取配置
    if config is None:
        from services.algorithm_config_service import AlgorithmConfigService
        config = AlgorithmConfigService.get_active_config()

    penalty_rules = config['training']['penalty_rules']
    duration_thresholds = config['training']['duration_thresholds']

    # Step 0: 数据准备
    total_ops = len(training_records)

    # 如果没有记录，根据统计周期判断严重程度（使用配置参数）
    if total_ops == 0:
        short_term_days = duration_thresholds['short_term_days']
        mid_term_days = duration_thresholds['mid_term_days']
        default_scores = duration_thresholds['default_scores']

        # 短期未培训：正常情况，给基础分
        if duration_days <= short_term_days:
            return {
                'radar_score': default_scores['short'],
                'original_score': default_scores['short'],
                'penalty_coefficient': 1.0,
                'stats': {
                    'total_ops': 0,
                    'fail_count': 0,
                    'duration_days': duration_days
                },
                'risk_alert': {
                    'show': True,
                    'level': 'NORMAL',
                    'text': '未开展培训',
                    'description': f'统计周期{duration_days}天内未开展培训，属于正常情况。'
                },
                'status_color': 'GREEN',
                'alert_tag': '未开展培训'
            }
        # 中期缺训：需要关注
        elif duration_days <= mid_term_days:
            return {
                'radar_score': default_scores['mid'],
                'original_score': default_scores['mid'],
                'penalty_coefficient': 1.0,
                'stats': {
                    'total_ops': 0,
                    'fail_count': 0,
                    'duration_days': duration_days
                },
                'risk_alert': {
                    'show': True,
                    'level': 'NOTICE',
                    'text': '⚠️ 长期未培训',
                    'description': f'统计周期{duration_days}天内未开展培训，建议安排培训。'
                },
                'status_color': 'YELLOW',
                'alert_tag': '⚠️ 长期未培训'
            }
        # 长期严重缺训：严重问题
        else:
            return {
                'radar_score': default_scores['long'],
                'original_score': default_scores['long'],
                'penalty_coefficient': 1.0,
                'stats': {
                    'total_ops': 0,
                    'fail_count': 0,
                    'duration_days': duration_days
                },
                'risk_alert': {
                    'show': True,
                    'level': 'CRITICAL',
                    'text': '❌ 严重缺训',
                    'description': f'统计周期{duration_days}天（超过半年）内未开展任何培训，严重影响业务能力。'
                },
                'status_color': 'RED',
                'alert_tag': '❌ 严重缺训'
            }

    # Step 1: 判定失格次数
    fail_count = 0
    total_score = 0

    for record in training_records:
        # 从字典中提取字段（MySQL DictCursor 返回字典）
        score = record['score']
        is_qualified = record['is_qualified']
        is_disqualified = record['is_disqualified']
        training_date = record['training_date']

        # 转换 score 为数值类型（MySQL 可能返回字符串）
        try:
            score_value = int(score) if score else 0
        except (ValueError, TypeError):
            score_value = 0

        # 失格判定：is_disqualified=1 OR score=0 OR is_qualified=0
        if is_disqualified == 1 or score_value == 0 or is_qualified == 0:
            fail_count += 1

        total_score += score_value

    # Step 2: 计算基础分（简单平均）
    avg_score = total_score / total_ops if total_ops > 0 else 0
    base_score = avg_score  # 可以根据需要调整权重，这里简化为平均分

    # Step 3: 确定惩罚系数（核心风控逻辑）
    coeff = 1.0
    tag_level = 'NORMAL'
    alert_msg = '✅ 能力达标'
    description = ''

    # Priority A: 绝对熔断红线（使用配置参数）
    absolute_threshold = penalty_rules['absolute_threshold']
    small_sample = penalty_rules['small_sample']

    if fail_count >= absolute_threshold['fail_count']:
        coeff = absolute_threshold['coefficient']
        tag_level = 'CRITICAL'
        alert_msg = '❌ 业务能力差 (高频失格)'
        description = f'检测到绝对失格次数 ≥ {absolute_threshold["fail_count"]}次（实际{fail_count}次），系统判定为不合格。'

    # Priority B: 小样本保护 & 高危标记（使用配置参数）
    elif total_ops < small_sample['sample_size'] and fail_count > 0:
        coeff = small_sample['coefficient']
        tag_level = 'HIGH_RISK'
        alert_msg = '⚠️ 观察期失格 (高风险-需带教)'
        description = f'样本量不足（仅{total_ops}次操作），但已出现{fail_count}次失格。建议加强带教。'

    # Priority C: 大样本年化推演（使用动态AFR阈值）
    elif total_ops >= small_sample['sample_size']:
        # 计算年化失格频率 (AFR - Annualized Failure Rate)
        duration_days = max(1, duration_days)  # 防止除零
        AFR = (fail_count / duration_days) * 365

        # 根据取证年限选择合适的AFR阈值（新增动态阈值逻辑）
        is_new_employee = cert_years is None or cert_years < 1.0

        if is_new_employee:
            # 新员工（取证1年内）：使用更宽松的阈值
            afr_thresholds = penalty_rules.get('afr_thresholds_new_employee', penalty_rules.get('afr_thresholds', []))
            employee_type = "新员工"
        else:
            # 老员工（取证1年以上）：使用标准阈值
            afr_thresholds = penalty_rules.get('afr_thresholds_experienced', penalty_rules.get('afr_thresholds', []))
            employee_type = "老员工"

        # 从高到低检查AFR阈值（支持新版可配置阈值）
        matched = False

        # 尝试按照 threshold 降序排序（如果有）
        sorted_rules = []
        try:
            # 过滤出有效的规则并排序
            valid_rules = [r for r in afr_thresholds if 'threshold' in r or 'min' in r]
            # 统一获取阈值用于排序
            def get_thresh(r):
                return float(r.get('threshold', r.get('min', 0)))
            sorted_rules = sorted(valid_rules, key=get_thresh, reverse=True)
        except Exception:
            sorted_rules = afr_thresholds

        for rule in sorted_rules:
            # 获取规则阈值
            limit = float(rule.get('threshold', rule.get('min', 0)))

            if AFR >= limit:
                coeff = rule['coefficient']

                # 确定警示级别
                if coeff <= 0.5:
                    tag_level = 'CRITICAL'
                    label = rule.get('label', '高频失格')
                elif coeff <= 0.8:
                    tag_level = 'WARNING'
                    label = rule.get('label', '频率偏高')
                else:
                    tag_level = 'NOTICE'
                    label = rule.get('label', '偶发失格')

                alert_msg = f'⚠️ {label} (年化 {AFR:.1f} 次)'
                description = f'当前周期{duration_days}天内失格{fail_count}次，年化等效{AFR:.1f}次/年，触发{label}阈值({limit})。'
                matched = True
                break

        if not matched:
            # AFR < 最低阈值
            coeff = 1.0
            tag_level = 'NORMAL'
            alert_msg = '✅ 能力达标'
            description = ''

    # 如果没有失格记录，保持正常
    elif fail_count == 0:
        coeff = 1.0
        tag_level = 'NORMAL'
        alert_msg = '✅ 能力达标'
        description = ''

    # Step 4: 计算最终分数
    final_score = base_score * coeff

    # 映射到前端颜色
    if tag_level == 'CRITICAL':
        status_color = 'RED'
    elif tag_level == 'HIGH_RISK':
        status_color = 'PURPLE'
    elif tag_level == 'WARNING':
        status_color = 'ORANGE'
    elif tag_level == 'NOTICE':
        status_color = 'YELLOW'
    else:
        status_color = 'GREEN'

    return {
        'radar_score': round(final_score, 1),
        'original_score': round(base_score, 1),
        'penalty_coefficient': coeff,
        'stats': {
            'total_ops': total_ops,
            'fail_count': fail_count,
            'duration_days': duration_days
        },
        'risk_alert': {
            'show': fail_count > 0,
            'level': tag_level,
            'text': alert_msg,
            'description': description
        },
        'status_color': status_color,
        'alert_tag': alert_msg
    }


# ==================== 以下函数从 blueprints/personnel/__init__.py 迁入 ====================
# 学习能力、稳定性、风险惯性等核心评分算法及相关辅助函数

from datetime import date, datetime, timedelta
from collections import Counter
def calculate_learning_ability_monthly(score_curr: float, score_prev: float) -> Dict:
    """
    学习能力评分 - 月度模式 (Algorithm A: Short-Term Sensitivity)

    核心设计：学习能力值 = 现状锚点分 (Position) + 趋势动能分 (Momentum)

    Args:
        score_curr: 本月综合三维得分 (0-100)
        score_prev: 上月综合三维得分 (0-100)，新员工传入 score_curr

    Returns:
        {
            'learning_score': 学习能力分数 (0-100+, 可能超过100),
            'delta': 月度变化量,
            'status_color': 状态颜色 (RED/ORANGE/YELLOW/GREEN/GOLD),
            'alert_tag': 警示标签,
            'tier': 评级 (潜力股/稳健型/懈怠型/高位企稳/低位躺平)
        }
    """
    # Step 1: 计算增量
    delta = score_curr - score_prev

    # Step 2: 计算基础成长分
    # 公式：以本月得分为基准，叠加变化的 1.5 倍权重
    learning_score = score_curr + (delta * 1.5)

    # Step 3: 应用修正逻辑
    tier = '稳健型'
    status_color = 'GREEN'
    alert_tag = '✅ 状态正常'

    # 情形 1：高位企稳 (大师红利)
    if score_curr >= 95 and delta >= -2:
        learning_score = max(100, learning_score)
        tier = '高位企稳'
        status_color = 'GOLD'
        alert_tag = '🏆 顶尖水平 (大师红利)'

    # 情形 2：低位躺平 (差生陷阱)
    elif score_curr < 70 and delta <= 0:
        learning_score = learning_score * 0.8
        tier = '低位躺平'
        status_color = 'RED'
        alert_tag = '❌ 差且无进步 (学习态度有问题)'

    # 情形 3：显著进步
    elif delta > 10:
        tier = '潜力股'
        status_color = 'GOLD'
        alert_tag = f'⭐ 进步神速 (+{delta:.1f}分)'

    # 情形 4：显著退步
    elif delta < -10:
        tier = '懈怠型'
        status_color = 'RED'
        alert_tag = f'⚠️ 严重退步 ({delta:.1f}分)'

    # 情形 5：小幅进步
    elif delta > 0:
        tier = '稳健型'
        status_color = 'GREEN'
        alert_tag = f'✅ 稳中有进 (+{delta:.1f}分)'

    # 情形 6：小幅退步
    elif delta < 0:
        tier = '需关注'
        status_color = 'YELLOW'
        alert_tag = f'⚡ 略有下滑 ({delta:.1f}分)'

    # 限制分数范围（但允许超过100）
    learning_score = max(0, learning_score)

    return {
        'learning_score': round(learning_score, 1),
        'delta': round(delta, 1),
        'slope': 0,  # 月度模式无斜率概念，设为0
        'status_color': status_color,
        'alert_tag': alert_tag,
        'tier': tier,
        'months': 1  # 月度模式统计1个月
    }


def calculate_learning_ability_longterm(
    score_list: List[float],
    config: dict = None,
    current_three_dim_score: float = None,
    group_avg: float = 1.0,
    initial_prev_viol: Optional[int] = None
) -> Dict:
    """
    [V5.0 核心算法二] 长周期·风险惯性聚合 (L_period)

    这是本模型的灵魂。按以下步骤实现：

    步骤 1：基础加权 (Base Score)
    - 对周期内单月得分进行时间加权平均，得到 base_score
    - 公式：base_score = Σ(score[i] × (1.0 + i × time_decay)) / Σweights

    步骤 2：计算"风险惯性" (Risk Inertia)
    - 扫描周期内的 zone 状态序列，寻找 "连续处于 DANGER/CRITICAL 的最大月数" (K_max)
    - 若 K_max < inertia_start_months: 惯性为 0
    - 若 K_max >= inertia_start_months:
        惯性惩罚 = min((K_max - Start + 1) × Step, max_penalty)

    步骤 3：最终计算
    - final_score = base_score × (1.0 - inertia_penalty_rate)
    - 若曾触发熔断(CRITICAL)，分数上限压制到40分

    业务含义：
    一个连续 4 个月处于危险边缘的"老油条"，即使每个月得分有 60 分（及格），
    经过惯性惩罚（-45%）后，最终得分只有 33 分（高危）。
    这精准识别了"事故前兆群体"。

    风险概率映射 (Dashboard Mapping)：
    - [事故前兆] PRE_ACCIDENT: 惯性惩罚 > 40% 或 曾触发熔断
    - [高危] HIGH_RISK: 分数 < 60
    - [重点关注] WATCH_LIST: 处于危险区 但 惯性低
    - [安全] SAFE: 其他

    Args:
        score_list: 周期内的违规数量列表（按时间顺序）
        config: 算法配置
        current_three_dim_score: 当前三维综合分（可选）
        group_avg: 班组平均违规数
        initial_prev_viol: 周期前一个月的违规数（用于计算第一个月的趋势）

    Returns:
        {
            'learning_score': float,          # 最终评分 (0-100)
            'risk_level': str,                # 风险等级: SAFE|WATCH_LIST|HIGH_RISK|PRE_ACCIDENT
            'inertia_penalty_rate': float,    # 惯性扣减率 (0.0 ~ 0.6)
            'max_consecutive_danger': int,    # 最大连续危险月数
            'base_score': float,              # 基础加权分（惯性前）
            'has_meltdown': bool,             # 是否曾触发熔断
            'zone_sequence': list,            # 各月风险区域序列
            'monthly_scores': list,           # 各月得分序列
            'slope': float,                   # 线性趋势斜率
            'average_score': float,           # 简单平均分
            'status_color': str,              # UI颜色
            'alert_tag': str,                 # 中文警示标签
            'tier': str,                      # 分层标签
            'months': int                     # 统计月数
        }
    """
    import numpy as np

    # =====================================================
    # 1. 初始化
    # =====================================================
    if config is None:
        from services.algorithm_config_service import AlgorithmConfigService
        config = AlgorithmConfigService.get_active_config()

    algo_new = config.get('learning_new', {})
    time_decay = algo_new.get('time_decay_rate', 0.2)
    history_list = score_list

    if not history_list:
        return {
            'learning_score': 0,
            'risk_level': 'UNKNOWN',
            'inertia_penalty_rate': 0,
            'max_consecutive_danger': 0,
            'base_score': 0,
            'has_meltdown': False,
            'zone_sequence': [],
            'monthly_scores': [],
            'slope': 0,
            'average_score': 0,
            'status_color': 'GRAY',
            'alert_tag': '无数据',
            'tier': '无数据',
            'months': 0
        }

    # =====================================================
    # 2. 逐月计算 & 构建状态序列
    # =====================================================
    monthly_scores = []
    zone_sequence = []
    prev_viol = initial_prev_viol
    has_meltdown = False  # 记录是否有过熔断（用于一票否决）

    for i, curr_viol in enumerate(history_list):
        res = calculate_learning_ability_new(curr_viol, prev_viol, group_avg, config)
        monthly_scores.append(res['learning_score'])
        zone_sequence.append(res['zone'])

        if res.get('trend_type') == 'meltdown' or res['zone'] == 'CRITICAL':
            has_meltdown = True

        prev_viol = curr_viol

    # =====================================================
    # 步骤 1：计算基础加权分 (Base Score)
    # 公式：base_score = Σ(score[i] × weight[i]) / Σweight[i]
    # 权重：weight[i] = 1.0 + (i × time_decay)，近期月份权重更高
    # =====================================================
    total_w = 0
    w_sum = 0
    for i, score in enumerate(monthly_scores):
        w = 1.0 + (i * time_decay)
        w_sum += score * w
        total_w += w

    base_score = w_sum / total_w if total_w > 0 else 0

    # =====================================================
    # 步骤 2：计算风险惯性 (Risk Inertia)
    # =====================================================
    inertia_res = calculate_inertia_penalty(zone_sequence, config)
    penalty_rate = inertia_res['penalty_rate']
    max_consecutive = inertia_res['max_consecutive']

    # =====================================================
    # 步骤 3：最终计算
    # final_score = base_score × (1.0 - penalty_rate)
    # =====================================================
    final_score = base_score * (1.0 - penalty_rate)

    # 特殊处理：如果有熔断记录，分数上限强行压制到40分
    if has_meltdown:
        final_score = min(final_score, 40)

    final_score = round(max(0, final_score), 1)

    # =====================================================
    # 风险概率映射 (Dashboard Mapping)
    # =====================================================
    risk_level = 'SAFE'
    status_color = 'GREEN'
    alert_tag = '✅ 状态良好'
    tier_display = '安全'

    # 规则1: [事故前兆] 惯性惩罚 > 40% 或 曾触发熔断
    if penalty_rate >= 0.4 or has_meltdown:
        risk_level = 'PRE_ACCIDENT'
        status_color = 'RED'
        tier_display = '⛔ 事故前兆'
        if has_meltdown:
            alert_tag = f'⛔ 极高危 (曾触发熔断)'
        else:
            alert_tag = f'⛔ 极高危 (惯性扣减{penalty_rate*100:.0f}%)'

    # 规则2: [高危] 分数 < 60
    elif final_score < 60:
        risk_level = 'HIGH_RISK'
        status_color = 'ORANGE'
        if penalty_rate > 0:
            status_color = 'RED'
        tier_display = '高危群体'
        if penalty_rate > 0:
            alert_tag = f'🔴 高风险 (惯性扣减{penalty_rate*100:.0f}%)'
        else:
            alert_tag = f'🔴 高风险 (得分{final_score})'

    # 规则3: [重点关注] 处于危险区 但 惯性低
    elif len(zone_sequence) >= 2 and 'DANGER' in zone_sequence[-2:]:
        risk_level = 'WATCH_LIST'
        status_color = 'YELLOW'
        tier_display = '重点关注'
        alert_tag = '⚠️ 重点关注'

    # 规则4: [安全] 其他
    # 已设置默认值

    # =====================================================
    # 计算斜率（仅供展示）
    # =====================================================
    slope = 0.0
    if len(history_list) >= 2:
        try:
            x = np.arange(len(history_list))
            y = np.array(history_list)
            res_poly = np.polyfit(x, y, 1)
            slope = float(res_poly[0])
        except Exception:
            pass

    return {
        'learning_score': final_score,
        'risk_level': risk_level,
        'inertia_penalty_rate': round(penalty_rate, 3),
        'max_consecutive_danger': max_consecutive,
        'base_score': round(base_score, 1),
        'has_meltdown': has_meltdown,
        'zone_sequence': zone_sequence,
        'monthly_scores': monthly_scores,

        # 兼容旧字段
        'slope': round(slope, 2),
        'average_score': round(float(np.mean(history_list)), 1),
        'status_color': status_color,
        'alert_tag': alert_tag,
        'tier': tier_display,
        'months': len(history_list)
    }


def calculate_stability_score(
    birth_date: Optional[str],
    work_start_date: Optional[str],
    entry_date: Optional[str],
    certification_date: Optional[str],
    solo_driving_date: Optional[str],
    historical_scores: Optional[Dict[str, List[float]]] = None,
    config: dict = None
) -> Dict:
    """
    职业稳定性综合评分算法（新版）

    评分维度：
    1. 资历维度（60%）：基于年龄、工龄、司龄、取证年限、单独驾驶年限
    2. 表现稳定性维度（40%）：基于过去一年绩效、安全、培训分值的波动度

    Args:
        birth_date: 出生日期 (YYYY-MM-DD)
        work_start_date: 参加工作时间 (YYYY-MM-DD)
        entry_date: 入司时间 (YYYY-MM-DD)
        certification_date: 取证时间 (YYYY-MM-DD)
        solo_driving_date: 单独驾驶时间 (YYYY-MM-DD)
        historical_scores: 过去一年的分数历史，格式：
            {
                'performance': [95.0, 96.0, ...],  # 最多12个月
                'safety': [92.0, 94.0, ...],
                'training': [88.0, 90.0, ...]
            }
        config: 算法配置（可选，默认从数据库读取）

    Returns:
        {
            'stability_score': 最终稳定性分数 (0-100),
            'seniority_score': 资历维度分数 (0-100),
            'volatility_score': 稳定性维度分数 (0-100),
            'metrics': {
                'age_years': 年龄,
                'working_years': 工龄,
                'company_years': 司龄,
                'cert_years': 取证年限,
                'solo_years': 单独驾驶年限,
                'volatility': 综合波动系数
            },
            'status_color': 状态颜色 (RED/ORANGE/GREEN),
            'alert_tag': 警示标签,
            'tier': 评级 (资深稳定/经验丰富/新手期/高波动风险)
        }
    """
    from datetime import datetime
    import numpy as np

    # 读取配置
    if config is None:
        from services.algorithm_config_service import AlgorithmConfigService
        config = AlgorithmConfigService.get_active_config()

    stability_config = config.get('stability', {
        'seniority_weights': {
            'age': 0.15,
            'working_years': 0.20,
            'company_years': 0.25,
            'cert_years': 0.20,
            'solo_years': 0.20
        },
        'seniority_thresholds': {
            'age_cap': 30,  # 年龄满30年算满分
            'working_cap': 20,  # 工龄满20年算满分
            'company_cap': 10,  # 司龄满10年算满分
            'cert_cap': 10,  # 取证满10年算满分
            'solo_cap': 10  # 单独驾驶满10年算满分
        },
        'dimension_weights': {
            'seniority': 0.60,  # 资历维度权重
            'volatility': 0.40   # 稳定性维度权重
        },
        'volatility_penalty': {
            'low_threshold': 5.0,     # 低波动阈值（标准差）
            'high_threshold': 15.0,   # 高波动阈值（标准差）
            'max_penalty': 0.5        # 最大惩罚系数
        }
    })

    now = datetime.now()

    # 辅助函数：解析日期（支持字符串和date对象）
    def parse_date(date_val):
        if not date_val:
            return None
        if isinstance(date_val, datetime):
            return date_val
        if hasattr(date_val, 'year'):  # date对象
            return datetime(date_val.year, date_val.month, date_val.day)
        if isinstance(date_val, str):
            return datetime.strptime(date_val, '%Y-%m-%d')
        return None

    # ==================== 维度1：资历评分（60%） ====================
    seniority_weights = stability_config['seniority_weights']
    seniority_thresholds = stability_config['seniority_thresholds']

    # 1.1 年龄计算
    age_years = 0
    if birth_date:
        try:
            birth = parse_date(birth_date)
            if birth:
                age_years = (now - birth).days / 365.25
        except Exception:
            pass
    age_score = min(100, (age_years / seniority_thresholds['age_cap']) * 100)

    # 1.2 工龄计算
    working_years = 0
    if work_start_date:
        try:
            work_start = parse_date(work_start_date)
            if work_start:
                working_years = (now - work_start).days / 365.25
        except Exception:
            pass
    working_score = min(100, (working_years / seniority_thresholds['working_cap']) * 100)

    # 1.3 司龄计算
    company_years = 0
    if entry_date:
        try:
            entry = parse_date(entry_date)
            if entry:
                company_years = (now - entry).days / 365.25
        except Exception:
            pass
    company_score = min(100, (company_years / seniority_thresholds['company_cap']) * 100)

    # 1.4 取证年限计算
    cert_years = 0
    if certification_date:
        try:
            cert = parse_date(certification_date)
            if cert:
                cert_years = (now - cert).days / 365.25
        except Exception:
            pass
    cert_score = min(100, (cert_years / seniority_thresholds['cert_cap']) * 100)

    # 1.5 单独驾驶年限计算
    solo_years = 0
    if solo_driving_date:
        try:
            solo = parse_date(solo_driving_date)
            if solo:
                solo_years = (now - solo).days / 365.25
        except Exception:
            pass
    solo_score = min(100, (solo_years / seniority_thresholds['solo_cap']) * 100)

    # 计算资历加权分数
    seniority_score = (
        age_score * seniority_weights['age'] +
        working_score * seniority_weights['working_years'] +
        company_score * seniority_weights['company_years'] +
        cert_score * seniority_weights['cert_years'] +
        solo_score * seniority_weights['solo_years']
    )

    # ==================== 维度2：表现稳定性评分（40%） ====================
    volatility_score = 100  # 默认满分（无波动数据时）
    volatility_coefficient = 0

    if historical_scores and any(historical_scores.values()):
        # 计算每个维度的标准差
        std_devs = []

        for dimension in ['performance', 'safety', 'training']:
            scores = historical_scores.get(dimension, [])
            if scores and len(scores) >= 2:
                std_dev = float(np.std(scores))
                std_devs.append(std_dev)

        if std_devs:
            # 综合波动系数：使用平均标准差
            volatility_coefficient = float(np.mean(std_devs))

            # 根据波动系数计算分数
            low_threshold = stability_config['volatility_penalty']['low_threshold']
            high_threshold = stability_config['volatility_penalty']['high_threshold']
            max_penalty = stability_config['volatility_penalty']['max_penalty']

            if volatility_coefficient <= low_threshold:
                # 低波动：满分
                volatility_score = 100
            elif volatility_coefficient >= high_threshold:
                # 高波动：应用最大惩罚
                volatility_score = 100 * (1 - max_penalty)
            else:
                # 中等波动：线性惩罚
                penalty_ratio = (volatility_coefficient - low_threshold) / (high_threshold - low_threshold)
                penalty = max_penalty * penalty_ratio
                volatility_score = 100 * (1 - penalty)

    # ==================== 综合评分 ====================
    dimension_weights = stability_config['dimension_weights']
    final_score = (
        seniority_score * dimension_weights['seniority'] +
        volatility_score * dimension_weights['volatility']
    )

    # ==================== 分级和状态判定 ====================
    # 判定资历等级
    if company_years >= 5 and cert_years >= 5:
        seniority_tier = "资深员工"
    elif company_years >= 2 and cert_years >= 2:
        seniority_tier = "经验员工"
    elif cert_years >= 1:
        seniority_tier = "新手期"
    else:
        seniority_tier = "新员工"

    # 判定稳定性等级
    if volatility_coefficient == 0:
        volatility_tier = "无历史数据"
    elif volatility_coefficient <= low_threshold:
        volatility_tier = "表现稳定"
    elif volatility_coefficient <= high_threshold:
        volatility_tier = "波动适中"
    else:
        volatility_tier = "高波动风险"

    # 综合评级
    if final_score >= 85:
        tier = f"{seniority_tier}·{volatility_tier}"
        status_color = 'GREEN'
        alert_tag = '✅ 稳定可靠'
    elif final_score >= 70:
        tier = f"{seniority_tier}·{volatility_tier}"
        status_color = 'GREEN'
        alert_tag = '✅ 基本稳定'
    elif final_score >= 50:
        tier = f"{seniority_tier}·{volatility_tier}"
        status_color = 'ORANGE'
        alert_tag = '⚠️ 稳定性一般'
    else:
        tier = f"{seniority_tier}·{volatility_tier}"
        status_color = 'RED'
        alert_tag = '⛔ 不稳定'

    return {
        'stability_score': round(final_score, 1),
        'seniority_score': round(seniority_score, 1),
        'volatility_score': round(volatility_score, 1),
        'metrics': {
            'age_years': round(age_years, 1),
            'working_years': round(working_years, 1),
            'company_years': round(company_years, 1),
            'cert_years': round(cert_years, 1),
            'solo_years': round(solo_years, 1),
            'volatility': round(volatility_coefficient, 2)
        },
        'status_color': status_color,
        'alert_tag': alert_tag,
        'tier': tier
    }


def _month_index(month_str: str) -> int:
    year, month = map(int, month_str.split('-'))
    return year * 12 + (month - 1)


def _month_shift(month_str: str, delta: int) -> str:
    idx = _month_index(month_str) + delta
    year = idx // 12
    month = idx % 12 + 1
    return f"{year:04d}-{month:02d}"


def _month_range(start_month: str, end_month: str) -> List[str]:
    if _month_index(start_month) > _month_index(end_month):
        return []
    months = []
    curr = start_month
    while _month_index(curr) <= _month_index(end_month):
        months.append(curr)
        curr = _month_shift(curr, 1)
    return months


def _resolve_stability_window(start_date: Optional[str], end_date: Optional[str], config: dict) -> tuple:
    from datetime import datetime

    stability_config = config.get('stability_new', {})
    window_months = stability_config.get('window_months', 12)
    min_effective_months = stability_config.get('min_effective_months', 6)

    end_month = end_date or datetime.now().strftime('%Y-%m')
    window_start = _month_shift(end_month, -(window_months - 1))

    if start_date and _month_index(start_date) > _month_index(window_start):
        window_start = start_date

    span = _month_index(end_month) - _month_index(window_start) + 1
    if span < min_effective_months:
        window_start = _month_shift(end_month, -(min_effective_months - 1))

    return window_start, end_month


def _load_monthly_safety_violations(cur, emp_name: str, start_month: str, end_month: str) -> Dict[str, List[float]]:
    from services.domain.safety_utils import extract_score_from_assessment

    start_date = f"{start_month}-01"
    end_next = f"{_month_shift(end_month, 1)}-01"

    cur.execute("""
        SELECT assessment, inspection_date
        FROM safety_inspection_records
        WHERE inspected_person = %s
        AND inspection_date >= %s
        AND inspection_date < %s
    """, [emp_name, start_date, end_next])
    rows = cur.fetchall()

    violations_by_month = {}
    for row in rows:
        insp_date = row['inspection_date']
        month_str = insp_date.strftime('%Y-%m') if hasattr(insp_date, 'strftime') else str(insp_date)[:7]
        score_val = extract_score_from_assessment(row['assessment'])
        if score_val > 0:
            violations_by_month.setdefault(month_str, []).append(float(score_val))

    return violations_by_month


def _build_monthly_safety_scores(violations_by_month: Dict[str, List[float]], months: List[str], config: dict) -> tuple:
    monthly_scores = {}
    monthly_issue_counts = {}

    for m in months:
        violations = violations_by_month.get(m, [])
        monthly_issue_counts[m] = len(violations)
        monthly_scores[m] = calculate_safety_score_dual_track(violations, 1, config)['final_score']

    return monthly_scores, monthly_issue_counts


def calculate_stability_for_employee(
    emp_name: str,
    start_date: Optional[str],
    end_date: Optional[str],
    config: dict,
    cur,
    safety_score_for_tip: Optional[float] = None,
    monthly_comprehensive_scores: Optional[Dict[str, float]] = None
) -> Dict:
    window_start, window_end = _resolve_stability_window(start_date, end_date, config)
    window_months = _month_range(window_start, window_end)

    last_12_start = _month_shift(window_end, -11)
    query_start = window_start if _month_index(window_start) <= _month_index(last_12_start) else last_12_start

    violations_by_month = _load_monthly_safety_violations(cur, emp_name, query_start, window_end)
    monthly_safety_scores, monthly_issue_counts = _build_monthly_safety_scores(violations_by_month, window_months, config)

    last_12_months = _month_range(last_12_start, window_end)
    issue_counts_last_12 = [len(violations_by_month.get(m, [])) for m in last_12_months]

    if not window_months:
        return {
            'stability_score': 50.0,
            'stability_label': '暂无数据',
            'status_color': 'GRAY',
            'alert_tag': '暂无数据'
        }

    return calculate_stability_score_new(
        window_months=window_months,
        monthly_safety_scores=monthly_safety_scores,
        monthly_issue_counts=monthly_issue_counts,
        issue_counts_last_12=issue_counts_last_12,
        monthly_comprehensive_scores=monthly_comprehensive_scores,
        safety_score_for_tip=safety_score_for_tip,
        config=config
    )


def calculate_stability_score_new(
    window_months: List[str],
    monthly_safety_scores: Dict[str, float],
    monthly_issue_counts: Dict[str, int],
    issue_counts_last_12: List[int],
    config: dict = None,
    monthly_comprehensive_scores: Optional[Dict[str, float]] = None,
    safety_score_for_tip: Optional[float] = None
) -> Dict:
    """
    稳定度评分算法（波动型）- 仅衡量安全表现波动

    设计原则：
    1. 使用近 window_months 个月安全分序列（不足 6 个月则标记低置信度）
    2. 0 记录按“无问题/未覆盖”规则区分
    3. 使用波动指标映射为稳定度分数（0-100）

    Args:
        window_months: 月份序列（YYYY-MM）
        monthly_safety_scores: 月度安全分（按月）
        monthly_issue_counts: 月度问题数（按月）
        issue_counts_last_12: 近 12 个月月度问题数列表（用于 0 记录判断）
        config: 算法配置
        monthly_comprehensive_scores: 月度综合分（用于 CV 对比提示，可选）
        safety_score_for_tip: 安全维度雷达分（用于低水平提示，可选）

    Returns:
        {
            'stability_score': 稳定度分数,
            'stability_label': 标签,
            'status_color': 状态颜色,
            'alert_tag': 标签文案,
            'volatility_metric': 波动指标,
            'volatility_value': 波动值,
            'coverage': 覆盖率 (有效月/窗口月),
            'confidence': 置信度,
            'volatility_tip': 波动异常提示,
            'low_level_tip': 低水平提示,
            'sample_tip': 样本不足提示,
            'safety_cv': 安全CV,
            'comprehensive_cv': 综合CV,
            'mean_safety': 安全均值
        }
    """
    import statistics

    # 读取配置
    if config is None:
        from services.algorithm_config_service import AlgorithmConfigService
        config = AlgorithmConfigService.get_active_config()

    stability_config = config.get('stability_new', {})
    metric = stability_config.get('volatility_metric', 'mean_abs_delta')
    min_effective_months = stability_config.get('min_effective_months', 6)
    high_vol_threshold = stability_config.get('high_vol_threshold', 0.0667)
    k_multiplier = stability_config.get('k_multiplier', 1.2)
    score_floor = stability_config.get('score_floor', 40.0)
    score_ceiling = stability_config.get('score_ceiling', 100.0)

    # 0 记录判定规则
    avg_issues_12 = sum(issue_counts_last_12) / len(issue_counts_last_12) if issue_counts_last_12 else 0.0
    zero_streak_months = set()
    current_streak = []
    for m in window_months:
        if monthly_issue_counts.get(m, 0) == 0:
            current_streak.append(m)
        else:
            if len(current_streak) >= 3:
                zero_streak_months.update(current_streak)
            current_streak = []
    if len(current_streak) >= 3:
        zero_streak_months.update(current_streak)

    effective_months = []
    effective_scores = []
    for m in window_months:
        issue_count = monthly_issue_counts.get(m, 0)
        is_zero = issue_count == 0
        is_effective = (not is_zero) or (avg_issues_12 < 1) or (m in zero_streak_months)
        if is_effective:
            effective_months.append(m)
            effective_scores.append(float(monthly_safety_scores.get(m, 100.0)))

    window_count = len(window_months)
    effective_count = len(effective_scores)
    coverage = f"{effective_count}/{window_count}" if window_count else "0/0"

    # 波动指标计算
    metric_value = 0.0
    if metric == 'mean_abs_delta':
        if effective_count >= 2:
            diffs = [abs(effective_scores[i] - effective_scores[i - 1]) for i in range(1, effective_count)]
            metric_value = sum(diffs) / len(diffs) if diffs else 0.0
    elif metric == 'mad':
        if effective_count >= 1:
            median_val = statistics.median(effective_scores)
            deviations = [abs(s - median_val) for s in effective_scores]
            metric_value = statistics.median(deviations) if deviations else 0.0
    elif metric == 'cv':
        if effective_count >= 2:
            mean_val = statistics.mean(effective_scores)
            if mean_val > 0:
                metric_value = statistics.pstdev(effective_scores) / mean_val
    else:
        if effective_count >= 2:
            diffs = [abs(effective_scores[i] - effective_scores[i - 1]) for i in range(1, effective_count)]
            metric_value = sum(diffs) / len(diffs) if diffs else 0.0

    # 分位映射（线性插值）
    map_low_value = stability_config.get('score_map_low', 1.09)
    map_high_value = stability_config.get('score_map_high', 6.00)
    map_low_score = stability_config.get('score_map_low_score', 90.0)
    map_high_score = stability_config.get('score_map_high_score', 60.0)

    if map_high_value == map_low_value:
        stability_score = (map_low_score + map_high_score) / 2
    else:
        slope = (map_high_score - map_low_score) / (map_high_value - map_low_value)
        stability_score = map_low_score + slope * (metric_value - map_low_value)

    stability_score = max(score_floor, min(score_ceiling, stability_score))

    # 标签判定
    label_cutoffs = stability_config.get('label_cutoffs') or {}
    stable_cut = label_cutoffs.get('stable')
    medium_cut = label_cutoffs.get('medium')

    if not isinstance(stable_cut, (int, float)):
        stable_cut = 75
    if not isinstance(medium_cut, (int, float)):
        medium_cut = 60

    if stability_score >= stable_cut:
        stability_label = '稳定'
        status_color = 'GREEN'
        alert_tag = '✅ 稳定'
    elif stability_score >= medium_cut:
        stability_label = '波动偏大'
        status_color = 'ORANGE'
        alert_tag = '⚠️ 波动偏大'
    else:
        stability_label = '波动较大'
        status_color = 'RED'
        alert_tag = '⛔ 波动较大'

    # CV 计算（用于提示）
    safety_cv = 0.0
    if effective_count >= 2:
        mean_safety = statistics.mean(effective_scores)
        if mean_safety > 0:
            safety_cv = statistics.pstdev(effective_scores) / mean_safety
    else:
        mean_safety = statistics.mean(effective_scores) if effective_scores else 0.0

    comprehensive_cv = None
    comp_scores = []
    if monthly_comprehensive_scores:
        for m in effective_months:
            score_val = monthly_comprehensive_scores.get(m)
            if isinstance(score_val, (int, float)):
                comp_scores.append(float(score_val))
    if len(comp_scores) >= 2:
        mean_comp = statistics.mean(comp_scores)
        if mean_comp > 0:
            comprehensive_cv = statistics.pstdev(comp_scores) / mean_comp

    volatility_tip = None
    if comprehensive_cv is not None:
        if safety_cv >= high_vol_threshold and safety_cv > comprehensive_cv * k_multiplier:
            volatility_tip = "安全表现波动明显，波动高于整体表现"

    low_level_tip = None
    low_level_threshold = stability_config.get('low_level_threshold')
    if low_level_threshold is None:
        low_level_threshold = config.get('safety', {}).get('thresholds', {}).get('fail_score', 60)
    tip_basis = None
    if isinstance(safety_score_for_tip, (int, float)):
        tip_basis = float(safety_score_for_tip)
    elif effective_scores:
        tip_basis = mean_safety

    if tip_basis is not None and tip_basis <= low_level_threshold:
        low_level_tip = "整体安全水平偏低（即使稳定，仍需关注）"

    sample_tip = None
    if effective_count < min_effective_months:
        sample_tip = "样本不足，稳定度参考价值有限"

    metric_labels = {
        'mean_abs_delta': 'Mean |Δ|',
        'mad': 'MAD',
        'cv': 'CV'
    }

    return {
        'stability_score': round(float(stability_score), 1),
        'stability_label': stability_label,
        'status_color': status_color,
        'alert_tag': alert_tag,
        'volatility_metric': metric,
        'volatility_metric_label': metric_labels.get(metric, metric),
        'volatility_value': round(float(metric_value), 3),
        'coverage': coverage,
        'confidence': 'LOW' if effective_count < min_effective_months else 'OK',
        'volatility_tip': volatility_tip,
        'low_level_tip': low_level_tip,
        'sample_tip': sample_tip,
        'safety_cv': round(float(safety_cv), 3) if effective_scores else None,
        'comprehensive_cv': round(float(comprehensive_cv), 3) if comprehensive_cv is not None else None,
        'mean_safety': round(float(mean_safety), 2) if effective_scores else None
    }



def calculate_inertia_penalty(zone_sequence: List[str], config: dict) -> Dict:
    """
    [V5.0 核心] 计算风险惯性惩罚 (Risk Inertia) - 识别长尾高风险群体

    核心理念：防止"短期洗白"。扫描周期内的 zone 状态序列，
    寻找"连续处于 DANGER/CRITICAL 的最大月数" (K_max)。

    判定逻辑：
    - 若 K_max < inertia_start_months: 惯性为 0，不触发惩罚
    - 若 K_max >= inertia_start_months:
        惯性惩罚 = min((K_max - Start + 1) × Step, max_penalty)

    示例（标准档 Start=2, Step=0.15, Max=0.6）：
    - 连续2个月危险 → (2-2+1)×0.15 = 15% 惩罚
    - 连续3个月危险 → (3-2+1)×0.15 = 30% 惩罚
    - 连续4个月危险 → (4-2+1)×0.15 = 45% 惩罚
    - 连续5个月危险 → min(60%, 60%) = 60% 惩罚（封顶）

    Args:
        zone_sequence: 状态序列，例如 ['SAFE', 'DANGER', 'DANGER', 'SAFE']
        config: 算法配置

    Returns:
        {
            'penalty_rate': float,        # 惯性扣减率 (0.0 ~ max_penalty)
            'max_consecutive': int,       # 最大连续危险月数 (K_max)
            'is_triggered': bool,         # 是否触发惯性惩罚
            'start_threshold': int,       # 启动阈值
            'step': float,                # 步长
            'max_penalty': float          # 最大惩罚
        }
    """
    cfg = config.get('learning_new', {})

    # =====================================================
    # C. 风险惯性配置 (The Risk Inertia)
    # =====================================================
    inertia_start = cfg.get('inertia_start_months', 2)   # 惯性启动阈值
    inertia_step = cfg.get('inertia_step', 0.15)         # 惯性累积步长
    inertia_max = cfg.get('inertia_max_penalty', 0.6)    # 最大惯性惩罚

    if not zone_sequence:
        return {
            'penalty_rate': 0.0,
            'max_consecutive': 0,
            'is_triggered': False,
            'start_threshold': inertia_start,
            'step': inertia_step,
            'max_penalty': inertia_max
        }

    # =====================================================
    # 扫描连续危险月数
    # =====================================================
    max_conse = 0       # 最大连续危险月数
    current_conse = 0   # 当前连续计数

    for zone in zone_sequence:
        if zone in ['DANGER', 'CRITICAL']:
            current_conse += 1
        else:
            max_conse = max(max_conse, current_conse)
            current_conse = 0

    # 处理序列末尾的连续危险
    max_conse = max(max_conse, current_conse)

    # =====================================================
    # 计算惯性惩罚
    # =====================================================
    penalty_rate = 0.0
    is_triggered = False

    if max_conse >= inertia_start:
        is_triggered = True
        # 公式: (K_max - Start + 1) × Step
        raw_penalty = (max_conse - inertia_start + 1) * inertia_step
        penalty_rate = min(raw_penalty, inertia_max)

    return {
        'penalty_rate': round(penalty_rate, 3),
        'max_consecutive': max_conse,
        'is_triggered': is_triggered,
        'start_threshold': inertia_start,
        'step': inertia_step,
        'max_penalty': inertia_max
    }


def calculate_learning_ability_new(
    current_violations: int,
    previous_violations: Optional[int],
    group_avg_violations: float,
    config: dict = None
) -> Dict:
    """
    [V5.0 核心算法一] 单月风险状态判定 (L_month)

    升级说明：
    - 不再单纯看趋势，而是根据动态水位判定当月处于哪个"风险区域"
    - 必须返回当月的"区域状态 (Zone Status)"，供长周期算法计算惯性

    水位线计算：
    - warning_line = max(group_avg × ratio, warning_floor, historical_baseline)
    - warning_line = min(warning_line, ceiling_floor)  # 绝对天花板限制
    - critical_line = max(group_avg × critical_ratio, critical_floor)

    区域判定：
    - CRITICAL: N >= critical_line → 分数 0.0, 一票否决
    - DANGER:   N >= warning_line  → 分数按危险区系数计算
    - SAFE:     N < warning_line   → 分数按安全区系数计算

    Args:
        current_violations: 本月违规数
        previous_violations: 上月违规数 (用于辅助判定改善/恶化)
        group_avg_violations: 班组均值
        config: 算法配置

    Returns:
        {
            'score': float,           # 单月得分 (0-100)
            'learning_score': float,  # 兼容旧字段名
            'zone': str,              # 'SAFE' | 'DANGER' | 'CRITICAL'
            'count': int,             # 当月违规数
            'trend_type': str,        # 细分类型
            'status_color': str,      # UI颜色
            'alert_tag': str,         # 警示标签
            'warning_line': float,    # 关注线
            'critical_line': float    # 熔断线
        }
    """
    # 1. 提取配置
    if config is None:
        from services.algorithm_config_service import AlgorithmConfigService
        config = AlgorithmConfigService.get_active_config()

    cfg = config.get('learning_new', {})

    # =====================================================
    # A. 动态水位配置 (The Filter) - 防止群体漂移的核心红线
    # =====================================================
    ceiling_floor = cfg.get('trend_ceiling_floor', 5)         # 绝对天花板
    warning_ratio = cfg.get('trend_warning_ratio', 1.5)       # 关注线倍率
    warning_floor = cfg.get('trend_warning_floor', 2)         # 关注线保底
    critical_ratio = cfg.get('trend_critical_ratio', 3.0)     # 熔断线倍率
    critical_floor = cfg.get('trend_critical_floor', 5)       # 熔断线保底
    historical_baseline = cfg.get('historical_baseline', 3)   # 历史基准

    # =====================================================
    # B. 阶梯趋势系数 (The Matrix)
    # =====================================================
    # 安全区系数
    factor_reward = cfg.get('factor_reward', cfg.get('factor_improvement', 1.2))
    factor_stable = cfg.get('factor_stable', 1.0)
    factor_safe_fluctuation = cfg.get('factor_safe_fluctuation', 0.9)
    # 危险区系数
    factor_mitigation = cfg.get('factor_mitigation', cfg.get('factor_high_improvement', 0.8))
    factor_warning = cfg.get('factor_warning', 0.6)
    factor_solidification = cfg.get('factor_solidification', 0.4)
    factor_deterioration = cfg.get('factor_deterioration', 0.3)

    # =====================================================
    # 计算水位线
    # =====================================================
    # 关注线 = max(group_avg × ratio, warning_floor, historical_baseline)
    warning_line_dynamic = max(
        group_avg_violations * warning_ratio,
        warning_floor,
        historical_baseline
    )
    # 应用绝对天花板：水位线不能超过 ceiling_floor
    warning_line = warning_line_dynamic
    if ceiling_floor > 0:
        warning_line = min(warning_line, ceiling_floor)

    # 熔断线
    critical_line = max(group_avg_violations * critical_ratio, critical_floor)
    # 保证 critical >= warning + 1 (至少差1)
    critical_line = max(critical_line, warning_line + 1)

    # =====================================================
    # 区域判定 (Zone Detection)
    # =====================================================
    zone = 'SAFE'
    score_base = 90
    coeff = 1.0
    trend_type = 'stable'
    status_color = 'GREEN'
    alert_tag = ''

    # --- (1) CRITICAL ZONE: 触达熔断线 → 一票否决 ---
    if current_violations >= critical_line:
        return {
            'score': 0.0,
            'learning_score': 0.0,
            'zone': 'CRITICAL',
            'count': current_violations,
            'trend_type': 'meltdown',
            'status_color': 'RED',
            'alert_tag': f'⛔ 触达熔断线 ({current_violations}≥{critical_line:.0f})',
            'warning_line': round(warning_line, 1),
            'critical_line': round(critical_line, 1)
        }

    # --- (2) DANGER ZONE: 高于关注线 ---
    elif current_violations >= warning_line:
        zone = 'DANGER'
        score_base = 60  # 危险区及格分起点

        # 细分趋势判定
        if previous_violations is not None:
            if current_violations < previous_violations:
                # 危险区改善 (Mitigation): 减轻惩罚但不奖励
                coeff = factor_mitigation  # 0.8
                trend_type = 'high_improvement'
                alert_tag = '⚠️ 高位改善 (未脱险)'
                status_color = 'YELLOW'
            elif current_violations == previous_violations:
                # 危险区固化 (Solidification): 严厉惩罚
                coeff = factor_solidification  # 0.4
                trend_type = 'solidification'
                alert_tag = '⛔ 风险固化'
                status_color = 'ORANGE'
            else:
                # 危险区恶化 (Warning): 更严厉
                coeff = factor_deterioration  # 0.3
                trend_type = 'deterioration'
                alert_tag = '🔴 高位恶化'
                status_color = 'RED'
        else:
            # 无历史数据 (冷启动高位)
            coeff = factor_warning  # 0.6
            trend_type = 'cold_start_warning'
            alert_tag = '⚠️ 起步高危'
            status_color = 'YELLOW'

    # --- (3) SAFE ZONE: 低于关注线 ---
    else:
        zone = 'SAFE'
        score_base = 95

        # 奖励机制
        if previous_violations is not None:
            if current_violations < previous_violations:
                # 安全区改善: 奖励
                coeff = factor_reward  # 1.2
                trend_type = 'improvement'
                alert_tag = '📈 持续改善'
                status_color = 'GREEN'
            elif current_violations == previous_violations:
                # 安全区稳定: 保持
                coeff = factor_stable  # 1.0
                trend_type = 'safe_stable'
                alert_tag = '✅ 保持平稳'
                status_color = 'GREEN'
            else:
                # 安全区波动: 轻微惩罚
                coeff = factor_safe_fluctuation  # 0.9
                trend_type = 'safe_fluctuation'
                alert_tag = '📉 安全波动'
                status_color = 'BLUE'
        else:
            # 冷启动良好
            coeff = factor_stable  # 1.0
            trend_type = 'cold_start_good'
            alert_tag = '✅ 表现良好'
            status_color = 'GREEN'

    # =====================================================
    # 计算最终得分
    # =====================================================
    final_score = score_base * coeff

    # 群体校准补偿：优于班组平均 +10%
    if current_violations < group_avg_violations:
        final_score *= 1.1

    final_score = min(100, max(0, final_score))

    return {
        'score': round(final_score, 1),
        'learning_score': round(final_score, 1),  # 兼容旧字段名
        'zone': zone,
        'count': current_violations,
        'trend_type': trend_type,
        'status_color': status_color,
        'alert_tag': alert_tag,
        'warning_line': round(warning_line, 1),
        'critical_line': round(critical_line, 1)
    }




def calculate_stability_period_aggregated(monthly_data, config):
    """
    长周期稳定度聚合逻辑 (V4.0)
    Args:
        monthly_data: list of dicts, item: {'score': float, 'has_redline': bool}
        config: EvaluationConfig dict
    Returns:
        dict: {
            'final_score': float,
            'is_veto': bool,
            'avg_score': float,
            'cv_discount': float,
            'cv': float,
            'alert_tag': str
        }
    """
    import statistics
    
    # 获取配置参数
    stability_config = config.get('stability_new', {})
    period_cv_sensitivity = stability_config.get('period_cv_sensitivity', 1.2)
    time_decay = config.get('learning_new', {}).get('time_decay_rate', 0.2)
    
    # 1. 短板熔断检查 (Veto Check)
    scores = []
    veto_triggered = False
    
    for month in monthly_data:
        # 条件：红线违规 或 得分为0
        # 注意：浮点数比较用 epsilon
        if month.get('has_redline', False) or month.get('score', 0) <= 0.001:
            veto_triggered = True
            return {
                'final_score': 0.0,
                'is_veto': True,
                'avg_score': 0.0,
                'cv_discount': 0.0,
                'cv': 0.0,
                'alert_tag': '❌ 熔断 (红线/零分)'
            }
        scores.append(month['score'])
        
    if not scores: # 无数据
        return {
            'final_score': 100.0,
            'is_veto': False,
            'avg_score': 100.0,
            'cv_discount': 1.0,
            'cv': 0.0,
            'alert_tag': '✅ 稳定'
        }

    # 2. 加权平均 (Weighted Average)
    weighted_sum = 0
    total_w = 0
    # 假设 scores 顺序为 [最早月 ... 最近月]
    for i, s in enumerate(scores):
        w = 1.0 + (i * time_decay)
        weighted_sum += s * w
        total_w += w
    
    avg_score = weighted_sum / total_w if total_w > 0 else 0
    
    # 3. 波动惩罚 (CV Discount)
    if len(scores) < 2:
        cv = 0.0
        discount = 1.0
    else:
        mean_val = statistics.mean(scores)
        if mean_val > 0.001:
            stdev_val = statistics.pstdev(scores) 
            cv = stdev_val / mean_val
        else:
            cv = 0.0
            
        discount = 1.0 - (cv * period_cv_sensitivity)
        discount = max(0.0, min(1.0, discount))
        
    final_score = avg_score * discount
    
    # 确定标签
    if final_score >= 80:
        tag = '✅ 稳定'
    elif final_score >= 60:
        tag = '⚠️ 波动'
    else:
        tag = '❌ 不稳定'
        
    return {
        'final_score': final_score,
        'is_veto': False,
        'avg_score': avg_score,
        'cv_discount': discount,
        'cv': cv,
        'alert_tag': tag
    }


def _parse_date_string(value: Optional[str]) -> Optional[date]:
    """解析日期字符串为date对象"""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value).strip()
    if not raw:
        return None
    fmts = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y.%m.%d",
        "%Y%m%d",
        "%Y-%m",
        "%Y/%m",
        "%Y.%m",
        "%Y%m",
    ]
    for fmt in fmts:
        try:
            dt = datetime.strptime(raw, fmt)
            if fmt in {"%Y-%m", "%Y/%m", "%Y.%m", "%Y%m"}:
                dt = dt.replace(day=1)
            return dt.date()
        except ValueError:
            continue
    return None


def _normalize_date_to_str(value: Optional[str]) -> Optional[str]:
    """标准化日期为字符串"""
    parsed = _parse_date_string(value)
    return parsed.strftime("%Y-%m-%d") if parsed else None


def _calculate_age(birth_date: Optional[str]) -> Optional[int]:
    """计算年龄"""
    parsed = _parse_date_string(birth_date)
    if not parsed:
        return None
    today = date.today()
    years = today.year - parsed.year
    if (today.month, today.day) < (parsed.month, parsed.day):
        years -= 1
    return max(years, 0)


def _calculate_years_since(date_str: Optional[str]) -> Optional[float]:
    """计算从指定日期到今天的年数"""
    parsed = _parse_date_string(date_str)
    if not parsed:
        return None
    today = date.today()
    if parsed > today:
        return 0.0
    years = (today - parsed).days / 365.25
    return round(years, 1)


def _serialize_person(row: Dict) -> Dict:
    """序列化人员数据，添加计算字段"""
    data = dict(row)
    data["age"] = _calculate_age(data.get("birth_date"))
    data["working_years"] = _calculate_years_since(data.get("work_start_date"))
    data["tenure_years"] = _calculate_years_since(data.get("entry_date"))
    return data


def _build_personnel_charts(rows: List[Dict]) -> Dict:
    """构建人员统计图表数据"""
    # 年龄分布
    age_labels = ["25岁及以下", "26-35岁", "36-45岁", "46岁及以上"]
    age_counts = [0, 0, 0, 0]
    for row in rows:
        age = row.get("age")
        if age is None:
            continue
        if age <= 25:
            age_counts[0] += 1
        elif 26 <= age <= 35:
            age_counts[1] += 1
        elif 36 <= age <= 45:
            age_counts[2] += 1
        else:
            age_counts[3] += 1

    # 学历分布
    education_counter = Counter(
        row.get("education") or "未填写" for row in rows
    )
    education_labels = list(education_counter.keys())
    education_counts = [education_counter[label] for label in education_labels]

    # 工龄分布
    tenure_labels = ["1年以下", "1-3年", "3-5年", "5-10年", "10年以上"]
    tenure_counts = [0, 0, 0, 0, 0]
    for row in rows:
        tenure = row.get("tenure_years")
        if tenure is None:
            continue
        if tenure < 1:
            tenure_counts[0] += 1
        elif 1 <= tenure < 3:
            tenure_counts[1] += 1
        elif 3 <= tenure < 5:
            tenure_counts[2] += 1
        elif 5 <= tenure < 10:
            tenure_counts[3] += 1
        else:
            tenure_counts[4] += 1

    return {
        "age": {"labels": age_labels, "values": age_counts},
        "education": {"labels": education_labels, "values": education_counts},
        "tenure": {"labels": tenure_labels, "values": tenure_counts},
    }
