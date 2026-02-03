#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Diagnosis Service for high-risk employee behavior analysis.
Supports multiple AI providers configured through database.

5维度专业诊断模板：
1. 关键风险画像 - 高频违章点、严重违章点、时空规律
2. 培训关联分析 - 培训失格与违章关联性
3. 根因深度定性 - 技能型/习惯型/状态型分类
4. 预测性预警 - 未来30天风险预测
5. 精准帮扶方案 - 针对性帮扶措施

Token节省机制：
- 数据指纹缓存：对输入数据生成MD5哈希，相同数据直接返回缓存结果
- 按需触发：仅对高风险人员（risk_score >= 80 或 前5%）显示AI分析按钮
"""
import json
import re
import hashlib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class DiagnosisResult:
    """AI diagnosis result - 结构化诊断结果"""
    success: bool
    diagnosis: Optional[str] = None  # 原始诊断文本（JSON字符串）
    error: Optional[str] = None
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None
    provider_name: Optional[str] = None
    # 解析后的结构化数据
    parsed_result: Optional[Dict] = field(default=None)
    # 数据来源标识：cache（缓存命中）或 api（新调用API）
    source: str = field(default="api")

    @property
    def summary(self) -> Optional[str]:
        """一句话诊断结论"""
        if self.parsed_result:
            return self.parsed_result.get('summary')
        return None

    @property
    def root_cause_type(self) -> Optional[str]:
        """根因类型：技能型/习惯型/状态型"""
        if self.parsed_result:
            return self.parsed_result.get('root_cause_type')
        return None

    @property
    def measures(self) -> List[str]:
        """帮扶措施列表"""
        if self.parsed_result:
            return self.parsed_result.get('measures', [])
        return []

    @property
    def prediction(self) -> Optional[str]:
        """风险预测"""
        if self.parsed_result:
            return self.parsed_result.get('prediction')
        return None


class AIDiagnosisService:
    """
    AI-powered behavior diagnosis service for high-risk employees.
    Implements cost control by only triggering for employees above risk threshold.
    Now reads configuration from database instead of environment variables.
    """

    # Risk threshold for triggering AI diagnosis
    RISK_THRESHOLD = 80.0
    TOP_PERCENT_THRESHOLD = 0.05  # Top 5%

    # 缓存配置
    CACHE_ENABLED = True  # 是否启用缓存

    # 5维度专业诊断提示语模板（基础框架，分析要求部分从数据库动态加载）
    DIAGNOSIS_PROMPT_TEMPLATE_BASE = """你是一位拥有20年经验的轨道交通安全管理专家，擅长通过数据挖掘员工的安全隐患，并制定针对性的改进计划。

# Task (任务)
请根据提供的该员工历史数据，进行深度风险诊断。

# Data Context (数据背景)
- 工号：{emp_no}（已完全脱敏）
- 姓名：{name}（已完全脱敏）
- 综合风险评分：{risk_score}分（满分100）

**重要提示**：以下数据已进行隐私脱敏处理：
- 所有地名信息已替换为通用标识符（如[地点]、[线路]、[站点]等）
- 员工个人身份信息已完全匿名化
- 请基于脱敏后的数据进行分析，不要尝试推测具体地理位置或个人身份

{data_context}

# Analysis Requirements (分析要求)
请严格按照以下 5 个维度进行推理和输出：

{analysis_requirements}

