#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Risk Mining Service - Core algorithms for high-risk employee identification.

Implements:
A. Dynamic Risk Scoring (Composite multi-dimensional model)
B. Anomaly Detection (Isolation Forest)
C. Text Mining (NLP keyword extraction)
D. Survival Analysis (Kaplan-Meier for violation prediction)
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

from models.database import get_db
from services.text_mining_service import TextMiningService
from services.ai_diagnosis_service import AIDiagnosisService
from config.settings import AIConfig


@dataclass
class RiskEmployee:
    """Risk analysis result for a single employee"""
    emp_no: str
    name: str
    risk_score: float
    performance_score: float
    performance_slope: float
    safety_score: float
    safety_count: int
    training_score: float
    training_disqualified_count: int
    is_anomaly: bool
    anomaly_score: float
    risk_factors: List[str]
    ai_diagnosis: Optional[str] = None


class RiskMiningService:
    """
    High-risk employee mining service with machine learning algorithms.

    Algorithms:
    - Linear Regression for performance trend (slope calculation)
    - Isolation Forest for anomaly detection
    - Jieba + TF for text mining
    - Kaplan-Meier for survival analysis
    """

    # Weight configuration for composite risk score
    WEIGHTS = {
        'safety': 0.5,      # 安全违章权重
        'training': 0.3,    # 培训隐患权重
        'performance': 0.2  # 绩效下滑权重
    }

    # Minimum months for slope calculation
    MIN_MONTHS_FOR_SLOPE = 3

    @classmethod
    def _get_employee_data(cls, department_path: Optional[str] = None) -> pd.DataFrame:
        """
        Get all employees with their basic info.

        Args:
            department_path: Optional department path filter

        Returns:
            DataFrame with employee information
        """
        conn = get_db()
        cur = conn.cursor()

        query = """
            SELECT e.id, e.emp_no, e.name, e.class_name,
                   e.work_start_date, e.entry_date, e.solo_driving_date,
                   d.name as department_name, d.path as department_path
            FROM employees e
            LEFT JOIN departments d ON e.department_id = d.id
        """

        if department_path:
            query += f" WHERE d.path LIKE %s"
            cur.execute(query, (f"{department_path}%",))
        else:
            cur.execute(query)

        rows = cur.fetchall()
        if not rows:
            return pd.DataFrame()

        # DictCursor 返回的是字典列表，直接转 DataFrame
        return pd.DataFrame(rows)

    @classmethod
    def _get_performance_data(
        cls,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Get performance records within date range.

        Args:
            start_date: Start date (YYYY-MM format)
            end_date: End date (YYYY-MM format)

        Returns:
            DataFrame with performance records
        """
        conn = get_db()
        cur = conn.cursor()

        start_year, start_month = map(int, start_date.split('-'))
        end_year, end_month = map(int, end_date.split('-'))

        query = """
            SELECT emp_no, name, year, month, score, grade
            FROM performance_records
            WHERE (year > %s OR (year = %s AND month >= %s))
              AND (year < %s OR (year = %s AND month <= %s))
            ORDER BY emp_no, year, month
        """

        cur.execute(query, (start_year, start_year, start_month,
                           end_year, end_year, end_month))
        rows = cur.fetchall()
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    @classmethod
    def _get_safety_data(
        cls,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Get safety inspection records.

        Args:
            start_date: Start date (YYYY-MM-DD or YYYY-MM format)
            end_date: End date

        Returns:
            DataFrame with safety records
        """
        conn = get_db()
        cur = conn.cursor()

        # Handle YYYY-MM format
        if len(start_date) == 7:
            start_date = f"{start_date}-01"
        if len(end_date) == 7:
            end_date = f"{end_date}-31"

        query = """
            SELECT id, category, inspection_date, hazard_description,
                   inspected_person, responsible_team, assessment
            FROM safety_inspection_records
            WHERE inspection_date >= %s AND inspection_date <= %s
        """

        cur.execute(query, (start_date, end_date))
        rows = cur.fetchall()
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    @classmethod
    def _get_training_data(
        cls,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Get training records with disqualified flag.

        Args:
            start_date: Start date (YYYY-MM-DD or YYYY-MM format)
            end_date: End date

        Returns:
            DataFrame with training records
        """
        conn = get_db()
        cur = conn.cursor()

        if len(start_date) == 7:
            start_date = f"{start_date}-01"
        if len(end_date) == 7:
            end_date = f"{end_date}-31"

        query = """
            SELECT id, emp_no, name, training_date, problem_type,
                   specific_problem, score, is_qualified, is_disqualified
            FROM training_records
            WHERE training_date >= %s AND training_date <= %s
        """

        cur.execute(query, (start_date, end_date))
        rows = cur.fetchall()
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    @classmethod
    def _calculate_performance_slope(cls, scores: List[float]) -> float:
        """
        Calculate performance trend slope using linear regression.

        Args:
            scores: List of monthly performance scores (ordered by time)

        Returns:
            Slope coefficient (negative = declining performance)
        """
        if len(scores) < cls.MIN_MONTHS_FOR_SLOPE:
            return 0.0

        try:
            # 确保 scores 是数值类型
            scores = [float(s) for s in scores if s is not None]
            if len(scores) < cls.MIN_MONTHS_FOR_SLOPE:
                return 0.0

            from sklearn.linear_model import LinearRegression

            X = np.arange(len(scores)).reshape(-1, 1)
            y = np.array(scores, dtype=float)

            model = LinearRegression()
            model.fit(X, y)

            return float(model.coef_[0])

        except (ImportError, ValueError, TypeError):
            try:
                # Fallback to numpy polyfit
                x = np.arange(len(scores))
                y = np.array(scores, dtype=float)
                coeffs = np.polyfit(x, y, 1)
                return float(coeffs[0])
            except:
                return 0.0

    @classmethod
    def _normalize_score(cls, value: float, min_val: float, max_val: float) -> float:
        """
        Normalize a value to 0-100 scale.

        Args:
            value: Raw value
            min_val: Minimum value in dataset
            max_val: Maximum value in dataset

        Returns:
            Normalized score (0-100)
        """
        if max_val == min_val:
            return 50.0
        return ((value - min_val) / (max_val - min_val)) * 100

    @classmethod
    def _detect_anomalies(cls, features_df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Detect anomalies using Isolation Forest.

        Args:
            features_df: DataFrame with features (performance_mean, performance_var, violation_count)

        Returns:
            Tuple of (is_anomaly array, anomaly_scores array)
        """
        if len(features_df) < 10:
            # Not enough data for meaningful anomaly detection
            return np.zeros(len(features_df), dtype=bool), np.zeros(len(features_df))

        try:
            from sklearn.ensemble import IsolationForest

            # Prepare features
            feature_cols = ['performance_mean', 'performance_var', 'violation_count']
            X = features_df[feature_cols].fillna(0).values

            # Fit Isolation Forest
            iso_forest = IsolationForest(
                n_estimators=100,
                contamination=0.05,  # Expect 5% anomalies
                random_state=42,
                n_jobs=-1
            )

            predictions = iso_forest.fit_predict(X)
            scores = iso_forest.decision_function(X)

            # Convert predictions: -1 (anomaly) -> True, 1 (normal) -> False
            is_anomaly = predictions == -1
            # Convert scores to 0-100 scale (higher = more anomalous)
            anomaly_scores = (1 - (scores - scores.min()) / (scores.max() - scores.min() + 1e-10)) * 100

            return is_anomaly, anomaly_scores

        except ImportError:
            # Fallback if sklearn not available
            return np.zeros(len(features_df), dtype=bool), np.zeros(len(features_df))

    @classmethod
    def _calculate_survival_curve(
        cls,
        employees_df: pd.DataFrame,
        violations_df: pd.DataFrame
    ) -> List[Dict]:
        """
        Calculate survival curve using Kaplan-Meier estimator.

        Args:
            employees_df: DataFrame with employee data including solo_driving_date
            violations_df: DataFrame with violation records

        Returns:
            List of dicts with time and probability
        """
        try:
            from lifelines import KaplanMeierFitter

            # Calculate driving years for each employee
            today = datetime.now()
            employees_df = employees_df.copy()

            # Parse solo_driving_date and calculate duration
            def calc_driving_years(row):
                if pd.isna(row.get('solo_driving_date')):
                    # Fallback to entry_date or work_start_date
                    date_str = row.get('entry_date') or row.get('work_start_date')
                else:
                    date_str = row['solo_driving_date']

                if pd.isna(date_str):
                    return None

                try:
                    start_date = pd.to_datetime(date_str)
                    years = (today - start_date).days / 365.25
                    return max(0, years)
                except:
                    return None

            employees_df['driving_years'] = employees_df.apply(calc_driving_years, axis=1)

            # Check if employee has any violation (event occurred)
            # violations_df should have 'name' column (already renamed from inspected_person)
            violation_emps = set(violations_df['name'].dropna().unique()) if 'name' in violations_df.columns else set()
            employees_df['has_violation'] = employees_df['name'].isin(violation_emps).astype(int)

            # Filter valid data
            valid_df = employees_df.dropna(subset=['driving_years'])
            valid_df = valid_df[valid_df['driving_years'] > 0]

            if len(valid_df) < 5:
                # Not enough data for survival analysis
                return [{"time": 0, "probability": 1.0}]

            # Fit Kaplan-Meier
            kmf = KaplanMeierFitter()
            kmf.fit(
                durations=valid_df['driving_years'],
                event_observed=valid_df['has_violation']
            )

            # Get survival curve data points
            timeline = kmf.survival_function_.index.tolist()
            probabilities = kmf.survival_function_['KM_estimate'].tolist()

            # Sample key points for output
            result = []
            target_times = [0, 1, 2, 3, 5, 7, 10, 15, 20]

            for t in target_times:
                if t <= max(timeline):
                    idx = np.searchsorted(timeline, t)
                    if idx < len(probabilities):
                        result.append({
                            "time": t,
                            "probability": round(probabilities[idx], 3)
                        })

            # Add the last point
            if timeline[-1] not in target_times:
                result.append({
                    "time": round(timeline[-1], 1),
                    "probability": round(probabilities[-1], 3)
                })

            return result if result else [{"time": 0, "probability": 1.0}]

        except ImportError:
            # Fallback if lifelines not available
            return [{"time": 0, "probability": 1.0}]
        except Exception as e:
            print(f"Survival analysis error: {e}")
            return [{"time": 0, "probability": 1.0}]

    @classmethod
    def _get_recent_violations(cls, emp_no: str, limit: int = 10,
                               start_date: str = None, end_date: str = None) -> List[Dict]:
        """
        获取员工最近的违章记录（用于AI诊断）

        Args:
            emp_no: 员工工号
            limit: 最大返回记录数
            start_date: 开始日期 (YYYY-MM 或 YYYY-MM-DD 格式)
            end_date: 结束日期 (YYYY-MM 或 YYYY-MM-DD 格式)

        Returns:
            违章记录列表，每条包含 date, issue, score 字段
        """
        conn = get_db()
        cur = conn.cursor()

        # 先获取员工姓名
        cur.execute("SELECT name FROM employees WHERE emp_no = %s", (emp_no,))
        row = cur.fetchone()
        if not row:
            return []

        emp_name = row['name']

        # 处理日期格式（YYYY-MM 转换为 YYYY-MM-DD）
        if start_date and len(start_date) == 7:
            start_date = f"{start_date}-01"
        if end_date and len(end_date) == 7:
            end_date = f"{end_date}-31"

        # 获取违章记录（添加 id 排序确保顺序稳定）
        if start_date and end_date:
            cur.execute("""
                SELECT inspection_date as date,
                       hazard_description as issue,
                       assessment as score
                FROM safety_inspection_records
                WHERE inspected_person = %s
                  AND inspection_date >= %s AND inspection_date <= %s
                ORDER BY inspection_date DESC, id DESC
                LIMIT %s
            """, (emp_name, start_date, end_date, limit))
        else:
            cur.execute("""
                SELECT inspection_date as date,
                       hazard_description as issue,
                       assessment as score
                FROM safety_inspection_records
                WHERE inspected_person = %s
                ORDER BY inspection_date DESC, id DESC
                LIMIT %s
            """, (emp_name, limit))

        return [dict(row) for row in cur.fetchall()]

    @classmethod
    def _get_severe_violations(cls, emp_no: str,
                               start_date: str = None, end_date: str = None) -> List[Dict]:
        """
        获取员工的严重违章记录（扣分>3分或包含特殊关键词）

        Args:
            emp_no: 员工工号
            start_date: 开始日期 (YYYY-MM 或 YYYY-MM-DD 格式)
            end_date: 结束日期 (YYYY-MM 或 YYYY-MM-DD 格式)

        Returns:
            严重违章记录列表
        """
        conn = get_db()
        cur = conn.cursor()

        # 先获取员工姓名
        cur.execute("SELECT name FROM employees WHERE emp_no = %s", (emp_no,))
        row = cur.fetchone()
        if not row:
            return []

        emp_name = row['name']

        # 处理日期格式（YYYY-MM 转换为 YYYY-MM-DD）
        if start_date and len(start_date) == 7:
            start_date = f"{start_date}-01"
        if end_date and len(end_date) == 7:
            end_date = f"{end_date}-31"

        # 获取严重违章记录（包含3分、双倍、红线等关键词，添加 id 排序确保顺序稳定）
        if start_date and end_date:
            cur.execute("""
                SELECT inspection_date as date,
                       hazard_description as issue,
                       assessment as score
                FROM safety_inspection_records
                WHERE inspected_person = %s
                  AND inspection_date >= %s AND inspection_date <= %s
                  AND (assessment LIKE '%%3分%%'
                       OR assessment LIKE '%%双倍%%'
                       OR assessment LIKE '%%红线%%'
                       OR assessment LIKE '%%严重%%')
                ORDER BY inspection_date DESC, id DESC
            """, (emp_name, start_date, end_date))
        else:
            cur.execute("""
                SELECT inspection_date as date,
                       hazard_description as issue,
                       assessment as score
                FROM safety_inspection_records
                WHERE inspected_person = %s
                  AND (assessment LIKE '%%3分%%'
                       OR assessment LIKE '%%双倍%%'
                       OR assessment LIKE '%%红线%%'
                       OR assessment LIKE '%%严重%%')
                ORDER BY inspection_date DESC, id DESC
            """, (emp_name,))

        return [dict(row) for row in cur.fetchall()]

    @classmethod
    def _get_failed_training(cls, emp_no: str,
                             start_date: str = None, end_date: str = None) -> List[Dict]:
        """
        获取员工培训不合格记录

        Args:
            emp_no: 员工工号
            start_date: 开始日期 (YYYY-MM 或 YYYY-MM-DD 格式)
            end_date: 结束日期 (YYYY-MM 或 YYYY-MM-DD 格式)

        Returns:
            培训不合格记录列表，包含 category(项目类别) 和 problem(具体问题)
        """
        conn = get_db()
        cur = conn.cursor()

        # 处理日期格式（YYYY-MM 转换为 YYYY-MM-DD）
        if start_date and len(start_date) == 7:
            start_date = f"{start_date}-01"
        if end_date and len(end_date) == 7:
            end_date = f"{end_date}-31"

        # 添加 id 排序确保顺序稳定
        if start_date and end_date:
            cur.execute("""
                SELECT problem_type as category,
                       specific_problem as problem,
                       training_date as date
                FROM training_records
                WHERE emp_no = %s AND is_disqualified = 1
                  AND training_date >= %s AND training_date <= %s
                ORDER BY training_date DESC, id DESC
            """, (emp_no, start_date, end_date))
        else:
            cur.execute("""
                SELECT problem_type as category,
                       specific_problem as problem,
                       training_date as date
                FROM training_records
                WHERE emp_no = %s AND is_disqualified = 1
                ORDER BY training_date DESC, id DESC
            """, (emp_no,))

        return [dict(row) for row in cur.fetchall()]

    @classmethod
    def analyze_all(
        cls,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        department_path: Optional[str] = None,
        enable_ai_diagnosis: bool = True
    ) -> Dict:
        """
        Main entry point: Perform comprehensive risk analysis.

        Args:
            start_date: Start date (YYYY-MM format), defaults to 12 months ago
            end_date: End date (YYYY-MM format), defaults to current month
            department_path: Optional department filter
            enable_ai_diagnosis: Whether to enable AI diagnosis for high-risk employees

        Returns:
            Dict containing:
            - high_risk_list: List of risk analysis results
            - keyword_cloud: Top keywords from text mining
            - survival_curve: Kaplan-Meier survival data
            - summary: Summary statistics
        """
        # Set default date range (last 12 months)
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m')
        if start_date is None:
            start = datetime.now() - timedelta(days=365)
            start_date = start.strftime('%Y-%m')

        # 1. Load all data
        employees_df = cls._get_employee_data(department_path)
        performance_df = cls._get_performance_data(start_date, end_date)
        safety_df = cls._get_safety_data(start_date, end_date)
        training_df = cls._get_training_data(start_date, end_date)

        if employees_df.empty:
            return {
                "high_risk_list": [],
                "keyword_cloud": [],
                "survival_curve": [{"time": 0, "probability": 1.0}],
                "summary": {
                    "total_employees": 0,
                    "high_risk_count": 0,
                    "anomaly_count": 0
                }
            }

        # 2. Calculate per-employee metrics
        results = []

        # 检查各DataFrame是否有数据和必要的列
        has_perf_data = not performance_df.empty and 'emp_no' in performance_df.columns
        has_safety_data = not safety_df.empty and 'inspected_person' in safety_df.columns
        has_training_data = not training_df.empty and 'emp_no' in training_df.columns

        for _, emp in employees_df.iterrows():
            emp_no = emp['emp_no']
            name = emp['name']

            # Performance metrics
            if has_perf_data:
                emp_perf = performance_df[performance_df['emp_no'] == emp_no].sort_values(['year', 'month'])
                # 确保 score 是数值类型
                perf_scores = pd.to_numeric(emp_perf['score'], errors='coerce').dropna().tolist()
            else:
                perf_scores = []
            perf_mean = float(np.mean(perf_scores)) if perf_scores else 0.0
            perf_var = float(np.var(perf_scores)) if len(perf_scores) > 1 else 0.0
            perf_slope = cls._calculate_performance_slope(perf_scores)

            # Safety metrics (match by name since safety records may not have emp_no)
            if has_safety_data:
                emp_safety = safety_df[safety_df['inspected_person'] == name]
                safety_count = len(emp_safety)
            else:
                safety_count = 0

            # Training metrics
            if has_training_data:
                emp_training = training_df[training_df['emp_no'] == emp_no]
                training_disqualified = emp_training[emp_training['is_disqualified'] == 1]
                training_disqualified_count = len(training_disqualified)
            else:
                training_disqualified_count = 0

            results.append({
                'emp_no': emp_no,
                'name': name,
                'performance_mean': float(perf_mean),
                'performance_var': float(perf_var),
                'performance_slope': float(perf_slope) if perf_slope is not None else 0.0,
                'safety_count': int(safety_count),
                'training_disqualified_count': int(training_disqualified_count),
                'violation_count': int(safety_count + training_disqualified_count)
            })

        results_df = pd.DataFrame(results)
        # 确保数值列类型正确
        numeric_cols = ['performance_mean', 'performance_var', 'performance_slope',
                        'safety_count', 'training_disqualified_count', 'violation_count']
        for col in numeric_cols:
            if col in results_df.columns:
                results_df[col] = pd.to_numeric(results_df[col], errors='coerce').fillna(0)

        # 3. Anomaly detection
        is_anomaly, anomaly_scores = cls._detect_anomalies(results_df)
        results_df['is_anomaly'] = is_anomaly
        results_df['anomaly_score'] = anomaly_scores

        # 4. Calculate composite risk score
        # Normalize each dimension
        if len(results_df) > 0:
            # Safety score (higher count = higher risk)
            results_df['safety_normalized'] = results_df['safety_count'].apply(
                lambda x: cls._normalize_score(x, 0, results_df['safety_count'].max())
            )

            # Training score (higher disqualified count = higher risk)
            results_df['training_normalized'] = results_df['training_disqualified_count'].apply(
                lambda x: cls._normalize_score(x, 0, results_df['training_disqualified_count'].max())
            )

            # Performance slope score (negative slope = higher risk)
            min_slope = results_df['performance_slope'].min()
            max_slope = results_df['performance_slope'].max()
            results_df['performance_normalized'] = results_df['performance_slope'].apply(
                lambda x: cls._normalize_score(-x, -max_slope, -min_slope)  # Invert so negative = high
            )

            # Composite risk score
            results_df['risk_score'] = (
                results_df['safety_normalized'] * cls.WEIGHTS['safety'] +
                results_df['training_normalized'] * cls.WEIGHTS['training'] +
                results_df['performance_normalized'] * cls.WEIGHTS['performance']
            )

        # 5. Generate risk factors
        def get_risk_factors(row):
            factors = []
            if row['performance_slope'] < -0.5:
                factors.append("绩效持续下滑")
            elif row['performance_slope'] < 0:
                factors.append("绩效略有下滑")
            if row['safety_count'] > 0:
                factors.append(f"安全隐患{row['safety_count']}次")
            if row['training_disqualified_count'] > 0:
                factors.append(f"培训不合格{row['training_disqualified_count']}次")
            if row['is_anomaly']:
                factors.append("数据模式异常")
            return factors

        results_df['risk_factors'] = results_df.apply(get_risk_factors, axis=1)

        # 6. Sort by risk score and build output
        results_df = results_df.sort_values('risk_score', ascending=False)

        # 7. AI diagnosis for top risk employees
        high_risk_list = []
        total_employees = len(results_df)
        ai_diagnosis_count = 0

        for idx, row in results_df.iterrows():
            # Calculate percentile
            rank = results_df.index.get_loc(idx) + 1 if isinstance(results_df.index, pd.Index) else idx + 1
            percentile = rank / total_employees

            # Check if AI diagnosis should be triggered
            ai_diagnosis = None
            ai_diagnosis_parsed = None  # 结构化诊断结果
            if enable_ai_diagnosis and ai_diagnosis_count < AIConfig.MAX_DIAGNOSES_PER_RUN:
                if AIDiagnosisService.should_trigger_diagnosis(row['risk_score'], percentile):
                    # 构建完整的risk_data，包含详细记录用于5维度分析
                    risk_data = {
                        # 基础统计数据
                        'performance_slope': row['performance_slope'],
                        'performance_mean': row['performance_mean'],
                        'safety_count': row['safety_count'],
                        'training_disqualified_count': row['training_disqualified_count'],
                        'is_anomaly': row['is_anomaly'],
                        'anomaly_score': row['anomaly_score'],
                        'risk_factors': row['risk_factors'],
                        # 详细记录用于AI诊断（使用日期范围过滤）
                        'recent_violations': cls._get_recent_violations(row['emp_no'], 10, start_date, end_date),
                        'severe_violations': cls._get_severe_violations(row['emp_no'], start_date, end_date),
                        'failed_training': cls._get_failed_training(row['emp_no'], start_date, end_date)
                    }

                    result = AIDiagnosisService.diagnose_sync(
                        emp_no=row['emp_no'],
                        name=row['name'],
                        risk_score=row['risk_score'],
                        risk_data=risk_data
                    )

                    if result.success:
                        ai_diagnosis = result.diagnosis
                        ai_diagnosis_parsed = result.parsed_result  # 获取解析后的结构化结果
                        ai_diagnosis_count += 1

            employee_result = {
                'emp_no': row['emp_no'],
                'name': row['name'],
                'risk_score': round(row['risk_score'], 1),
                'performance_score': round(row['performance_mean'], 1),
                'performance_slope': round(row['performance_slope'], 3),
                'safety_score': round(row['safety_normalized'], 1),
                'safety_count': int(row['safety_count']),
                'training_score': round(row['training_normalized'], 1),
                'training_disqualified_count': int(row['training_disqualified_count']),
                'is_anomaly': bool(row['is_anomaly']),
                'anomaly_score': round(row['anomaly_score'], 1),
                'risk_factors': row['risk_factors'],
                'ai_diagnosis': ai_diagnosis,
                'ai_diagnosis_parsed': ai_diagnosis_parsed  # 新增：结构化诊断结果
            }

            high_risk_list.append(employee_result)

        # 8. Text mining for keyword cloud
        texts = []
        # From safety records
        if not safety_df.empty:
            texts.extend(safety_df['hazard_description'].dropna().tolist())
        # From training records
        if not training_df.empty:
            texts.extend(training_df['specific_problem'].dropna().tolist())

        keyword_result = TextMiningService.analyze_text_batch(
            records=[{'text': t} for t in texts],
            text_fields=['text'],
            top_n=20
        )
        keyword_cloud = keyword_result.get('keyword_cloud', [])

        # 9. Survival analysis
        # Combine safety and training violations for survival analysis
        if not safety_df.empty and 'inspected_person' in safety_df.columns:
            violations_df = safety_df[['inspected_person']].rename(columns={'inspected_person': 'name'})
        else:
            violations_df = pd.DataFrame(columns=['name'])

        if not training_df.empty:
            training_violations = training_df[training_df['is_disqualified'] == 1][['name']]
            violations_df = pd.concat([violations_df, training_violations], ignore_index=True)

        survival_curve = cls._calculate_survival_curve(employees_df, violations_df)

        # 10. Build summary
        high_risk_count = sum(1 for e in high_risk_list if e['risk_score'] >= AIConfig.RISK_THRESHOLD)
        anomaly_count = sum(1 for e in high_risk_list if e['is_anomaly'])

        return {
            "high_risk_list": high_risk_list,
            "keyword_cloud": keyword_cloud,
            "survival_curve": survival_curve,
            "summary": {
                "total_employees": total_employees,
                "high_risk_count": high_risk_count,
                "anomaly_count": anomaly_count,
                "date_range": {
                    "start": start_date,
                    "end": end_date
                },
                "ai_diagnoses_performed": ai_diagnosis_count
            }
        }


# Singleton instance
risk_mining_service = RiskMiningService()
