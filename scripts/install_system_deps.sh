#!/usr/bin/env bash
set -e

if command -v mysqldump >/dev/null 2>&1; then
  echo "mysqldump already installed."
  exit 0
fi

if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update && sudo apt-get install -y mysql-client
  exit 0
fi

if command -v yum >/dev/null 2>&1; then
  sudo yum install -y mysql
  exit 0
fi

if command -v dnf >/dev/null 2>&1; then
  sudo dnf install -y mysql
  exit 0
fi

if command -v apk >/dev/null 2>&1; then
  sudo apk add mysql-client
  exit 0
fi

echo "Unsupported package manager. Please install mysqldump manually."
exit 1
