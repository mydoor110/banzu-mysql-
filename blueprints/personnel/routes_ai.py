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
    validate_employee_access, log_import_operation, parse_time_range
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
    # 验证权限
    if not validate_employee_access(emp_no):
        return jsonify({'error': '无权限查看此员工'}), 403

    # 获取日期筛选参数
    tr = parse_time_range(request.args, ['month'], default_grain='month', default_range=None)
    start_month = tr['start_month']
    end_month = tr['end_month']
    # 传给 Service 的是标准 YYYY-MM-DD 日期
    start_date = tr['start_date']
    end_date = tr['end_date']

    current_app.logger.debug(
        f" [comprehensive-profile]: emp_no={emp_no}, start_month='{start_month}', end_month='{end_month}'"
    )

    # 调用 Service 层获取画像数据
    from services.comprehensive_profile_service import ComprehensiveProfileService
    result = ComprehensiveProfileService.get_profile(emp_no, start_date, end_date)

    if result is None:
        return jsonify({'error': '员工不存在'}), 404

    return jsonify(result)


@personnel_bp.route('/api/risk-mining')
@login_required
def api_risk_mining():
    """
    API: 高风险人员挖掘分析

    Query Parameters:
        start_month: 开始月份 (YYYY-MM), 默认12个月前
        end_month: 结束月份 (YYYY-MM), 默认当前月
        enable_ai: 是否启用AI诊断 (true/false), 默认true

    Returns:
        {
            high_risk_list: [...],   # 按风险分排序的员工列表
            keyword_cloud: [...],     # 关键词词云数据
            survival_curve: [...],    # 生存曲线数据
            summary: {...}            # 统计摘要
        }
    """
    # parse_time_range 放在 try 外，确保 TimeRangeError 由全局 handler 处理（→ 400）
    tr = parse_time_range(request.args, ['month'], default_grain='month', default_range=None)
    start_month = tr['start_month']
    end_month = tr['end_month']
    start_date = tr['start_date']
    end_date = tr['end_date']

    try:
        from services.risk_mining_service import RiskMiningService

        enable_ai = request.args.get('enable_ai', 'true').lower() == 'true'

        # 使用 AccessControlService 进行权限判断（P1 统一出口）
        from services.access_control_service import AccessControlService
        department_path = None

        if not AccessControlService.is_admin():
            accessible_dept_ids = get_accessible_department_ids()

            if not accessible_dept_ids:
                return jsonify({
                    'success': True,
                    'high_risk_list': [],
                    'keyword_cloud': [],
                    'survival_curve': [],
                    'summary': {
                        'total_employees': 0,
                        'high_risk_count': 0,
                        'anomaly_count': 0,
                        'analysis_period': f'{start_month} ~ {end_month}' if start_month and end_month else '最近12个月'
                    },
                    'message': '您未被分配到任何部门，无法查看风险数据'
                })

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
                return jsonify({
                    'success': True,
                    'high_risk_list': [],
                    'keyword_cloud': [],
                    'survival_curve': [],
                    'summary': {
                        'total_employees': 0,
                        'high_risk_count': 0,
                        'anomaly_count': 0,
                        'analysis_period': f'{start_month} ~ {end_month}' if start_month and end_month else '最近12个月'
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
        # 日期范围参数：统一要求 YYYY-MM-DD
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
        # [4B] all_violations 是标准输入键，与 _build_cache_key / _build_data_context 对齐
        risk_data = {
            # 基础统计数据（来自前端）
            'performance_slope': basic_risk_data.get('performance_slope', 0),
            'performance_mean': basic_risk_data.get('performance_score', 0),
            'safety_count': basic_risk_data.get('safety_count', 0),
            'training_disqualified_count': basic_risk_data.get('training_disqualified_count', 0),
            'is_anomaly': basic_risk_data.get('is_anomaly', False),
            'anomaly_score': basic_risk_data.get('anomaly_score', 0),
            'risk_factors': basic_risk_data.get('risk_factors', []),
            # 详细记录（从数据库重新获取，全量不限条数，与批量分析保持一致）
            'all_violations': RiskMiningService._get_all_violations(emp_no, start_date, end_date),
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
