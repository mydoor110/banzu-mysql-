#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全管理领域纯函数

从 blueprints/safety.py 提取的纯业务逻辑函数，
供 blueprints.safety / blueprints.personnel / services 共同引用。
"""
import re


def extract_score_from_assessment(assessment):
    """
    从考核情况中提取分值
    逻辑：从右向左扫描所有数字。
    1. 优先寻找带"分"的数字。
    2. 如果数字带"元/钱"或看起来像金额（如迟到罚款），则跳过该数字，继续向左找。
    3. 如果找到无明确单位的数字，且不像金额，则返回。
    4. 如果所有数字都被判定为金额，则返回0。
    """
    if not assessment:
        return 0

    # 1. 过滤正面评价
    positive_keywords = ['继续发扬', '正常', '良好', '优秀', '表扬', '未发现']
    for keyword in positive_keywords:
        if keyword in assessment:
            return 0

    # 2. 提取所有数字及其位置
    matches = list(re.finditer(r'(\d+(\.\d+)?)', assessment))

    if not matches:
        return 1  # 默认扣1分

    # 从右向左遍历（倒序）
    for match in reversed(matches):
        val_str = match.group(1)
        value = float(val_str)
        end_pos = match.end()
        start_pos = match.start()

        # 查看数字后面的文字 (suffix)
        suffix = assessment[end_pos:end_pos + 5]
        # 查看数字前面的文字 (prefix)
        prefix = assessment[max(0, start_pos - 5):start_pos]

        # A. 检查是否明确是金额 -> 跳过
        if any(u in suffix for u in ['元', '钱', '块', '¥', '￥']):
            continue

        # B. 检查是否明确是分数 -> 返回
        if '分' in suffix:
            return value

        # C. 无明确单位 - 上下文判断

        # C1. 迟到/早退 且数值 > 10 -> 视为金额，跳过
        if ('迟到' in assessment or '早退' in assessment) and value > 10:
            continue

        # C2. 前缀包含"罚款"、"扣款"、"金额" -> 视为金额，跳过
        if any(k in prefix for k in ['罚款', '扣款', '金额']):
            continue

        # D. 默认视为分数（例如 "扣5", "考核: 3"）
        return value

    # 如果所有数字都被跳过（都是钱），则不扣分
    return 0
