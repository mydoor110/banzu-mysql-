#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bootstrap Service - 系统初始化引导逻辑

将重型初始化逻辑从 app.py 入口层迁出，
由 CLI 或显式 bootstrap 流程调用。

整改说明：
  - 从 app.py 迁出 _init_algorithm_config() (~400行)
  - 入口文件只保留轻量调用
"""
import os
import json
from datetime import datetime
from models.database import get_db, close_db


def init_algorithm_config():
    """初始化算法配置预设

    从 config/algorithm_presets.json 读取预设配置，
    如果文件不存在则使用内置默认值。
    仅在 algorithm_presets 表为空时执行。
    
    注意：此函数在请求上下文外运行（CLI/启动时），
    必须显式 close_db() 回收连接。
    """
    conn = get_db()
    cur = conn.cursor()

    # 检查算法预设表是否存在且为空
    try:
        cur.execute("SELECT COUNT(1) as cnt FROM algorithm_presets")
        result = cur.fetchone()
        count = result['cnt'] if result else 0
        if count > 0:
            return  # 已初始化
    except Exception:
        return  # 表不存在，跳过

    try:
        # 尝试从配置文件加载预设
        preset_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "algorithm_presets.json")
        preset_payload = None
        try:
            with open(preset_path, "r", encoding="utf-8") as handle:
                preset_payload = json.load(handle)
        except FileNotFoundError:
            preset_payload = None
        except Exception as e:
            print(f"读取初始化预设失败: {e}")
            preset_payload = None

        # 构建默认配置（标准、严格、宽松三档）
        standard_config = _build_standard_config()
        strict_config = _build_strict_config(standard_config)
        lenient_config = _build_lenient_config(standard_config)

        strict_name = "严格"
        strict_desc = "更严格的惩罚力度，适用于高要求场景"
        standard_name = "标准"
        standard_desc = "标准惩罚力度，平衡公平与激励"
        lenient_name = "宽松"
        lenient_desc = "较宽松的惩罚力度，适用于培养阶段"
        default_preset_key = "standard"

        # 如果有外部预设文件，用它覆盖默认值
        if preset_payload:
            preset_map = {}
            for preset in preset_payload.get("presets", []):
                key = preset.get("preset_key")
                if key:
                    preset_map[key] = preset

            if preset_map.get("strict"):
                strict_config = preset_map["strict"].get("config_data") or strict_config
                strict_name = preset_map["strict"].get("preset_name") or strict_name
                strict_desc = preset_map["strict"].get("description") or strict_desc

            if preset_map.get("standard"):
                standard_config = preset_map["standard"].get("config_data") or standard_config
                standard_name = preset_map["standard"].get("preset_name") or standard_name
                standard_desc = preset_map["standard"].get("description") or standard_desc

            if preset_map.get("lenient"):
                lenient_config = preset_map["lenient"].get("config_data") or lenient_config
                lenient_name = preset_map["lenient"].get("preset_name") or lenient_name
                lenient_desc = preset_map["lenient"].get("description") or lenient_desc

            default_preset_key = preset_payload.get("default_preset") or default_preset_key

        # 插入预设方案
        presets = [
            (strict_name, 'strict', strict_desc, json.dumps(strict_config, ensure_ascii=False)),
            (standard_name, 'standard', standard_desc, json.dumps(standard_config, ensure_ascii=False)),
            (lenient_name, 'lenient', lenient_desc, json.dumps(lenient_config, ensure_ascii=False))
        ]
        for preset_name, preset_key, description, config_data in presets:
            cur.execute(
                "INSERT INTO algorithm_presets (preset_name, preset_key, description, config_data) VALUES (%s, %s, %s, %s)",
                (preset_name, preset_key, description, config_data)
            )

        # 初始化当前配置
        default_config = standard_config
        default_preset_name = standard_name
        if default_preset_key == 'strict':
            default_config = strict_config
            default_preset_name = strict_name
        elif default_preset_key == 'lenient':
            default_config = lenient_config
            default_preset_name = lenient_name
        cur.execute(
            "INSERT INTO algorithm_active_config (id, based_on_preset, is_customized, config_data, config_version, updated_at) VALUES (1, %s, 0, %s, 1, %s)",
            (default_preset_key, json.dumps(default_config, ensure_ascii=False), datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )

        # 记录初始化日志（含版本号）
        cur.execute(
            "INSERT INTO algorithm_config_logs (action, preset_name, new_config, change_reason, changed_by, changed_by_name, config_version) VALUES ('INIT', %s, %s, '系统初始化', 1, 'system', 1)",
            (default_preset_name, json.dumps(default_config, ensure_ascii=False))
        )

        conn.commit()
        print(f"✅ 算法配置初始化完成: 已创建3个预设方案(严格/标准/宽松)，当前配置为'{default_preset_name}'档")
    finally:
        close_db()


def _build_standard_config():
    """构建标准档算法配置"""
    return {
        "performance": {
            "grade_coefficients": {"D": 0.0, "C": 0.6, "B": 0.9, "B+": 1.0, "A": 1.1},
            "grade_ranges": {
                "D": {"min": 0, "max": 79.9, "radar_override": 50},
                "C": {"min": 80, "max": 89.9},
                "B": {"min": 90, "max": 94.9},
                "B+": {"min": 95, "max": 99.9},
                "A": {"min": 100, "max": 110}
            },
            "contamination_rules": {
                "d_count_threshold": 1,
                "c_count_threshold": 2,
                "d_cap_score": 90,
                "c_cap_score": 94.9
            }
        },
        "safety": {
            "behavior_track": {
                "freq_thresholds": [2, 5, 6],
                "freq_multipliers": [1.2, 3.0, 6.0]
            },
            "severity_track": {
                "score_ranges": [
                    {"max": 3, "multiplier": 1.3},
                    {"min": 3, "max": 5, "multiplier": 3.25},
                    {"min": 5, "multiplier": 6.5}
                ],
                "critical_threshold": 12
            },
            "dual_track_weights": {
                "behavior": 0.4,
                "severity": 0.6
            },
            "thresholds": {
                "red_score": 60,
                "red_freq": 6,
                "orange_score": 80,
                "orange_freq": 3,
                "fail_score": 60,
                "warning_score": 90
            }
        },
        "training": {
            "penalty_rules": {
                "absolute_disqualification": 50,
                "small_sample_penalty": 0.85,
                "afr_threshold": 0.2,
                "absolute_threshold": {"fail_count": 3, "coefficient": 0.50},
                "small_sample": {"sample_size": 10, "coefficient": 0.85},
                "afr_thresholds": [
                    {"min": 2.5, "coefficient": 0.5, "label": "高频失格"},
                    {"min": 1.5, "max": 2.5, "coefficient": 0.7, "label": "频率偏高"},
                    {"min": 0.5, "max": 1.5, "coefficient": 0.9, "label": "偶发失格"}
                ],
                "afr_thresholds_new_employee": [
                    {"threshold": 15, "coefficient": 0.70, "label": "高频失格"},
                    {"threshold": 8, "coefficient": 0.80, "label": "频率偏高"},
                    {"threshold": 4, "coefficient": 0.90, "label": "偶发失格"}
                ],
                "afr_thresholds_experienced": [
                    {"threshold": 10, "coefficient": 0.60, "label": "高频失格"},
                    {"threshold": 5, "coefficient": 0.75, "label": "频率偏高"},
                    {"threshold": 2, "coefficient": 0.90, "label": "偶发失格"}
                ]
            },
            "duration_thresholds": {
                "short_term_days": 60,
                "mid_term_days": 180,
                "long_term_years": 1,
                "default_scores": {"short": 65, "mid": 50, "long": 0}
            }
        },
        "comprehensive": {
            "score_weights": {
                "performance": 0.35,
                "safety": 0.30,
                "training": 0.20,
                "stability": 0.10,
                "learning": 0.05
            }
        },
        "key_personnel": {
            "comprehensive_threshold": 70,
            "monthly_violation_threshold": 3
        },
        "learning": {
            "potential_threshold": 0.5,
            "decline_threshold": -0.2,
            "decline_penalty": 0.8,
            "slope_amplifier": 10
        },
        "stability_new": {
            "window_months": 12,
            "min_effective_months": 6,
            "volatility_metric": "mean_abs_delta",
            "score_map_low": 1.09,
            "score_map_high": 6.00,
            "score_map_low_score": 90.0,
            "score_map_high_score": 60.0,
            "high_vol_threshold": 0.0667,
            "k_multiplier": 1.2,
            "label_cutoffs": {"stable": 75, "medium": 60},
            "low_level_threshold": 60
        },
        "learning_new": {
            "trend_ceiling_floor": 5,
            "trend_warning_ratio": 1.5,
            "trend_warning_floor": 4,
            "trend_critical_ratio": 3.0,
            "trend_critical_floor": 6,
            "historical_baseline": 3,
            "factor_reward": 1.2,
            "factor_stable": 1.0,
            "factor_safe_fluctuation": 0.9,
            "factor_mitigation": 0.8,
            "factor_warning": 0.6,
            "factor_improvement": 1.2,
            "factor_high_improvement": 0.8,
            "factor_solidification": 0.4,
            "factor_deterioration": 0.3,
            "factor_deterioration_mild": 0.3,
            "inertia_start_months": 2,
            "inertia_step": 0.05,
            "inertia_max_penalty": 0.40,
            "time_decay_rate": 0.2
        },
        "nine_grid": {
            "y_axis_weights": {
                "stability": 0.4,
                "learning": 0.6
            }
        }
    }


def _build_strict_config(standard_config):
    """构建严格档算法配置（基于标准档修改）"""
    strict_config = json.loads(json.dumps(standard_config))
    strict_config["performance"]["contamination_rules"] = {
        "d_count_threshold": 1, "c_count_threshold": 2,
        "d_cap_score": 85, "c_cap_score": 92
    }
    strict_config["safety"]["behavior_track"]["freq_multipliers"] = [1.2, 3.0, 6.0]
    strict_config["safety"]["severity_track"]["score_ranges"] = [
        {"max": 3, "multiplier": 1.5},
        {"min": 3, "max": 5, "multiplier": 3.75},
        {"min": 5, "multiplier": 7.5}
    ]
    strict_config["safety"]["severity_track"]["critical_threshold"] = 12
    strict_config["training"]["penalty_rules"]["absolute_threshold"]["coefficient"] = 0.45
    strict_config["training"]["penalty_rules"]["small_sample"]["coefficient"] = 0.80
    strict_config["training"]["penalty_rules"]["afr_thresholds_new_employee"] = [
        {"threshold": 15, "coefficient": 0.65, "label": "高频失格"},
        {"threshold": 8, "coefficient": 0.75, "label": "频率偏高"},
        {"threshold": 4, "coefficient": 0.85, "label": "偶发失格"}
    ]
    strict_config["training"]["penalty_rules"]["afr_thresholds_experienced"] = [
        {"threshold": 10, "coefficient": 0.55, "label": "高频失格"},
        {"threshold": 5, "coefficient": 0.70, "label": "频率偏高"},
        {"threshold": 2, "coefficient": 0.85, "label": "偶发失格"}
    ]
    strict_config["key_personnel"] = {
        "comprehensive_threshold": 75,
        "monthly_violation_threshold": 2
    }
    strict_config["learning"] = {
        "potential_threshold": 0.6,
        "decline_threshold": -0.2,
        "decline_penalty": 0.7,
        "slope_amplifier": 10
    }
    strict_config["stability_new"] = {
        "window_months": 6,
        "min_effective_months": 6,
        "volatility_metric": "mean_abs_delta",
        "score_map_low": 0.65,
        "score_map_high": 5.41,
        "score_map_low_score": 90.0,
        "score_map_high_score": 60.0,
        "high_vol_threshold": 0.0576,
        "k_multiplier": 1.1,
        "label_cutoffs": {"stable": 85, "medium": 55},
        "low_level_threshold": 60
    }
    strict_config["learning_new"] = {
        "trend_ceiling_floor": 5,
        "trend_warning_ratio": 1.5,
        "trend_warning_floor": 4,
        "trend_critical_ratio": 3.0,
        "trend_critical_floor": 6,
        "historical_baseline": 3,
        "factor_reward": 1.2,
        "factor_stable": 1.0,
        "factor_safe_fluctuation": 0.9,
        "factor_mitigation": 0.8,
        "factor_warning": 0.6,
        "factor_improvement": 1.2,
        "factor_high_improvement": 0.8,
        "factor_solidification": 0.4,
        "factor_deterioration": 0.3,
        "factor_deterioration_mild": 0.3,
        "inertia_start_months": 2,
        "inertia_step": 0.10,
        "inertia_max_penalty": 0.40,
        "time_decay_rate": 0.2
    }
    strict_config["nine_grid"] = {
        "y_axis_weights": {
            "stability": 0.4,
            "learning": 0.6
        }
    }
    return strict_config


def _build_lenient_config(standard_config):
    """构建宽松档算法配置（基于标准档修改）"""
    lenient_config = json.loads(json.dumps(standard_config))
    lenient_config["performance"]["contamination_rules"] = {
        "d_count_threshold": 1, "c_count_threshold": 3,
        "d_cap_score": 95, "c_cap_score": 97
    }
    lenient_config["safety"]["behavior_track"]["freq_multipliers"] = [1.2, 3.0, 6.0]
    lenient_config["safety"]["severity_track"]["score_ranges"] = [
        {"max": 3, "multiplier": 0.8},
        {"min": 3, "max": 5, "multiplier": 2.0},
        {"min": 5, "multiplier": 4.0}
    ]
    lenient_config["safety"]["severity_track"]["critical_threshold"] = 12
    lenient_config["training"]["penalty_rules"]["absolute_threshold"]["coefficient"] = 0.60
    lenient_config["training"]["penalty_rules"]["small_sample"]["coefficient"] = 0.90
    lenient_config["training"]["penalty_rules"]["afr_thresholds_new_employee"] = [
        {"threshold": 15, "coefficient": 0.75, "label": "高频失格"},
        {"threshold": 8, "coefficient": 0.85, "label": "频率偏高"},
        {"threshold": 4, "coefficient": 0.95, "label": "偶发失格"}
    ]
    lenient_config["training"]["penalty_rules"]["afr_thresholds_experienced"] = [
        {"threshold": 10, "coefficient": 0.70, "label": "高频失格"},
        {"threshold": 5, "coefficient": 0.80, "label": "频率偏高"},
        {"threshold": 2, "coefficient": 0.95, "label": "偶发失格"}
    ]
    lenient_config["key_personnel"] = {
        "comprehensive_threshold": 65,
        "monthly_violation_threshold": 4
    }
    lenient_config["learning"] = {
        "potential_threshold": 0.4,
        "decline_threshold": -0.2,
        "decline_penalty": 0.9,
        "slope_amplifier": 10
    }
    lenient_config["stability_new"] = {
        "window_months": 12,
        "min_effective_months": 6,
        "volatility_metric": "mean_abs_delta",
        "score_map_low": 1.46,
        "score_map_high": 7.32,
        "score_map_low_score": 90.0,
        "score_map_high_score": 60.0,
        "high_vol_threshold": 0.0855,
        "k_multiplier": 1.3,
        "label_cutoffs": {"stable": 70, "medium": 55},
        "low_level_threshold": 60
    }
    lenient_config["learning_new"] = {
        "trend_ceiling_floor": 5,
        "trend_warning_ratio": 1.5,
        "trend_warning_floor": 4,
        "trend_critical_ratio": 3.0,
        "trend_critical_floor": 6,
        "historical_baseline": 3,
        "factor_reward": 1.2,
        "factor_stable": 1.0,
        "factor_safe_fluctuation": 0.9,
        "factor_mitigation": 0.8,
        "factor_warning": 0.6,
        "factor_improvement": 1.2,
        "factor_high_improvement": 0.8,
        "factor_solidification": 0.4,
        "factor_deterioration": 0.3,
        "factor_deterioration_mild": 0.3,
        "inertia_start_months": 4,
        "inertia_step": 0.05,
        "inertia_max_penalty": 0.40,
        "time_decay_rate": 0.2
    }
    lenient_config["nine_grid"] = {
        "y_axis_weights": {
            "stability": 0.4,
            "learning": 0.6
        }
    }
    return lenient_config
