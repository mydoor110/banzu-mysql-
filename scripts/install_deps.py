#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统依赖自动安装脚本
一键安装所需的系统工具（如 mysqldump）
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.system_check import SystemChecker


def main():
    """主函数"""
    print("=" * 70)
    print("系统依赖自动安装工具")
    print("=" * 70)
    print()

    # 创建检查器
    checker = SystemChecker()

    # 执行检查
    all_satisfied = checker.check_all(silent=False)

    if all_satisfied:
        print("\n" + "=" * 70)
        print("✓ 所有依赖已满足，无需安装")
        print("=" * 70)
        return 0

    # 询问是否安装
    print("\n" + "=" * 70)
    print("发现缺失的依赖")
    print("=" * 70)

    for dep in checker.missing_deps:
        print(f"\n依赖: {dep['name']}")
        print(f"  用途: {dep['feature']}")
        print(f"  必需: {'是' if dep['required'] else '否（有替代方案）'}")
        print(f"  安装命令: {dep['install_hint']}")

    print("\n" + "=" * 70)
    print("安装选项:")
    print("  1. 自动安装（推荐，需要 sudo 权限）")
    print("  2. 显示安装命令，稍后手动安装")
    print("  3. 跳过安装")
    print("=" * 70)

    try:
        choice = input("\n请选择 [1/2/3]: ").strip()

        if choice == '1':
            print("\n开始自动安装...\n")
            success = checker._auto_install()

            if success:
                print("\n" + "=" * 70)
                print("✓ 所有依赖安装成功!")
                print("=" * 70)
                return 0
            else:
                print("\n" + "=" * 70)
                print("✗ 部分依赖安装失败，请查看上方错误信息")
                print("=" * 70)
                return 1

        elif choice == '2':
            print("\n" + "=" * 70)
            print("手动安装命令:")
            print("=" * 70)
            for dep in checker.missing_deps:
                print(f"\n# 安装 {dep['name']}")
                print(dep['install_hint'])
            print("\n安装完成后，请重新运行此脚本验证。")
            print("=" * 70)
            return 0

        else:
            print("\n跳过安装。")
            print("注意: 某些功能可能无法使用（如数据库备份）。")
            return 0

    except (KeyboardInterrupt, EOFError):
        print("\n\n用户取消")
        return 130


if __name__ == '__main__':
    sys.exit(main())
