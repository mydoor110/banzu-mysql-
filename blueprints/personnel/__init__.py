#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人员管理模块
负责员工信息管理、导入导出等功能
"""
import json
import os
import pymysql
from collections import Counter
from datetime import date, datetime, timedelta
from io import BytesIO
from typing import Dict, List, Optional

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, session, current_app
from openpyxl import Workbook, load_workbook

from config.settings import APP_TITLE, EXPORT_DIR
from models.database import get_db, close_db, get_year_month_concat
from ..decorators import login_required, manager_required
from ..helpers import (
    current_user_id, require_user_id, get_accessible_department_ids,
    get_accessible_departments, calculate_years_from_date, get_user_department,
    validate_employee_access, log_import_operation
)
from services.domain.safety_utils import extract_score_from_assessment

# 创建 Blueprint
personnel_bp = Blueprint('personnel', __name__, url_prefix='/personnel')


# ==================== 常量定义 ====================
# P1.2：常量唯一定义在 services/domain/personnel_constants.py
# 此处 re-export 以确保路由子模块向后兼容
from services.domain.personnel_constants import (
    PERSONNEL_FIELD_SCHEME,
    PERSONNEL_DB_COLUMNS,
    PERSONNEL_DATE_FIELDS,
    PERSONNEL_SELECT_OPTIONS,
    PERSONNEL_IMPORT_HEADER_MAP,
)


# ==================== 算法函数 ====================
# 核心算法已迁移到 services/domain/personnel_algo.py
# 此处保留 re-export 以确保向后兼容
from services.domain.personnel_algo import (
    calculate_learning_ability_monthly,
    calculate_learning_ability_longterm,
    calculate_stability_score,
    calculate_stability_score_new,
    calculate_stability_period_aggregated,
    calculate_inertia_penalty,
    calculate_learning_ability_new,
    calculate_stability_for_employee,
    _month_index,
    _month_shift,
    _month_range,
    _resolve_stability_window,
    _load_monthly_safety_violations,
    _build_monthly_safety_scores,
    _parse_date_string,
    _normalize_date_to_str,
    _calculate_age,
    _calculate_years_since,
    _serialize_person,
    _build_personnel_charts,
)



# ==================== 数据库访问函数 ====================
# 业务逻辑已迁移到 services/personnel_service.py
# 此处保留 re-export 以确保路由子模块向后兼容
from services.personnel_service import (
    list_personnel,
    get_personnel,
    _sanitize_person_payload,
    upsert_personnel,
    bulk_import_personnel,
    update_personnel_field,
    delete_employee,
)


# ==================== 路由处理 ====================



# ==================== 路由子模块 ====================
# 路由按业务子域拆分，此处导入以注册到 personnel_bp
from . import routes_crud       # noqa: F401, E402
from . import routes_dashboard  # noqa: F401, E402
from . import routes_analytics  # noqa: F401, E402
from . import routes_ai         # noqa: F401, E402
