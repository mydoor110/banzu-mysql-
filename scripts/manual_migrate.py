import sys
import os
from dotenv import load_dotenv

# 手动加载 .env
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..'))
dotenv_path = os.path.join(project_root, '.env')

if os.path.exists(dotenv_path):
    print(f"Loading .env from {dotenv_path}")
    load_dotenv(dotenv_path)
else:
    print("Warning: .env file not found")

# 添加项目根目录到 path
sys.path.append(project_root)

try:
    from models.database import init_database
    print("Beginning database migration...")
    init_database()
    print("Database migration completed successfully.")
except Exception as e:
    print(f"Migration failed: {e}")
