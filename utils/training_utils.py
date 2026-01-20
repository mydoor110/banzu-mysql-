#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
培训模块工具函数
提供培训相关的辅助功能
"""
import re


def normalize_project_name(name):
    """
    清理项目名称，去除序号和中文标点符号
    
    处理规则：
    1. 去除开头的序号模式：
       - 数字+点：1. 2. 3.
       - 数字+顿号：1、2、3、
       - 括号数字：（1）(1) [1]
    2. 去除结尾的中文标点符号：，。、；：！？
    3. 去除多余的空格
    
    Args:
        name: 原始项目名称
        
    Returns:
        清理后的项目名称
        
    Examples:
        >>> normalize_project_name("1. 安全培训，")
        "安全培训"
        >>> normalize_project_name("2、消防演练。")
        "消防演练"
        >>> normalize_project_name("（3）应急处理")
        "应急处理"
    """
    if not name or not isinstance(name, str):
        return name
    
    # 去除首尾空格
    name = name.strip()
    
    # 去除开头的序号模式
    # 匹配：数字+点、数字+顿号、括号数字、多级编号等
    # 注意：多级编号模式必须放在前面，否则会被单级模式部分匹配
    patterns = [
        r'^\d+(\.\d+)+\s+',     # 1.2.3 或 1.2 后跟空格（多级编号，必须有至少一个点）
        r'^\d+\.\s*',           # 1. 2. 3.
        r'^\d+、\s*',           # 1、2、3、
        r'^（\d+）\s*',         # （1）（2）
        r'^\(\d+\)\s*',         # (1) (2)
        r'^\[\d+\]\s*',         # [1] [2]
        r'^【\d+】\s*',         # 【1】【2】
        r'^\d+\s+',             # 纯数字后跟空格（放在最后，避免误匹配）
    ]
    
    for pattern in patterns:
        name = re.sub(pattern, '', name)
    
    # 去除结尾的中文标点符号
    # 常见的中文标点：，。、；：！？
    name = re.sub(r'[，。、；：！？]+$', '', name)
    
    # 去除多余的空格（首尾）
    name = name.strip()
    
    return name
