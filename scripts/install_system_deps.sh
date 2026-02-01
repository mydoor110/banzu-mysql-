#!/usr/bin/env bash
# 系统依赖安装脚本
# 优先使用 Python 脚本（更智能），降级到简单 bash 脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 尝试使用 Python 脚本（推荐）
if command -v python3 >/dev/null 2>&1; then
  echo "使用 Python 安装脚本..."
  python3 "$SCRIPT_DIR/install_deps.py"
  exit $?
fi

# 降级到简单的 bash 脚本
echo "Python3 not found, using fallback bash script..."
echo "Note: For better experience, install Python3 first."
echo ""

if command -v mysqldump >/dev/null 2>&1; then
  echo "✓ mysqldump already installed."
  exit 0
fi

echo "mysqldump not found, attempting to install..."

if command -v apt-get >/dev/null 2>&1; then
  echo "Detected apt-get (Debian/Ubuntu)"
  sudo apt-get update && sudo apt-get install -y mysql-client
  echo "✓ mysql-client installed"
  exit 0
fi

if command -v yum >/dev/null 2>&1; then
  echo "Detected yum (CentOS/RHEL)"
  sudo yum install -y mysql
  echo "✓ mysql installed"
  exit 0
fi

if command -v dnf >/dev/null 2>&1; then
  echo "Detected dnf (Fedora)"
  sudo dnf install -y mysql
  echo "✓ mysql installed"
  exit 0
fi

if command -v apk >/dev/null 2>&1; then
  echo "Detected apk (Alpine)"
  sudo apk add mysql-client
  echo "✓ mysql-client installed"
  exit 0
fi

if command -v brew >/dev/null 2>&1; then
  echo "Detected brew (macOS)"
  brew install mysql-client
  echo "✓ mysql-client installed"
  exit 0
fi

echo "✗ Unsupported package manager."
echo "Please install mysqldump manually:"
echo ""
echo "  Ubuntu/Debian:  sudo apt-get install -y mysql-client"
echo "  CentOS/RHEL:    sudo yum install -y mysql"
echo "  Fedora:         sudo dnf install -y mysql"
echo "  Alpine:         sudo apk add mysql-client"
echo "  macOS:          brew install mysql-client"
echo ""
exit 1
