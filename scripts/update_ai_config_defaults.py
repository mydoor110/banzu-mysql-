#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新数据库中AI提示语的默认配置

从 AIPromptConfigService.FALLBACK_CONFIGS 读取最新的默认值，
更新数据库中的 default_instruction 字段。

如果用户的 current_instruction 等于旧的 default_instruction，
也会同步更新 current_instruction 到新的默认值。
"""
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.database import get_db
from services.ai_prompt_config_service import AIPromptConfigService


def update_ai_config_defaults():
    """更新数据库中的AI配置默认值"""
    conn = get_db()
    cur = conn.cursor()

    print("=" * 80)
    print("更新 AI 提示语默认配置")
    print("=" * 80)
    print()

    # 获取最新的默认配置
    fallback_configs = AIPromptConfigService.FALLBACK_CONFIGS

    for config_key in AIPromptConfigService.CONFIG_ORDER:
        config = fallback_configs.get(config_key)
        if not config:
            continue

        new_default = config['instruction']
        title = config['title']

        # 查询当前数据库中的配置
        cur.execute("""
            SELECT default_instruction, current_instruction
            FROM ai_analysis_config
            WHERE config_key = %s
        """, (config_key,))
        row = cur.fetchone()

        if not row:
            print(f"⚠ 配置 {config_key} 不存在于数据库，跳过")
            continue

        old_default = row['default_instruction']
        current_instruction = row['current_instruction']

        # 检查是否需要更新
        if old_default == new_default:
            print(f"✓ {title}")
            print(f"  配置键: {config_key}")
            print(f"  默认值无变化，无需更新")
            print()
            continue

        # 检查用户是否使用默认配置
        is_using_default = (current_instruction == old_default)

        print(f"📝 {title}")
        print(f"  配置键: {config_key}")
        print(f"  用户是否使用默认: {is_using_default}")
        print()
        print(f"  旧默认值:")
        print(f"    {old_default[:80]}...")
        print(f"  新默认值:")
        print(f"    {new_default[:80]}...")
        print()

        # 更新 default_instruction
        cur.execute("""
            UPDATE ai_analysis_config
            SET default_instruction = %s,
                updated_at = NOW()
            WHERE config_key = %s
        """, (new_default, config_key))

        # 如果用户使用的是旧默认值，也更新 current_instruction
        if is_using_default:
            cur.execute("""
                UPDATE ai_analysis_config
                SET current_instruction = %s,
                    updated_at = NOW()
                WHERE config_key = %s
            """, (new_default, config_key))
            print(f"  ✓ 已更新 default_instruction 和 current_instruction")
        else:
            print(f"  ✓ 已更新 default_instruction（保留用户自定义的 current_instruction）")

        print()

    conn.commit()

    print("=" * 80)
    print("更新完成")
    print("=" * 80)


if __name__ == '__main__':
    try:
        update_ai_config_defaults()
        sys.exit(0)
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
