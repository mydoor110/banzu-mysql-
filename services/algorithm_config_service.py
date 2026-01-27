#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
算法配置服务
提供算法配置的读取、更新、校验等功能
"""
import json
import math
import time
from typing import Dict, Tuple, Optional, List
from datetime import datetime
from models.database import get_db


class AlgorithmConfigService:
    """算法配置服务 - 立即生效模式"""

    # 配置缓存
    _cache: Optional[dict] = None
    _cache_time: float = 0
    _cache_ttl: int = 300  # 5分钟缓存
    _cache_updated_at: Optional[str] = None

    @classmethod
    def get_active_config(cls) -> dict:
        """
        获取当前生效配置（带缓存）

        Returns:
            dict: 当前生效的算法配置

        Raises:
            ValueError: 配置不存在或无效
        """
        # 检查缓存
        current_time = time.time()
        if cls._cache is not None and (current_time - cls._cache_time) < cls._cache_ttl:
            try:
                conn = get_db()
                cur = conn.cursor()
                cur.execute("""
                    SELECT updated_at FROM algorithm_active_config WHERE id = 1
                """)
                row = cur.fetchone()
                if row and row['updated_at'] == cls._cache_updated_at:
                    return cls._cache
            except Exception:
                pass

        # 从数据库读取
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT config_data, updated_at FROM algorithm_active_config WHERE id = 1
        """)
        row = cur.fetchone()

        if not row:
            raise ValueError("系统配置未初始化，请联系管理员")

        config_data = json.loads(row['config_data'])

        # 更新缓存
        cls._cache = config_data
        cls._cache_time = current_time
        cls._cache_updated_at = row.get('updated_at') if row else None

        return config_data

    @staticmethod
    def _flatten_config(data: object, prefix: str = "") -> Dict[str, object]:
        """将配置展开为路径映射，便于diff"""
        result = {}
        if isinstance(data, dict):
            for key, value in data.items():
                path = f"{prefix}.{key}" if prefix else str(key)
                result.update(AlgorithmConfigService._flatten_config(value, path))
        elif isinstance(data, list):
            for index, value in enumerate(data):
                path = f"{prefix}[{index}]" if prefix else f"[{index}]"
                result.update(AlgorithmConfigService._flatten_config(value, path))
        else:
            result[prefix] = data
        return result

    @classmethod
    def _diff_configs(cls, old_config: Optional[dict], new_config: Optional[dict]) -> List[dict]:
        """生成配置diff列表"""
        old_flat = cls._flatten_config(old_config or {})
        new_flat = cls._flatten_config(new_config or {})

        keys = set(old_flat.keys()) | set(new_flat.keys())
        diffs = []
        for key in sorted(keys):
            old_val = old_flat.get(key)
            new_val = new_flat.get(key)
            if old_val != new_val:
                diffs.append({
                    "path": key,
                    "old": old_val,
                    "new": new_val
                })
        return diffs

    @classmethod
    def apply_preset(cls, preset_key: str, user_id: int, reason: str, username: Optional[str] = None, ip_address: Optional[str] = None) -> Tuple[bool, str]:
        """
        应用预设方案

        Args:
            preset_key: 预设方案标识（strict/standard/lenient）
            user_id: 操作者用户ID
            reason: 变更原因
            username: 操作者姓名（可选）
            ip_address: 操作者IP地址（可选）

        Returns:
            Tuple[bool, str]: (成功标志, 消息)
        """
        conn = get_db()
        cur = conn.cursor()

        try:
            # 1. 查询预设方案
            cur.execute("""
                SELECT preset_name, config_data FROM algorithm_presets
                WHERE preset_key = %s
            """, (preset_key,))
            preset_row = cur.fetchone()

            if not preset_row:
                return False, f"预设方案不存在: {preset_key}"

            preset_name = preset_row['preset_name']
            new_config_data = preset_row['config_data']

            # 2. 获取当前配置（用于日志）
            cur.execute("""
                SELECT config_data FROM algorithm_active_config WHERE id = 1
            """)
            current_row = cur.fetchone()
            old_config_data = current_row['config_data'] if current_row else None

            # 3. 更新当前配置
            cur.execute("""
                REPLACE INTO algorithm_active_config
                (id, based_on_preset, is_customized, config_data, updated_by, updated_at)
                VALUES (1, %s, 0, %s, %s, %s)
            """, (preset_key, new_config_data, user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            # 4. 记录变更日志
            if not username:
                cur.execute("SELECT username FROM users WHERE id = %s", (user_id,))
                user_row = cur.fetchone()
                username = user_row['username'] if user_row else f"用户{user_id}"

            cur.execute("""
                INSERT INTO algorithm_config_logs
                (action, preset_name, old_config, new_config, change_reason, changed_by, changed_by_name, ip_address)
                VALUES ('APPLY_PRESET', %s, %s, %s, %s, %s, %s, %s)
            """, (preset_name, old_config_data, new_config_data, reason, user_id, username, ip_address))

            conn.commit()

            # 5. 清除缓存
            cls.clear_cache()

            return True, f"成功应用预设方案: {preset_name}"

        except Exception as e:
            conn.rollback()
            return False, f"应用预设方案失败: {str(e)}"

    @classmethod
    def update_custom_config(cls, config_data: dict, user_id: int, reason: str, username: Optional[str] = None, ip_address: Optional[str] = None) -> Tuple[bool, str]:
        """
        更新自定义配置

        Args:
            config_data: 新的配置数据
            user_id: 操作者用户ID
            reason: 变更原因
            username: 操作者姓名（可选）
            ip_address: 操作者IP地址（可选）

        Returns:
            Tuple[bool, str]: (成功标志, 消息)
        """
        # 1. 校验配置
        is_valid, error_msg = cls.validate_config(config_data)
        if not is_valid:
            return False, f"配置校验失败: {error_msg}"

        conn = get_db()
        cur = conn.cursor()

        try:
            # 2. 获取当前配置（用于日志）
            cur.execute("""
                SELECT config_data FROM algorithm_active_config WHERE id = 1
            """)
            current_row = cur.fetchone()
            old_config_data = current_row['config_data'] if current_row else None

            # 3. 更新当前配置
            new_config_json = json.dumps(config_data, ensure_ascii=False)
            cur.execute("""
                REPLACE INTO algorithm_active_config
                (id, based_on_preset, is_customized, config_data, updated_by, updated_at)
                VALUES (1, NULL, 1, %s, %s, %s)
            """, (new_config_json, user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            # 4. 记录变更日志
            if not username:
                cur.execute("SELECT username FROM users WHERE id = %s", (user_id,))
                user_row = cur.fetchone()
                username = user_row['username'] if user_row else f"用户{user_id}"

            cur.execute("""
                INSERT INTO algorithm_config_logs
                (action, old_config, new_config, change_reason, changed_by, changed_by_name, ip_address)
                VALUES ('CUSTOM_UPDATE', %s, %s, %s, %s, %s, %s)
            """, (old_config_data, new_config_json, reason, user_id, username, ip_address))

            conn.commit()

            # 5. 清除缓存
            cls.clear_cache()

            return True, "成功更新自定义配置"

        except Exception as e:
            conn.rollback()
            return False, f"更新配置失败: {str(e)}"

    @classmethod
    def update_preset(cls, preset_key: str, config_data: dict, user_id: int, reason: str,
                      username: Optional[str] = None, ip_address: Optional[str] = None) -> Tuple[bool, str]:
        """更新预设方案配置"""
        is_valid, error_msg = cls.validate_config(config_data)
        if not is_valid:
            return False, f"配置校验失败: {error_msg}"

        conn = get_db()
        cur = conn.cursor()

        try:
            cur.execute("""
                SELECT preset_name, config_data FROM algorithm_presets
                WHERE preset_key = %s
            """, (preset_key,))
            preset_row = cur.fetchone()

            if not preset_row:
                return False, f"预设方案不存在: {preset_key}"

            preset_name = preset_row['preset_name']
            old_config_data = preset_row['config_data']
            new_config_json = json.dumps(config_data, ensure_ascii=False)

            cur.execute("""
                UPDATE algorithm_presets
                SET config_data = %s
                WHERE preset_key = %s
            """, (new_config_json, preset_key))

            if not username:
                cur.execute("SELECT username FROM users WHERE id = %s", (user_id,))
                user_row = cur.fetchone()
                username = user_row['username'] if user_row else f"用户{user_id}"

            cur.execute("""
                INSERT INTO algorithm_config_logs
                (action, preset_name, old_config, new_config, change_reason, changed_by, changed_by_name, ip_address)
                VALUES ('UPDATE_PRESET', %s, %s, %s, %s, %s, %s, %s)
            """, (preset_name, old_config_data, new_config_json, reason, user_id, username, ip_address))

            conn.commit()
            cls.clear_cache()

            return True, f"成功更新预设方案: {preset_name}"

        except Exception as e:
            conn.rollback()
            return False, f"更新预设方案失败: {str(e)}"

    @classmethod
    def rollback_preset_update(cls, log_id: int, user_id: int, reason: str,
                               username: Optional[str] = None, ip_address: Optional[str] = None) -> Tuple[bool, str]:
        """回滚预设方案配置"""
        conn = get_db()
        cur = conn.cursor()

        try:
            cur.execute("""
                SELECT action, preset_name, old_config, new_config
                FROM algorithm_config_logs
                WHERE id = %s
            """, (log_id,))
            log_row = cur.fetchone()

            if not log_row:
                return False, "日志不存在"

            if log_row['action'] != 'UPDATE_PRESET':
                return False, "仅支持回滚预设更新日志"

            preset_name = log_row['preset_name']
            old_config_data = log_row['old_config']
            current_config_data = log_row['new_config']

            cur.execute("""
                SELECT preset_key, config_data FROM algorithm_presets
                WHERE preset_name = %s
            """, (preset_name,))
            preset_row = cur.fetchone()

            if not preset_row:
                return False, f"预设方案不存在: {preset_name}"

            preset_key = preset_row['preset_key']
            preset_current = preset_row['config_data']

            # 回滚预设配置
            cur.execute("""
                UPDATE algorithm_presets
                SET config_data = %s
                WHERE preset_key = %s
            """, (old_config_data, preset_key))

            # 如当前配置正在使用该预设，则同步应用
            cur.execute("""
                SELECT based_on_preset, is_customized FROM algorithm_active_config WHERE id = 1
            """)
            active_row = cur.fetchone()
            if active_row and active_row['based_on_preset'] == preset_key and int(active_row['is_customized'] or 0) == 0:
                cur.execute("""
                    REPLACE INTO algorithm_active_config
                    (id, based_on_preset, is_customized, config_data, updated_by, updated_at)
                    VALUES (1, %s, 0, %s, %s, %s)
                """, (preset_key, old_config_data, user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            if not username:
                cur.execute("SELECT username FROM users WHERE id = %s", (user_id,))
                user_row = cur.fetchone()
                username = user_row['username'] if user_row else f"用户{user_id}"

            cur.execute("""
                INSERT INTO algorithm_config_logs
                (action, preset_name, old_config, new_config, change_reason, changed_by, changed_by_name, ip_address)
                VALUES ('ROLLBACK_PRESET', %s, %s, %s, %s, %s, %s, %s)
            """, (preset_name, preset_current, old_config_data, reason, user_id, username, ip_address))

            conn.commit()
            cls.clear_cache()

            return True, f"已回滚预设方案: {preset_name}"

        except Exception as e:
            conn.rollback()
            return False, f"回滚失败: {str(e)}"

    @classmethod
    def simulate_calculation(cls, config_data: dict, sample_data: dict) -> dict:
        """
        模拟计算（不保存配置）

        Args:
            config_data: 要模拟的配置数据
            sample_data: 样例数据，格式：
                {
                    "performance": {"grades": ["D", "C", "B+"]},
                    "safety": {"violations": [3, 5, 12]},
                    "training": {"scores": [85, 0, 90], "is_qualified": [1, 0, 1]}
                }

        Returns:
            dict: 模拟计算结果
        """
        # 导入算法函数（避免循环导入）
        from blueprints.personnel import (
            calculate_performance_score_monthly,
            calculate_safety_score_dual_track,
            calculate_training_score_with_penalty
        )

        results = {
            "performance": [],
            "safety": [],
            "training": [],
            "comprehensive": [],
            "errors": []
        }

        try:
            # 模拟绩效计算
            if "performance" in sample_data and "grades" in sample_data["performance"]:
                for grade in sample_data["performance"]["grades"]:
                    try:
                        result = calculate_performance_score_monthly(grade, 95.0, config=config_data)
                        results["performance"].append({
                            "grade": grade,
                            "score": result["score"],
                            "label": result["label"]
                        })
                    except Exception as e:
                        results["errors"].append(f"绩效计算错误 ({grade}): {str(e)}")

            # 模拟安全计算
            if "safety" in sample_data and "violations" in sample_data["safety"]:
                for violation_score in sample_data["safety"]["violations"]:
                    try:
                        # 构造虚拟数据
                        violations_list = [violation_score]
                        result = calculate_safety_score_dual_track(violations_list, 1, config=config_data)
                        results["safety"].append({
                            "violation_score": violation_score,
                            "score": result["score"],
                            "label": result["label"]
                        })
                    except Exception as e:
                        results["errors"].append(f"安全计算错误 ({violation_score}分): {str(e)}")

            # 模拟培训计算
            if "training" in sample_data:
                scores = sample_data["training"].get("scores", [])
                is_qualified = sample_data["training"].get("is_qualified", [])

                if len(scores) == len(is_qualified):
                    for i, (score, qualified) in enumerate(zip(scores, is_qualified)):
                        try:
                            # 构造虚拟记录
                            training_records = [(score, qualified, 0 if qualified else 1)]
                            result = calculate_training_score_with_penalty(training_records, 90, config=config_data)
                            results["training"].append({
                                "index": i + 1,
                                "input_score": score,
                                "is_qualified": qualified,
                                "final_score": result["score"],
                                "label": result["label"]
                            })
                        except Exception as e:
                            results["errors"].append(f"培训计算错误 (样本{i+1}): {str(e)}")

            # 计算综合分（使用权重）
            weights = config_data.get("comprehensive", {}).get("score_weights", {})
            if results["performance"] and results["safety"] and results["training"]:
                perf_score = results["performance"][0]["score"]
                safety_score = results["safety"][0]["score"]
                training_score = results["training"][0]["score"]

                comprehensive_score = (
                    perf_score * weights.get("performance", 0.35) +
                    safety_score * weights.get("safety", 0.30) +
                    training_score * weights.get("training", 0.20)
                )
                results["comprehensive"].append({
                    "score": round(comprehensive_score, 1),
                    "weights": weights
                })

        except Exception as e:
            results["errors"].append(f"模拟计算异常: {str(e)}")

        return results

    @classmethod
    def validate_config(cls, config_data: dict) -> Tuple[bool, str]:
        """
        配置数据校验

        Args:
            config_data: 配置数据

        Returns:
            Tuple[bool, str]: (是否有效, 错误消息)
        """
        def is_number(value) -> bool:
            return isinstance(value, (int, float)) and not (isinstance(value, float) and math.isnan(value))

        def require_number(value, label: str) -> Tuple[bool, str]:
            if not is_number(value):
                return False, f"{label} 必须是数字"
            return True, ""

        try:
            # 1. 结构完整性校验
            required_sections = ["performance", "safety", "training", "comprehensive", "key_personnel"]
            for section in required_sections:
                if section not in config_data:
                    return False, f"缺少必填配置节: {section}"

            # 2. 绩效配置校验
            perf = config_data["performance"]
            if "grade_coefficients" not in perf:
                return False, "缺少绩效等级系数配置"

            required_grades = ["D", "C", "B", "B+", "A"]
            for grade in required_grades:
                if grade not in perf["grade_coefficients"]:
                    return False, f"缺少等级系数: {grade}"

                coeff = perf["grade_coefficients"][grade]
                ok, msg = require_number(coeff, f"等级系数 {grade}")
                if not ok:
                    return False, msg
                if coeff < 0 or coeff > 2:
                    return False, f"等级系数 {grade} 超出范围 [0, 2]: {coeff}"

            # 3. 安全配置校验
            safety = config_data["safety"]
            if "severity_track" in safety and "critical_threshold" in safety["severity_track"]:
                threshold = safety["severity_track"]["critical_threshold"]
                ok, msg = require_number(threshold, "重大违规红线")
                if not ok:
                    return False, msg
                if threshold < 1 or threshold > 50:
                    return False, f"重大违规红线超出范围 [1, 50]: {threshold}"

            # 4. 培训配置校验
            # 4. 培训配置校验
            training = config_data["training"]
            if "penalty_rules" in training:
                # 校验绝对失格
                if "absolute_threshold" in training["penalty_rules"]:
                    fail_count = training["penalty_rules"]["absolute_threshold"].get("fail_count", 3)
                    if not isinstance(fail_count, int):
                        return False, "绝对失格次数必须为整数"
                    if fail_count < 1 or fail_count > 10:
                        return False, f"绝对失格次数超出范围 [1, 10]: {fail_count}"
                
                # 校验AFR阈值（如果存在）
                if "afr_thresholds" in training["penalty_rules"]:
                    for idx, rule in enumerate(training["penalty_rules"]["afr_thresholds"]):
                        if "threshold" in rule:
                            thresh = rule["threshold"]
                            ok, msg = require_number(thresh, f"AFR阈值[{idx}]")
                            if not ok:
                                return False, msg
                            if thresh < 0 or thresh > 50:
                                return False, f"AFR阈值[{idx}]超出范围 [0, 50]: {thresh}"

            # 5. 综合评分权重校验
            comprehensive = config_data["comprehensive"]
            if "score_weights" not in comprehensive:
                return False, "缺少综合评分权重配置"

            weights = comprehensive["score_weights"]
            for key, value in weights.items():
                ok, msg = require_number(value, f"综合评分权重 {key}")
                if not ok:
                    return False, msg

            total_weight = sum(weights.values())
            if abs(total_weight - 1.0) > 0.01:  # 容忍0.01的浮点误差
                return False, f"综合评分权重总和必须为1.0，当前为: {total_weight}"

            # 6. 关键人员判定标准校验
            key_personnel = config_data["key_personnel"]
            if "comprehensive_threshold" not in key_personnel:
                return False, "缺少关键人员综合分阈值"

            threshold = key_personnel["comprehensive_threshold"]
            ok, msg = require_number(threshold, "关键人员综合分阈值")
            if not ok:
                return False, msg
            if threshold < 0 or threshold > 100:
                return False, f"关键人员综合分阈值超出范围 [0, 100]: {threshold}"

            # 7. 安全趋势配置校验
            if "learning_new" in config_data:
                ln = config_data["learning_new"]
                if "deterioration_mode" in ln:
                    if ln["deterioration_mode"] not in ["progressive", "immediate"]:
                        return False, f"无效的恶化处理模式: {ln['deterioration_mode']}"
                if "factor_deterioration_mild" in ln:
                    f = ln["factor_deterioration_mild"]
                    ok, msg = require_number(f, "轻度恶化系数")
                    if not ok:
                        return False, msg
                    if f < 0 or f > 1:
                        return False, f"轻度恶化系数超出范围 [0, 1]: {f}"
                        
            return True, "校验通过"

        except Exception as e:
            return False, f"校验异常: {str(e)}"

    @classmethod
    def get_logs(cls, limit: int = 50, offset: int = 0) -> List[dict]:
        """
        获取配置变更日志

        Args:
            limit: 返回记录数
            offset: 分页偏移

        Returns:
            List[dict]: 日志列表
        """
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                id, action, preset_name, change_reason,
                changed_by, changed_by_name, changed_at, ip_address
            FROM algorithm_config_logs
            ORDER BY changed_at DESC
            LIMIT %s OFFSET %s
        """, (limit, offset))

        logs = []
        for row in cur.fetchall():
            logs.append({
                "id": row['id'],
                "action": row['action'],
                "preset_name": row['preset_name'],
                "change_reason": row['change_reason'],
                "changed_by": row['changed_by'],
                "changed_by_name": row['changed_by_name'],
                "changed_at": row['changed_at'],
                "ip_address": row['ip_address']
            })

        return logs

    @classmethod
    def get_log_detail(cls, log_id: int) -> Optional[dict]:
        """获取单条日志详情（含diff）"""
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                id, action, preset_name, change_reason, changed_by, changed_by_name,
                changed_at, ip_address, old_config, new_config
            FROM algorithm_config_logs
            WHERE id = %s
        """, (log_id,))
        row = cur.fetchone()
        if not row:
            return None

        old_config = json.loads(row['old_config']) if row['old_config'] else None
        new_config = json.loads(row['new_config']) if row['new_config'] else None

        return {
            "id": row['id'],
            "action": row['action'],
            "preset_name": row['preset_name'],
            "change_reason": row['change_reason'],
            "changed_by": row['changed_by'],
            "changed_by_name": row['changed_by_name'],
            "changed_at": row['changed_at'],
            "ip_address": row['ip_address'],
            "diffs": cls._diff_configs(old_config, new_config)
        }

    @classmethod
    def get_current_info(cls) -> dict:
        """
        获取当前配置信息

        Returns:
            dict: 当前配置信息（包含基于的预设方案、是否自定义等）
        """
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT based_on_preset, is_customized, updated_at
            FROM algorithm_active_config
            WHERE id = 1
        """)
        row = cur.fetchone()

        if row:
            return {
                "based_on_preset": row['based_on_preset'],
                "is_customized": bool(row['is_customized']),
                "updated_at": row['updated_at']
            }
        else:
            return {
                "based_on_preset": None,
                "is_customized": False,
                "updated_at": None
            }

    @classmethod
    def get_presets(cls) -> List[dict]:
        """
        获取所有预设方案

        Returns:
            List[dict]: 预设方案列表
        """
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT preset_key, preset_name, description, config_data
            FROM algorithm_presets
            ORDER BY id
        """)

        presets = []
        for row in cur.fetchall():
            presets.append({
                "preset_key": row['preset_key'],
                "preset_name": row['preset_name'],
                "description": row['description'],
                "config_data": json.loads(row['config_data']) if row['config_data'] else {}
            })

        return presets

    @classmethod
    def clear_cache(cls):
        """清除配置缓存"""
        cls._cache = None
        cls._cache_time = 0
        cls._cache_updated_at = None
