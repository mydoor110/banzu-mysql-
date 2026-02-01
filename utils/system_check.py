#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统依赖检测模块
在应用启动时检测必需的系统工具
"""
import os
import sys
import shutil
import platform
import subprocess


class SystemChecker:
    """系统依赖检查器"""

    def __init__(self):
        self.os_type = platform.system().lower()
        self.missing_deps = []
        self.warnings = []

    def check_all(self, silent=False):
        """
        检查所有系统依赖

        Args:
            silent: 静默模式，只返回结果不打印

        Returns:
            bool: 所有必需依赖是否满足
        """
        if not silent:
            print("[-] Checking system dependencies...")

        # 检查 mysqldump（备份功能需要）
        self._check_mysqldump(silent)

        # 可以添加更多检查
        # self._check_other_tool(silent)

        if not silent:
            self._print_summary()

        return len(self.missing_deps) == 0

    def _check_mysqldump(self, silent=False):
        """检查 mysqldump 是否可用"""
        if shutil.which('mysqldump'):
            if not silent:
                print("   ✓ mysqldump found")
            return True
        else:
            self.missing_deps.append({
                'name': 'mysqldump',
                'required': False,  # 不是强制的，有后备方案
                'feature': '数据库备份功能',
                'install_hint': self._get_mysqldump_install_hint()
            })
            if not silent:
                print("   ⚠ mysqldump not found (备份功能将降级)")
            return False

    def _get_mysqldump_install_hint(self):
        """获取 mysqldump 安装提示"""
        hints = {
            'linux': {
                'debian': 'sudo apt-get install -y mysql-client',
                'ubuntu': 'sudo apt-get install -y mysql-client',
                'centos': 'sudo yum install -y mysql',
                'rhel': 'sudo yum install -y mysql',
                'fedora': 'sudo dnf install -y mysql',
                'alpine': 'sudo apk add mysql-client',
            },
            'darwin': 'brew install mysql-client',
            'windows': '请从 MySQL 官网下载并安装 MySQL Client'
        }

        if self.os_type == 'linux':
            # 尝试检测 Linux 发行版
            distro = self._detect_linux_distro()
            return hints['linux'].get(distro, 'sudo apt-get install -y mysql-client')
        elif self.os_type == 'darwin':
            return hints['darwin']
        elif self.os_type == 'windows':
            return hints['windows']
        else:
            return '未知操作系统，请手动安装 MySQL Client'

    def _detect_linux_distro(self):
        """检测 Linux 发行版"""
        try:
            # 尝试读取 /etc/os-release
            if os.path.exists('/etc/os-release'):
                with open('/etc/os-release', 'r') as f:
                    content = f.read().lower()
                    if 'ubuntu' in content:
                        return 'ubuntu'
                    elif 'debian' in content:
                        return 'debian'
                    elif 'centos' in content:
                        return 'centos'
                    elif 'rhel' in content or 'red hat' in content:
                        return 'rhel'
                    elif 'fedora' in content:
                        return 'fedora'
                    elif 'alpine' in content:
                        return 'alpine'
        except Exception:
            pass

        return 'unknown'

    def _print_summary(self):
        """打印检查结果摘要"""
        if not self.missing_deps and not self.warnings:
            print("[+] All system dependencies satisfied")
            return

        if self.missing_deps:
            print("\n" + "=" * 70)
            print("⚠️  缺少可选系统依赖")
            print("=" * 70)

            for dep in self.missing_deps:
                print(f"\n依赖: {dep['name']}")
                print(f"  功能: {dep['feature']}")
                print(f"  必需: {'是' if dep['required'] else '否（有替代方案）'}")
                print(f"  安装: {dep['install_hint']}")

            print("\n" + "=" * 70)
            print("💡 提示:")
            print("   1. 运行自动安装脚本: python3 scripts/install_deps.py")
            print("   2. 或手动执行上述安装命令")
            print("   3. 应用可以继续运行，但某些功能可能受限")
            print("=" * 70)

    def auto_install_prompt(self):
        """
        提示用户是否自动安装缺失的依赖

        Returns:
            bool: 用户是否同意安装
        """
        if not self.missing_deps:
            return True

        print("\n是否尝试自动安装缺失的依赖? (需要 sudo 权限)")
        print("1. 是，自动安装")
        print("2. 否，稍后手动安装")
        print("3. 跳过，继续启动应用")

        try:
            choice = input("\n请选择 [1/2/3]: ").strip()
            if choice == '1':
                return self._auto_install()
            elif choice == '2':
                print("\n请稍后手动安装依赖。")
                return False
            else:
                print("\n跳过依赖安装，继续启动...")
                return False
        except (KeyboardInterrupt, EOFError):
            print("\n\n用户取消，继续启动...")
            return False

    def _auto_install(self):
        """自动安装缺失的依赖"""
        print("\n[-] 开始自动安装...")

        for dep in self.missing_deps:
            if dep['name'] == 'mysqldump':
                success = self._install_mysqldump()
                if success:
                    print(f"   ✓ {dep['name']} 安装成功")
                else:
                    print(f"   ✗ {dep['name']} 安装失败，请手动安装")
                    return False

        print("[+] 所有依赖安装完成")
        return True

    def _install_mysqldump(self):
        """尝试自动安装 mysqldump"""
        install_cmd = None

        if self.os_type == 'linux':
            distro = self._detect_linux_distro()
            if distro in ['ubuntu', 'debian']:
                install_cmd = ['sudo', 'apt-get', 'install', '-y', 'mysql-client']
            elif distro in ['centos', 'rhel']:
                install_cmd = ['sudo', 'yum', 'install', '-y', 'mysql']
            elif distro == 'fedora':
                install_cmd = ['sudo', 'dnf', 'install', '-y', 'mysql']
            elif distro == 'alpine':
                install_cmd = ['sudo', 'apk', 'add', 'mysql-client']
        elif self.os_type == 'darwin':
            install_cmd = ['brew', 'install', 'mysql-client']

        if install_cmd:
            try:
                subprocess.run(install_cmd, check=True)
                return True
            except subprocess.CalledProcessError:
                return False
            except FileNotFoundError:
                print(f"   ⚠ 包管理器不可用，请手动安装")
                return False
        else:
            print(f"   ⚠ 不支持自动安装，请手动安装")
            return False


def check_system_dependencies(silent=False, interactive=False):
    """
    便捷函数：检查系统依赖

    Args:
        silent: 静默模式
        interactive: 交互模式（询问是否安装）

    Returns:
        bool: 是否满足所有依赖
    """
    checker = SystemChecker()
    all_satisfied = checker.check_all(silent=silent)

    if not all_satisfied and interactive and not silent:
        checker.auto_install_prompt()

    return all_satisfied


if __name__ == '__main__':
    # 独立运行时，使用交互模式
    print("=" * 70)
    print("系统依赖检查工具")
    print("=" * 70)
    check_system_dependencies(silent=False, interactive=True)
