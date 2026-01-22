
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.database import init_database, bootstrap_data, get_db

def verify_fix():
    print("Running database initialization...")
    try:
        # Initialize tables (should create missing table)
        init_database()
        
        # Bootstrap data (should seed missing table)
        bootstrap_data()
        
        print("Initialization completed.")
        
        # Verify table exists
        conn = get_db()
        cur = conn.cursor()
        
        print("Verifying ai_analysis_config table...")
        cur.execute("SHOW TABLES LIKE 'ai_analysis_config'")
        if not cur.fetchone():
            print("ERROR: Table ai_analysis_config does not exist!")
            return False
            
        # Verify data exists
        cur.execute("SELECT count(*) as count FROM ai_analysis_config")
        row = cur.fetchone()
        count = row['count']
        print(f"Table row count: {count}")
        
        if count == 0:
            print("ERROR: Table is empty!")
            return False

        print("SUCCESS: Table created and seeded.")
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if verify_fix():
        sys.exit(0)
    else:
        sys.exit(1)
