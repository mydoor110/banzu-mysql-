#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Prompt Configuration Service

管理 AI 分析的 5 维度提示语配置：
1. 关键风险画像 (risk_profile)
2. 培训关联分析 (training_gap)
3. 根因深度定性 (root_cause)
4. 预测性预警 (prediction)
5. 精准帮扶方案 (measures)

提供以下功能：
- 获取所有配置
- 更新单个配置的 current_instruction
- 重置单个配置为默认值
- 重置所有配置为默认值
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime


class AIPromptConfigService:
    """AI 提示语配置服务"""

    # 硬编码的默认配置（作为容错回退使用）
    FALLBACK_CONFIGS = {
        "risk_profile": {
            "title": "1. 关键风险画像",
            "instruction": """1. 高频违章点：指出出现频率最高的前3个问题类型。
2. 严重违章点：提取所有考核分值 > 3分（或双倍扣分）的严重问题。
3. 时空规律：分析这些问题是否集中在特定时间（如早晚班）或特定作业环节（如出入库、正线折返）。"""
        },
        "training_gap": {
            "title": "2. 培训关联分析",
            "instruction": """1. 结合"培训失格"和"培训具体问题"记录，分析他的**实操弱项**是否直接导致了上述违章？
2. (例如：培训中多次"车门故障"不合格，现场是否也发生了车门操作违章？)"""
        },
        "root_cause": {
            "title": "3. 根因深度定性",
            "instruction": """请判断该员工的主要风险来源是以下哪一种，并给出理由：
A. **技能型短板** (Skill Deficit): 业务生疏，不知道怎么做。
B. **习惯性违章** (Habitual Violation): 知道标准，但为了省事简化作业。
C. **状态型异常** (State Anomaly): 近期家庭变故、疲劳或情绪波动导致。"""
        },
        "prediction": {
            "title": "4. 预测性预警",
            "instruction": """基于现有趋势，如果不仅行干预，预测该员工在未来 30 天内最可能发生的**具体安全事故**是什么？（如：冒进信号、夹人夹物等）。"""
        },
        "measures": {
            "title": "5. 精准帮扶方案",
            "instruction": """针对上述原因，给出具体的帮扶措施（不要给万金油建议）。
- **技能型**：建议重修哪一门具体课程？
- **习惯型**：建议采取何种检查手段（如：加密视频抽查频次、跟车添乘）？"""
        }
    }

    # 配置键的顺序（用于构建提示语）
    CONFIG_ORDER = ["risk_profile", "training_gap", "root_cause", "prediction", "measures"]

    @classmethod
    def get_all_configs(cls) -> List[Dict]:
        """
        获取所有 AI 提示语配置

        Returns:
            配置列表，按显示顺序排列
        """
        try:
            from models.database import get_db
            conn = get_db()
            cur = conn.cursor()

            cur.execute("""
                SELECT id, config_key, title, default_instruction, current_instruction,
                       created_at, updated_at
                FROM ai_analysis_config
                ORDER BY id ASC
            """)
            rows = cur.fetchall()

            if not rows:
                # 数据库中没有配置，返回硬编码默认值
                return cls._get_fallback_configs_list()

            return [
                {
                    'id': row['id'],
                    'config_key': row['config_key'],
                    'title': row['title'],
                    'default_instruction': row['default_instruction'],
                    'current_instruction': row['current_instruction'],
                    'is_modified': row['current_instruction'] != row['default_instruction'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                }
                for row in rows
            ]
        except Exception as e:
            print(f"[AIPromptConfigService] 获取配置失败: {e}")
            return cls._get_fallback_configs_list()

    @classmethod
    def _get_fallback_configs_list(cls) -> List[Dict]:
        """将硬编码的 FALLBACK_CONFIGS 转换为列表格式"""
        result = []
        for i, key in enumerate(cls.CONFIG_ORDER):
            config = cls.FALLBACK_CONFIGS.get(key, {})
            result.append({
                'id': i + 1,
                'config_key': key,
                'title': config.get('title', ''),
                'default_instruction': config.get('instruction', ''),
                'current_instruction': config.get('instruction', ''),
                'is_modified': False,
                'created_at': None,
                'updated_at': None
            })
        return result

    @classmethod
    def get_config_by_key(cls, config_key: str) -> Optional[Dict]:
        """
        按 key 获取单个配置

        Args:
            config_key: 配置键名

        Returns:
            配置字典，不存在返回 None
        """
        try:
            from models.database import get_db
            conn = get_db()
            cur = conn.cursor()

            cur.execute("""
                SELECT id, config_key, title, default_instruction, current_instruction,
                       created_at, updated_at
                FROM ai_analysis_config
                WHERE config_key = %s
            """, (config_key,))
            row = cur.fetchone()

            if row:
                return {
                    'id': row['id'],
                    'config_key': row['config_key'],
                    'title': row['title'],
                    'default_instruction': row['default_instruction'],
                    'current_instruction': row['current_instruction'],
                    'is_modified': row['current_instruction'] != row['default_instruction'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                }

            # 数据库中没有，尝试返回硬编码默认值
            if config_key in cls.FALLBACK_CONFIGS:
                fallback = cls.FALLBACK_CONFIGS[config_key]
                return {
                    'id': None,
                    'config_key': config_key,
                    'title': fallback['title'],
                    'default_instruction': fallback['instruction'],
                    'current_instruction': fallback['instruction'],
                    'is_modified': False,
                    'created_at': None,
                    'updated_at': None
                }

            return None
        except Exception as e:
            print(f"[AIPromptConfigService] 获取配置失败 ({config_key}): {e}")
            # 容错：返回硬编码默认值
            if config_key in cls.FALLBACK_CONFIGS:
                fallback = cls.FALLBACK_CONFIGS[config_key]
                return {
                    'id': None,
                    'config_key': config_key,
                    'title': fallback['title'],
                    'default_instruction': fallback['instruction'],
                    'current_instruction': fallback['instruction'],
                    'is_modified': False,
                    'created_at': None,
                    'updated_at': None
                }
            return None

    @classmethod
    def get_current_instruction(cls, config_key: str) -> str:
        """
        获取指定配置的当前指令文本（用于构建 AI 提示语）

        Args:
            config_key: 配置键名

        Returns:
            当前指令文本，查询失败时返回硬编码默认值
        """
        config = cls.get_config_by_key(config_key)
        if config:
            return config['current_instruction']

        # 容错：返回硬编码默认值
        if config_key in cls.FALLBACK_CONFIGS:
            return cls.FALLBACK_CONFIGS[config_key]['instruction']

        return ""

    @classmethod
    def get_all_current_instructions(cls) -> Dict[str, str]:
        """
        获取所有配置的当前指令文本（用于构建 AI 提示语）

        Returns:
            {config_key: current_instruction} 字典
        """
        configs = cls.get_all_configs()
        return {c['config_key']: c['current_instruction'] for c in configs}

    @classmethod
    def update_config(cls, config_key: str, new_instruction: str) -> Tuple[bool, str]:
        """
        更新指定配置的 current_instruction

        Args:
            config_key: 配置键名
            new_instruction: 新的指令文本

        Returns:
            (success, message) 元组
        """
        if not new_instruction or not new_instruction.strip():
            return False, "指令内容不能为空"

        try:
            from models.database import get_db
            conn = get_db()
            cur = conn.cursor()

            # 检查配置是否存在
            cur.execute("SELECT id FROM ai_analysis_config WHERE config_key = %s", (config_key,))
            if not cur.fetchone():
                return False, f"配置项 '{config_key}' 不存在"

            # 更新配置
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cur.execute("""
                UPDATE ai_analysis_config
                SET current_instruction = %s, updated_at = %s
                WHERE config_key = %s
            """, (new_instruction.strip(), now, config_key))
            conn.commit()

            return True, "配置更新成功"
        except Exception as e:
            print(f"[AIPromptConfigService] 更新配置失败 ({config_key}): {e}")
            return False, f"更新失败: {str(e)}"

    @classmethod
    def reset_config(cls, config_key: str) -> Tuple[bool, str]:
        """
        重置指定配置的 current_instruction 为 default_instruction

        Args:
            config_key: 配置键名

        Returns:
            (success, message) 元组
        """
        try:
            from models.database import get_db
            conn = get_db()
            cur = conn.cursor()

            # 检查配置是否存在
            cur.execute("""
                SELECT id, default_instruction
                FROM ai_analysis_config
                WHERE config_key = %s
            """, (config_key,))
            row = cur.fetchone()

            if not row:
                return False, f"配置项 '{config_key}' 不存在"

            # 重置为默认值
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cur.execute("""
                UPDATE ai_analysis_config
                SET current_instruction = default_instruction, updated_at = %s
                WHERE config_key = %s
            """, (now, config_key))
            conn.commit()

            return True, "配置已重置为默认值"
        except Exception as e:
            print(f"[AIPromptConfigService] 重置配置失败 ({config_key}): {e}")
            return False, f"重置失败: {str(e)}"

    @classmethod
    def reset_all_configs(cls) -> Tuple[bool, str]:
        """
        重置所有配置的 current_instruction 为 default_instruction

        Returns:
            (success, message) 元组
        """
        try:
            from models.database import get_db
            conn = get_db()
            cur = conn.cursor()

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cur.execute("""
                UPDATE ai_analysis_config
                SET current_instruction = default_instruction, updated_at = %s
            """, (now,))
            affected = cur.rowcount
            conn.commit()

            return True, f"已重置 {affected} 个配置项为默认值"
        except Exception as e:
            print(f"[AIPromptConfigService] 重置所有配置失败: {e}")
            return False, f"重置失败: {str(e)}"

    @classmethod
    def build_analysis_requirements(cls) -> str:
        """
        构建 AI 分析要求部分的提示语（5 维度）

        从数据库读取当前配置，构建格式化的分析要求文本。
        如果数据库查询失败，使用硬编码默认值。

        Returns:
            格式化的分析要求文本
        """
        instructions = cls.get_all_current_instructions()

        # 按顺序构建分析要求
        sections = []

        # 1. 关键风险画像
        risk_profile = instructions.get('risk_profile', cls.FALLBACK_CONFIGS['risk_profile']['instruction'])
        sections.append(f"""1. **关键风险画像 (Risk Profile)**
   {risk_profile}""")

        # 2. 培训关联分析
        training_gap = instructions.get('training_gap', cls.FALLBACK_CONFIGS['training_gap']['instruction'])
        sections.append(f"""2. **培训关联分析 (Training Gap)**
   {training_gap}""")

        # 3. 根因深度定性
        root_cause = instructions.get('root_cause', cls.FALLBACK_CONFIGS['root_cause']['instruction'])
        sections.append(f"""3. **根因深度定性 (Root Cause Classification)**
   {root_cause}""")

        # 4. 预测性预警
        prediction = instructions.get('prediction', cls.FALLBACK_CONFIGS['prediction']['instruction'])
        sections.append(f"""4. **预测性预警 (Prediction)**
   {prediction}""")

        # 5. 精准帮扶方案
        measures = instructions.get('measures', cls.FALLBACK_CONFIGS['measures']['instruction'])
        sections.append(f"""5. **精准帮扶方案 (Actionable Plan)**
   {measures}""")

        return "\n\n".join(sections)
