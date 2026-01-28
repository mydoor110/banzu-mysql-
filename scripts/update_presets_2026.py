#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新算法配置预设值脚本
根据2026年1月25日的调整要求更新安全、培训、学习能力配置

变更内容：
- 安全：只改惩罚倍数
- 培训：只改惩罚系数
- 学习能力：统一规则 + 分档惯性参数
"""
import json
import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 加载.env文件
from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, '.env'))

from models.database import get_db
from datetime import datetime


def backup_presets():
    """备份当前预设值"""
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT preset_key, preset_name, config_data FROM algorithm_presets")
    rows = cur.fetchall()

    backup_data = {}
    for row in rows:
        backup_data[row['preset_key']] = {
            'preset_name': row['preset_name'],
            'config_data': json.loads(row['config_data']) if row['config_data'] else {}
        }

    # 保存备份到文件
    backup_file = f"scripts/presets_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)

    print(f"✅ 预设值已备份到: {backup_file}")
    return backup_data


def update_presets():
    """更新预设值"""
    conn = get_db()
    cur = conn.cursor()

    # 获取当前预设配置
    cur.execute("SELECT preset_key, config_data FROM algorithm_presets")
    rows = cur.fetchall()

    presets = {}
    for row in rows:
        presets[row['preset_key']] = json.loads(row['config_data']) if row['config_data'] else {}

    if not presets:
        print("❌ 未找到预设配置")
        return False

    # ==================== 更新标准档 ====================
    if 'standard' in presets:
        cfg = presets['standard']

        # 安全配置：只改惩罚倍数
        cfg['safety']['behavior_track']['freq_multipliers'] = [1.2, 3.0, 6.0]
        cfg['safety']['severity_track']['score_ranges'] = [
            {"max": 3, "multiplier": 1.3},
            {"min": 3, "max": 5, "multiplier": 3.25},
            {"min": 5, "multiplier": 6.5}
        ]

        # 培训配置：只改惩罚系数
        cfg['training']['penalty_rules']['absolute_threshold']['coefficient'] = 0.50
        cfg['training']['penalty_rules']['small_sample']['coefficient'] = 0.85
        cfg['training']['penalty_rules']['afr_thresholds_new_employee'] = [
            {"threshold": 15, "coefficient": 0.70, "label": "高频失格"},
            {"threshold": 8, "coefficient": 0.80, "label": "频率偏高"},
            {"threshold": 4, "coefficient": 0.90, "label": "偶发失格"}
        ]
        cfg['training']['penalty_rules']['afr_thresholds_experienced'] = [
            {"threshold": 10, "coefficient": 0.60, "label": "高频失格"},
            {"threshold": 5, "coefficient": 0.75, "label": "频率偏高"},
            {"threshold": 2, "coefficient": 0.90, "label": "偶发失格"}
        ]

        # 学习能力配置：统一规则 + 标准档惯性参数
        cfg['learning_new'] = {
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
        }

        print("✅ 标准档配置已更新")

    # ==================== 更新严格档 ====================
    if 'strict' in presets:
        cfg = presets['strict']

        # 安全配置：只改惩罚倍数
        cfg['safety']['behavior_track']['freq_multipliers'] = [1.2, 3.0, 6.0]
        cfg['safety']['severity_track']['score_ranges'] = [
            {"max": 3, "multiplier": 1.5},
            {"min": 3, "max": 5, "multiplier": 3.75},
            {"min": 5, "multiplier": 7.5}
        ]
        cfg['safety']['severity_track']['critical_threshold'] = 12

        # 培训配置：只改惩罚系数
        cfg['training']['penalty_rules']['absolute_threshold']['coefficient'] = 0.45
        cfg['training']['penalty_rules']['small_sample']['coefficient'] = 0.80
        cfg['training']['penalty_rules']['afr_thresholds_new_employee'] = [
            {"threshold": 15, "coefficient": 0.65, "label": "高频失格"},
            {"threshold": 8, "coefficient": 0.75, "label": "频率偏高"},
            {"threshold": 4, "coefficient": 0.85, "label": "偶发失格"}
        ]
        cfg['training']['penalty_rules']['afr_thresholds_experienced'] = [
            {"threshold": 10, "coefficient": 0.55, "label": "高频失格"},
            {"threshold": 5, "coefficient": 0.70, "label": "频率偏高"},
            {"threshold": 2, "coefficient": 0.85, "label": "偶发失格"}
        ]

        # 学习能力配置：统一规则 + 严格档惯性参数
        cfg['learning_new'] = {
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

        print("✅ 严格档配置已更新")

    # ==================== 更新宽松档 ====================
    if 'lenient' in presets:
        cfg = presets['lenient']

        # 安全配置：只改惩罚倍数
        cfg['safety']['behavior_track']['freq_multipliers'] = [1.2, 3.0, 6.0]
        cfg['safety']['severity_track']['score_ranges'] = [
            {"max": 3, "multiplier": 0.8},
            {"min": 3, "max": 5, "multiplier": 2.0},
            {"min": 5, "multiplier": 4.0}
        ]
        cfg['safety']['severity_track']['critical_threshold'] = 12

        # 培训配置：只改惩罚系数
        cfg['training']['penalty_rules']['absolute_threshold']['coefficient'] = 0.60
        cfg['training']['penalty_rules']['small_sample']['coefficient'] = 0.90
        cfg['training']['penalty_rules']['afr_thresholds_new_employee'] = [
            {"threshold": 15, "coefficient": 0.75, "label": "高频失格"},
            {"threshold": 8, "coefficient": 0.85, "label": "频率偏高"},
            {"threshold": 4, "coefficient": 0.95, "label": "偶发失格"}
        ]
        cfg['training']['penalty_rules']['afr_thresholds_experienced'] = [
            {"threshold": 10, "coefficient": 0.70, "label": "高频失格"},
            {"threshold": 5, "coefficient": 0.80, "label": "频率偏高"},
            {"threshold": 2, "coefficient": 0.95, "label": "偶发失格"}
        ]

        # 学习能力配置：统一规则 + 宽松档惯性参数
        cfg['learning_new'] = {
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

        print("✅ 宽松档配置已更新")

    # ==================== 写入数据库 ====================
    try:
        for preset_key, config_data in presets.items():
            cur.execute(
                "UPDATE algorithm_presets SET config_data = %s WHERE preset_key = %s",
                (json.dumps(config_data, ensure_ascii=False), preset_key)
            )

        conn.commit()
        print("\n✅ 所有预设值已更新到数据库")
        return True

    except Exception as e:
        conn.rollback()
        print(f"\n❌ 更新失败: {str(e)}")
        return False


def update_active_config_if_needed():
    """如果当前生效配置基于预设，也更新它"""
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT based_on_preset, is_customized FROM algorithm_active_config WHERE id = 1")
    row = cur.fetchone()

    if row and row['based_on_preset'] and not row['is_customized']:
        preset_key = row['based_on_preset']

        # 获取更新后的预设配置
        cur.execute("SELECT config_data FROM algorithm_presets WHERE preset_key = %s", (preset_key,))
        preset_row = cur.fetchone()

        if preset_row:
            cur.execute(
                "UPDATE algorithm_active_config SET config_data = %s, updated_at = %s WHERE id = 1",
                (preset_row['config_data'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            )
            conn.commit()
            print(f"✅ 当前生效配置(基于{preset_key}档)已同步更新")
    else:
        print("ℹ️  当前生效配置是自定义配置，未自动更新")


def main():
    print("=" * 60)
    print("算法配置预设值更新脚本")
    print("=" * 60)
    print("\n本次更新内容：")
    print("- 安全：只改惩罚倍数 (freq_multipliers, severity multipliers)")
    print("- 培训：只改惩罚系数 (absolute_threshold, small_sample, afr系数)")
    print("- 学习能力：统一规则 + 分档惯性参数")
    print("\n" + "-" * 60)

    # 1. 备份当前配置
    print("\n[1/3] 备份当前预设值...")
    backup_presets()

    # 2. 更新预设值
    print("\n[2/3] 更新预设值...")
    success = update_presets()

    if success:
        # 3. 同步更新当前生效配置
        print("\n[3/3] 检查并更新当前生效配置...")
        update_active_config_if_needed()

        print("\n" + "=" * 60)
        print("✅ 更新完成！")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ 更新失败，请检查错误信息")
        print("=" * 60)


if __name__ == '__main__':
    main()