# Output Format (输出格式)
请直接输出 JSON 格式，不要包含Markdown标记，字段如下：
{{
  "summary": "一句话诊断结论",
  "frequent_issues": ["高频问题1", "高频问题2", "高频问题3"],
  "severe_issues": [{{"issue": "严重问题描述", "score": "扣分值"}}],
  "time_pattern": "时空规律分析结果",
  "training_gap": "培训关联分析结果",
  "root_cause_type": "技能型/习惯型/状态型",
  "root_cause_analysis": "具体的根因分析文本",
  "prediction": "预测的具体风险",
  "measures": ["具体帮扶措施1", "具体帮扶措施2"]
}}
"""

    @classmethod
    def _get_analysis_requirements(cls) -> str:
        """
        从数据库读取 5 维度分析要求配置

        配置存储在 ai_analysis_config 表中，用户可通过前端界面修改。
        如果数据库不可用，AIPromptConfigService 会使用内置的 FALLBACK_CONFIGS。

        Returns:
            格式化的分析要求文本
        """
        from services.ai_prompt_config_service import AIPromptConfigService
        return AIPromptConfigService.build_analysis_requirements()

    @classmethod
    def _build_prompt(cls, emp_no: str, name: str, risk_score: str, data_context: str) -> str:
        """
        构建完整的 AI 诊断提示语

        Args:
            emp_no: 脱敏后的工号
            name: 脱敏后的姓名
            risk_score: 风险评分字符串
            data_context: 数据上下文

        Returns:
            完整的提示语文本
        """
        analysis_requirements = cls._get_analysis_requirements()

        return cls.DIAGNOSIS_PROMPT_TEMPLATE_BASE.format(
            emp_no=emp_no,
            name=name,
            risk_score=risk_score,
            data_context=data_context,
            analysis_requirements=analysis_requirements
        )

    @classmethod
    def _get_ai_config(cls) -> Optional[Dict]:
        """
        Get AI configuration from database.
        Falls back to environment variables if no database config exists.
        """
        try:
            from services.ai_config_service import AIConfigService
            provider = AIConfigService.get_default_provider()
            if provider:
                return provider
            if AIConfigService.has_providers():
                return None
        except Exception as e:
            print(f"Failed to load AI config from database: {e}")

        # Fallback to environment variables for backward compatibility
        import os
        api_key = os.environ.get("AI_API_KEY", "")
        if api_key:
            return {
                'id': None,
                'name': 'Environment Config',
                'provider_type': os.environ.get("AI_PROVIDER", "openrouter"),
                'api_key': api_key,
                'base_url': os.environ.get("AI_BASE_URL", "https://openrouter.ai/api/v1"),
                'model': os.environ.get("AI_MODEL", "anthropic/claude-3-haiku"),
                'timeout': int(os.environ.get("AI_TIMEOUT", "30")),
                'max_tokens': 500,
                'temperature': 0.7,
                'extra_headers': {}
            }

        return None

    @classmethod
    def _log_usage(cls, provider_id: Optional[int], provider_name: str, model: str,
                   tokens: int, success: bool, error_message: Optional[str]):
        """Log AI usage to database"""
        try:
            from services.ai_config_service import AIConfigService
            AIConfigService.log_usage(
                provider_id or 0,
                provider_name,
                model,
                tokens,
                success,
                error_message,
                'diagnosis'
            )
        except Exception as e:
            print(f"Failed to log AI usage: {e}")

    @classmethod
    def _compute_data_hash(cls, data_context: str) -> str:
        """
        计算数据上下文的MD5哈希值，用于缓存去重。

        Args:
            data_context: 发送给AI的数据上下文字符串

        Returns:
            MD5哈希字符串
        """
        return hashlib.md5(data_context.encode('utf-8')).hexdigest()

    @classmethod
    def _build_cache_key(cls, risk_data: Dict) -> str:
        """
        构建用于缓存的稳定数据键（全量方案）

        只使用数据库中的原始数据（违章记录、培训记录），
        排除动态计算的值（anomaly_score、performance_slope等），
        确保相同的原始数据产生相同的哈希值。

        Args:
            risk_data: 包含员工风险数据的字典

        Returns:
            稳定的数据上下文字符串，用于哈希计算
        """
        parts = []

        # 1. 所有违章记录（按日期排序确保顺序稳定）
        if 'all_violations' in risk_data and risk_data['all_violations']:
            violations = sorted(
                risk_data['all_violations'],
                key=lambda x: (x.get('date', ''), x.get('issue', ''))
            )
            for v in violations:
                parts.append(f"V:{v.get('date', '')}|{v.get('issue', '')}|{v.get('score', '')}")

        # 2. 培训不合格记录
        if 'failed_training' in risk_data and risk_data['failed_training']:
            training = sorted(
                risk_data['failed_training'],
                key=lambda x: (x.get('category', ''), x.get('problem', ''))
            )
            for t in training:
                parts.append(f"T:{t.get('category', '')}|{t.get('problem', '')}")

        # 4. 统计数据（使用整数，避免浮点精度问题）
        parts.append(f"C:{risk_data.get('safety_count', 0)}|{risk_data.get('training_disqualified_count', 0)}")

        return "||".join(parts)

    @classmethod
    def _get_cached_result(cls, emp_no: str, data_hash: str) -> Optional[Dict]:
        """
        从缓存中查询已有的AI分析结果。

        Args:
            emp_no: 员工工号
            data_hash: 数据指纹（MD5哈希）

        Returns:
            缓存的结果字典，未命中返回None
        """
        if not cls.CACHE_ENABLED:
            return None

        try:
            from models.database import get_db
            conn = get_db()
            cur = conn.cursor()

            cur.execute("""
                SELECT ai_result, provider_name, model, tokens_used, created_at
                FROM ai_analysis_history
                WHERE emp_no = %s AND data_hash = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (emp_no, data_hash))
            row = cur.fetchone()

            if row:
                return {
                    'ai_result': row['ai_result'],
                    'provider_name': row['provider_name'],
                    'model': row['model'],
                    'tokens_used': row['tokens_used'],
                    'created_at': row['created_at']
                }
            return None
        except Exception as e:
            print(f"Cache lookup failed: {e}")
            return None

    @classmethod
    def _save_to_cache(cls, emp_no: str, data_hash: str, time_window: str,
                       ai_result: str, provider_name: str, model: str, tokens_used: int):
        """
        将AI分析结果保存到缓存。

        Args:
            emp_no: 员工工号
            data_hash: 数据指纹（MD5哈希）
            time_window: 数据时间范围（如 "2025.12-2026.01"）
            ai_result: AI返回的原始结果（JSON字符串）
            provider_name: AI提供商名称
            model: 使用的模型
            tokens_used: 消耗的token数
        """
        if not cls.CACHE_ENABLED:
            return

        try:
            from models.database import get_db
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                REPLACE INTO ai_analysis_history
                (emp_no, data_hash, time_window, ai_result, provider_name, model, tokens_used)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (emp_no, data_hash, time_window, ai_result, provider_name, model, tokens_used))
            conn.commit()
        except Exception as e:
            print(f"Cache save failed: {e}")

    @classmethod
    def should_trigger_diagnosis(
        cls,
        risk_score: float,
        rank_percentile: float
    ) -> bool:
        """
        Determine if AI diagnosis should be triggered based on risk score and ranking.

        Args:
            risk_score: Employee's composite risk score (0-100)
            rank_percentile: Employee's percentile ranking (0.0 = highest risk)

        Returns:
            True if diagnosis should be triggered
        """
        return risk_score >= cls.RISK_THRESHOLD or rank_percentile <= cls.TOP_PERCENT_THRESHOLD

    @classmethod
    def _build_history_summary(cls, risk_data: Dict) -> str:
        """
        Build a detailed history summary from risk data for the prompt.
        Provides specific data points for AI analysis.

        Args:
            risk_data: Dictionary containing employee risk factors

        Returns:
            Detailed history string with specific metrics
        """
        sections = []

        # === 绩效数据 ===
        perf_items = []
        if 'performance_mean' in risk_data:
            mean = risk_data['performance_mean']
            perf_items.append(f"平均绩效分：{mean:.1f}分")
        if 'performance_std' in risk_data:
            std = risk_data['performance_std']
            perf_items.append(f"绩效波动（标准差）：{std:.2f}")
        if 'performance_slope' in risk_data:
            slope = risk_data['performance_slope']
            trend = "下滑" if slope < 0 else "上升" if slope > 0 else "持平"
            perf_items.append(f"绩效趋势：{trend}（斜率{slope:.2f}）")
        if 'performance_months' in risk_data:
            months = risk_data['performance_months']
            perf_items.append(f"统计月数：{months}个月")

        if perf_items:
            sections.append("### 绩效表现\n" + "\n".join(f"- {item}" for item in perf_items))

        # === 安全记录 ===
        safety_items = []
        if 'safety_count' in risk_data:
            count = risk_data['safety_count']
            safety_items.append(f"安全隐患/违章次数：{count}次")
        if 'safety_score' in risk_data:
            score = risk_data['safety_score']
            safety_items.append(f"安全维度得分：{score:.1f}分（满分100，越低越差）")

        if safety_items:
            sections.append("### 安全记录\n" + "\n".join(f"- {item}" for item in safety_items))

        # === 培训记录 ===
        training_items = []
        if 'training_disqualified_count' in risk_data:
            count = risk_data['training_disqualified_count']
            if count > 0:
                training_items.append(f"培训不合格次数：{count}次")
        if 'training_score' in risk_data:
            score = risk_data['training_score']
            training_items.append(f"培训维度得分：{score:.1f}分")

        if training_items:
            sections.append("### 培训情况\n" + "\n".join(f"- {item}" for item in training_items))

        # === 异常检测 ===
        if risk_data.get('is_anomaly'):
            anomaly_score = risk_data.get('anomaly_score', 0)
            sections.append(f"### 异常检测\n- 孤立森林算法检测到数据异常（异常分数：{anomaly_score}）\n- 说明：该员工的数据模式与大多数员工不同，可能存在隐性问题")

        # === 风险因素汇总 ===
        if 'risk_factors' in risk_data and risk_data['risk_factors']:
            factors = risk_data['risk_factors']
            sections.append("### 主要风险因素\n" + "\n".join(f"- {f}" for f in factors))

        # === 排名信息 ===
        if 'rank' in risk_data and 'total_employees' in risk_data:
            rank = risk_data['rank']
            total = risk_data['total_employees']
            percentile = (rank / total) * 100
            sections.append(f"### 风险排名\n- 在{total}名员工中排第{rank}位（前{percentile:.1f}%）")

        return "\n\n".join(sections) if sections else "暂无具体历史记录"

    @classmethod
    def _build_data_context(cls, risk_data: Dict) -> str:
        """
        构建AI诊断所需的数据上下文（全量方案 - 让AI根据提示语自行判断严重性）

        重要脱敏措施：
        - 移除所有地名信息（郑州、河南、地铁线路、站点等）
        - 脱敏员工姓名和工号（在调用此方法前已处理）
        - 保留业务相关的违章类型和培训问题，以便AI分析

        Args:
            risk_data: 包含员工风险数据的字典，需要包含：
                - all_violations: 所有违章记录列表（全量，不预筛选）
                - failed_training: 培训不合格记录列表
                - performance_slope: 绩效趋势斜率
                - is_anomaly: 是否为异常数据

        Returns:
            脱敏后的格式化数据上下文字符串
        """
        sections = []

        # 1. 所有违章记录（全量方案 - 不再预筛选严重违章）
        # 让AI根据提示语中配置的严重性标准（如>3分、>5分等）自行判断
        # 【脱敏处理】移除违章描述中的地名信息
        if 'all_violations' in risk_data and risk_data['all_violations']:
            violations = risk_data['all_violations']
            violation_lines = []
            for v in violations:
                date = v.get('date', '未知日期')
                issue = v.get('issue', '未知问题')
                score = v.get('score', '未知')

                # 脱敏违章描述中的地名
                anonymized_issue = cls._anonymize_location(issue)

                violation_lines.append(f"- {date}: {anonymized_issue} (考核: {score})")
            if violation_lines:
                sections.append("[所有违章记录]:\n" + "\n".join(violation_lines))

        # 2. 培训薄弱点
        # 【脱敏处理】移除培训问题描述中的地名信息
        if 'failed_training' in risk_data and risk_data['failed_training']:
            training = risk_data['failed_training']
            training_lines = []
            for t in training:
                category = t.get('category', '未知类别')
                problem = t.get('problem', '未知问题')

                # 脱敏类别和问题描述中的地名
                anonymized_category = cls._anonymize_location(category)
                anonymized_problem = cls._anonymize_location(problem)

                training_lines.append(f"- {anonymized_category}: {anonymized_problem}")
            if training_lines:
                sections.append("[培训薄弱点]:\n" + "\n".join(training_lines))

        # 4. 绩效趋势
        if 'performance_slope' in risk_data:
            slope = risk_data['performance_slope']
            trend = "下滑" if slope < 0 else "上升" if slope > 0 else "持平"
            perf_mean = risk_data.get('performance_mean', 0)
            sections.append(f"[绩效趋势]:\n- 平均绩效: {perf_mean:.1f}分\n- 趋势: {trend}(斜率: {slope:.3f})")

        # 5. 异常检测结果
        if risk_data.get('is_anomaly'):
            anomaly_score = risk_data.get('anomaly_score', 0)
            sections.append(f"[异常检测]:\n- 孤立森林算法检测到数据异常(异常分数: {anomaly_score:.1f})\n- 说明: 该员工数据模式与大多数员工不同")

        # 6. 安全统计
        safety_count = risk_data.get('safety_count', 0)
        training_count = risk_data.get('training_disqualified_count', 0)
        if safety_count > 0 or training_count > 0:
            sections.append(f"[统计汇总]:\n- 安全隐患/违章次数: {safety_count}次\n- 培训不合格次数: {training_count}次")

        return "\n\n".join(sections) if sections else "暂无详细历史记录"

    @classmethod
    def _parse_diagnosis_response(cls, response_text: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        解析AI返回的JSON诊断结果

        Args:
            response_text: AI返回的原始文本

        Returns:
            Tuple of (success, parsed_dict, error_message)
        """
        try:
            # 清理响应文本
            cleaned = response_text.strip()

            # 移除可能的markdown代码块标记
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            if cleaned.startswith('```'):
                cleaned = cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            # 尝试直接解析JSON
            result = json.loads(cleaned)

            # 验证必需字段
            required_fields = ['summary', 'root_cause_type', 'measures']
            missing = [f for f in required_fields if f not in result]
            if missing:
                return False, None, f"缺少必需字段: {', '.join(missing)}"

            # 验证root_cause_type的值
            valid_types = ['技能型', '习惯型', '状态型']
            if result.get('root_cause_type') not in valid_types:
                # 尝试模糊匹配
                rct = result.get('root_cause_type', '')
                if '技能' in rct:
                    result['root_cause_type'] = '技能型'
                elif '习惯' in rct:
                    result['root_cause_type'] = '习惯型'
                elif '状态' in rct:
                    result['root_cause_type'] = '状态型'

            return True, result, None

        except json.JSONDecodeError as e:
            # 尝试提取JSON部分（AI可能添加了额外文本）
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    return True, result, None
                except json.JSONDecodeError:
                    pass

            return False, None, f"JSON解析失败: {str(e)}"

    @classmethod
    def _anonymize_name(cls, name: str) -> str:
        """
        Anonymize employee name completely for privacy.
        完全脱敏姓名，避免任何个人信息泄露

        Example: 张三 → 员工A
        """
        if not name:
            return "员工"
        # 使用名字的哈希值生成稳定的匿名标识符
        hash_val = hash(name) % 26
        return f"员工{chr(65 + hash_val)}"  # 员工A, 员工B, ...

    @classmethod
    def _anonymize_emp_no(cls, emp_no: str) -> str:
        """
        Anonymize employee number completely for privacy.
        完全脱敏工号，避免任何工号信息泄露

        Example: G12345 → ID****
        """
        if not emp_no:
            return "ID****"
        # 完全替换为通用标识符
        return "ID****"

    @classmethod
    def _anonymize_location(cls, text: str) -> str:
        """
        Remove sensitive location information while preserving station names and line numbers.
        移除敏感地名信息（城市、省份、区域），但保留站点名称和线路编号以便AI准确分析

        脱敏策略：
        - 保留：站点名称（如"紫荆山站"、"火车站"）、线路编号（如"1号线"）
        - 脱敏：城市名称、省份名称、行政区域、详细地址

        Args:
            text: 原始文本

        Returns:
            脱敏后的文本
        """
        if not text:
            return text

        import re

        # 按优先级顺序替换（先替换更长、更具体的关键词，避免重复替换）
        anonymized = text

        # 1. 替换区域和城市名称（保护企业具体位置）
        # 注意：先替换更长的组合词，避免部分替换
        regions = [
            # 先替换完整的"XX市"、"XX省"组合
            ('郑州市', '[城市]'),
            ('河南省', '[省份]'),
            # 再替换区域名称（包含城市名）
            ('郑东新区', '[区域]'),
            ('金水区', '[区域]'),
            ('二七区', '[区域]'),
            ('中原区', '[区域]'),
            ('管城区', '[区域]'),
            ('惠济区', '[区域]'),
            ('上街区', '[区域]'),
            ('航空港区', '[区域]'),
            # 最后替换单独的城市/省份名
            ('郑州', '[城市]'),
            ('河南', '[省份]'),
        ]
        for keyword, replacement in regions:
            anonymized = anonymized.replace(keyword, replacement)

        # 2. 使用正则移除可能的详细地址模式
        # 例如: "位于XX路XX号" -> "位于[地点]"
        anonymized = re.sub(r'位于[^，。；]+[路街道巷里][\d号]*', '位于[地点]', anonymized)
        # 匹配 "数字+路/街/道/巷/里+可能的门牌号"（但不影响"1号线"这样的表述）
        anonymized = re.sub(r'(?<!\d号线)\d+[路街道巷里][\d号]*', '[路段]', anonymized)

        # 注意：站点名称、线路编号、站台等词汇都保留，不做脱敏处理
        # 这些信息对AI分析时空规律和违章模式很重要

        return anonymized

    @classmethod
    async def diagnose_async(
        cls,
        emp_no: str,
        name: str,
        risk_score: float,
        risk_data: Dict
    ) -> DiagnosisResult:
        """
        Perform AI diagnosis asynchronously.

        Args:
            emp_no: Employee number
            name: Employee name (will be anonymized)
            risk_score: Composite risk score
            risk_data: Dictionary containing risk factors and history

        Returns:
            DiagnosisResult with diagnosis text or error
        """
        try:
            import httpx
        except ImportError:
            return DiagnosisResult(
                success=False,
                error="httpx library not installed. Please install with: pip install httpx"
            )

        # Get AI configuration from database
        config = cls._get_ai_config()
        if not config:
            return DiagnosisResult(
                success=False,
                error="AI未配置。请在系统设置中添加AI提供商配置。"
            )

        if not config.get('api_key'):
            return DiagnosisResult(
                success=False,
                error="AI API Key未配置。请在系统设置中配置API密钥。"
            )

        # Build prompt with new 5-dimension data context (从数据库动态加载分析要求)
        data_context = cls._build_data_context(risk_data)
        prompt = cls._build_prompt(
            emp_no=cls._anonymize_emp_no(emp_no),
            name=cls._anonymize_name(name),
            risk_score=f"{risk_score:.1f}",
            data_context=data_context
        )

        # Extract config values
        provider_id = config.get('id')
        provider_name = config.get('name', 'Unknown')
        provider_type = config.get('provider_type', 'openai')
        api_key = config['api_key']
        model = config.get('model', 'gpt-3.5-turbo')
        base_url = config.get('base_url', 'https://api.openai.com/v1')
        timeout = config.get('timeout', 30)
        # 5维度诊断需要更多token输出（JSON格式至少需要1500 tokens）
        max_tokens = max(config.get('max_tokens', 1500), 1500)
        # Gemini 免费版 maxOutputTokens 上限约8192，超过会报错
        if provider_type == 'gemini' and max_tokens > 8000:
            max_tokens = 8000
        temperature = config.get('temperature', 0.7)
        extra_headers = config.get('extra_headers', {})

        # Prepare request headers
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        # Add extra headers from config
        if extra_headers:
            headers.update(extra_headers)

        # Anthropic API uses different auth header
        if provider_type == 'anthropic':
            headers['x-api-key'] = api_key
            del headers['Authorization']

        # Gemini API - 不需要 Authorization header
        if provider_type == 'gemini':
            headers.pop('Authorization', None)

        # 根据提供商类型构建不同的请求格式
        if provider_type == 'gemini':
            # Gemini API 格式
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens
                }
            }
            endpoint = f"{base_url}/models/{model}:generateContent?key={api_key}"
        else:
            payload = {
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            # Determine API endpoint
            if provider_type == 'anthropic':
                endpoint = f"{base_url}/messages"
            else:
                endpoint = f"{base_url}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    endpoint,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()

                data = response.json()

                # Parse response based on provider
                if provider_type == 'gemini':
                    # Gemini 响应格式
                    candidates = data.get('candidates', [{}])
                    if candidates:
                        parts = candidates[0].get('content', {}).get('parts', [{}])
                        diagnosis = parts[0].get('text', '').strip() if parts else ''
                    else:
                        diagnosis = ''
                    usage = data.get('usageMetadata', {})
                    tokens_used = usage.get('totalTokenCount', 0)
                elif provider_type == 'anthropic':
                    diagnosis = data.get('content', [{}])[0].get('text', '').strip()
                    tokens_used = data.get('usage', {}).get('input_tokens', 0) + \
                                  data.get('usage', {}).get('output_tokens', 0)
                else:
                    diagnosis = data['choices'][0]['message']['content'].strip()
                    tokens_used = data.get('usage', {}).get('total_tokens', 0)

                # Log successful usage
                cls._log_usage(provider_id, provider_name, model, tokens_used, True, None)

                # Parse JSON response for structured result
                parse_success, parsed_result, parse_error = cls._parse_diagnosis_response(diagnosis)

                return DiagnosisResult(
                    success=True,
                    diagnosis=diagnosis,
                    model_used=model,
                    tokens_used=tokens_used,
                    provider_name=provider_name,
                    parsed_result=parsed_result if parse_success else None
                )

        except httpx.HTTPStatusError as e:
            error_msg = f"API请求失败: {e.response.status_code}"
            try:
                error_detail = e.response.json()
                if 'error' in error_detail:
                    error_msg = error_detail['error'].get('message', error_msg)
            except:
                pass
            cls._log_usage(provider_id, provider_name, model, 0, False, error_msg)
            return DiagnosisResult(
                success=False,
                error=error_msg,
                provider_name=provider_name
            )
        except httpx.RequestError as e:
            error_msg = f"网络错误: {str(e)}"
            cls._log_usage(provider_id, provider_name, model, 0, False, error_msg)
            return DiagnosisResult(
                success=False,
                error=error_msg,
                provider_name=provider_name
            )
        except Exception as e:
            error_msg = f"未知错误: {str(e)}"
            cls._log_usage(provider_id, provider_name, model, 0, False, error_msg)
            return DiagnosisResult(
                success=False,
                error=error_msg,
                provider_name=provider_name
            )

    @classmethod
    def diagnose_sync(
        cls,
        emp_no: str,
        name: str,
        risk_score: float,
        risk_data: Dict,
        time_window: Optional[str] = None
    ) -> DiagnosisResult:
        """
        Synchronous version of diagnose for compatibility.
        Implements caching mechanism to save API tokens.

        Args:
            emp_no: Employee number
            name: Employee name (will be anonymized)
            risk_score: Composite risk score
            risk_data: Dictionary containing risk factors and history
            time_window: Optional time window string (e.g., "2025.12-2026.01")

        Returns:
            DiagnosisResult with diagnosis text or error
        """
        try:
            import httpx
        except ImportError:
            return DiagnosisResult(
                success=False,
                error="httpx library not installed. Please install with: pip install httpx"
            )

        # Get AI configuration from database
        config = cls._get_ai_config()
        if not config:
            return DiagnosisResult(
                success=False,
                error="AI未配置。请在系统设置中添加AI提供商配置。"
            )

        if not config.get('api_key'):
            return DiagnosisResult(
                success=False,
                error="AI API Key未配置。请在系统设置中配置API密钥。"
            )

        # ====== 缓存检查逻辑（省Token核心）======
        # 使用稳定的缓存键计算哈希（只包含原始数据，排除动态计算值）
        cache_key = cls._build_cache_key(risk_data)
        data_hash = cls._compute_data_hash(cache_key)

        # 查询缓存
        cached = cls._get_cached_result(emp_no, data_hash)
        if cached:
            # 缓存命中！直接返回，消耗0 Token
            cached_diagnosis = cached['ai_result']
            parse_success, parsed_result, _ = cls._parse_diagnosis_response(cached_diagnosis)
            return DiagnosisResult(
                success=True,
                diagnosis=cached_diagnosis,
                model_used=cached.get('model'),
                tokens_used=0,  # 缓存命中不消耗token
                provider_name=cached.get('provider_name'),
                parsed_result=parsed_result if parse_success else None,
                source="cache"  # 标记数据来源为缓存
            )

        # ====== 缓存未命中，调用API ======
        # 构建完整的数据上下文用于AI分析（从数据库动态加载分析要求）
        data_context = cls._build_data_context(risk_data)

        prompt = cls._build_prompt(
            emp_no=cls._anonymize_emp_no(emp_no),
            name=cls._anonymize_name(name),
            risk_score=f"{risk_score:.1f}",
            data_context=data_context
        )

        # Extract config values
        provider_id = config.get('id')
        provider_name = config.get('name', 'Unknown')
        provider_type = config.get('provider_type', 'openai')
        api_key = config['api_key']
        model = config.get('model', 'gpt-3.5-turbo')
        base_url = config.get('base_url', 'https://api.openai.com/v1')
        timeout = config.get('timeout', 30)
        # 5维度诊断需要更多token输出（JSON格式至少需要1500 tokens）
        max_tokens = max(config.get('max_tokens', 1500), 1500)
        # Gemini 免费版 maxOutputTokens 上限约8192，超过会报错
        if provider_type == 'gemini' and max_tokens > 8000:
            max_tokens = 8000
        temperature = config.get('temperature', 0.7)
        extra_headers = config.get('extra_headers', {})

        # Prepare request headers
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        # Add extra headers from config
        if extra_headers:
            headers.update(extra_headers)

        # Anthropic API uses different auth header
        if provider_type == 'anthropic':
            headers['x-api-key'] = api_key
            del headers['Authorization']

        # Gemini API - 不需要 Authorization header
        if provider_type == 'gemini':
            headers.pop('Authorization', None)

        # 根据提供商类型构建不同的请求格式
        if provider_type == 'gemini':
            # Gemini API 格式
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens
                }
            }
            endpoint = f"{base_url}/models/{model}:generateContent?key={api_key}"
        else:
            payload = {
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            # Determine API endpoint
            if provider_type == 'anthropic':
                endpoint = f"{base_url}/messages"
            else:
                endpoint = f"{base_url}/chat/completions"

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    endpoint,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()

                data = response.json()

                # Parse response based on provider
                if provider_type == 'gemini':
                    # Gemini 响应格式
                    candidates = data.get('candidates', [{}])
                    if candidates:
                        parts = candidates[0].get('content', {}).get('parts', [{}])
                        diagnosis = parts[0].get('text', '').strip() if parts else ''
                    else:
                        diagnosis = ''
                    usage = data.get('usageMetadata', {})
                    tokens_used = usage.get('totalTokenCount', 0)
                elif provider_type == 'anthropic':
                    diagnosis = data.get('content', [{}])[0].get('text', '').strip()
                    tokens_used = data.get('usage', {}).get('input_tokens', 0) + \
                                  data.get('usage', {}).get('output_tokens', 0)
                else:
                    diagnosis = data['choices'][0]['message']['content'].strip()
                    tokens_used = data.get('usage', {}).get('total_tokens', 0)

                # Log successful usage
                cls._log_usage(provider_id, provider_name, model, tokens_used, True, None)

                # Parse JSON response for structured result
                parse_success, parsed_result, parse_error = cls._parse_diagnosis_response(diagnosis)

                # ====== 保存到缓存（供下次复用）======
                cls._save_to_cache(
                    emp_no=emp_no,
                    data_hash=data_hash,
                    time_window=time_window or "",
                    ai_result=diagnosis,
                    provider_name=provider_name,
                    model=model,
                    tokens_used=tokens_used
                )

                return DiagnosisResult(
                    success=True,
                    diagnosis=diagnosis,
                    model_used=model,
                    tokens_used=tokens_used,
                    provider_name=provider_name,
                    parsed_result=parsed_result if parse_success else None,
                    source="api"  # 标记数据来源为新API调用
                )

        except httpx.HTTPStatusError as e:
            error_msg = f"API请求失败: {e.response.status_code}"
            try:
                error_detail = e.response.json()
                if 'error' in error_detail:
                    error_msg = error_detail['error'].get('message', error_msg)
            except:
                pass
            cls._log_usage(provider_id, provider_name, model, 0, False, error_msg)
            return DiagnosisResult(
                success=False,
                error=error_msg,
                provider_name=provider_name
            )
        except httpx.RequestError as e:
            error_msg = f"网络错误: {str(e)}"
            cls._log_usage(provider_id, provider_name, model, 0, False, error_msg)
            return DiagnosisResult(
                success=False,
                error=error_msg,
                provider_name=provider_name
            )
        except Exception as e:
            error_msg = f"未知错误: {str(e)}"
            cls._log_usage(provider_id, provider_name, model, 0, False, error_msg)
            return DiagnosisResult(
                success=False,
                error=error_msg,
                provider_name=provider_name
            )

    @classmethod
    def is_configured(cls) -> bool:
        """Check if AI is properly configured"""
        config = cls._get_ai_config()
        return config is not None and bool(config.get('api_key'))


# Singleton instance
ai_diagnosis_service = AIDiagnosisService()
