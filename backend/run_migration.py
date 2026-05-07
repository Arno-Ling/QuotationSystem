"""
Run database migration script
"""
import pymysql
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def run_migration():
    """Run the database migration"""
    try:
        # Connect to database
        connection = pymysql.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 3306)),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME', 'mold_procurement'),
            charset='utf8mb4'
        )
        
        print("✓ Connected to database")
        
        # Read migration script
        with open('database/migrations/001_add_ai_analysis_columns.sql', 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        # Split by semicolons and execute each statement
        statements = [s.strip() for s in sql_script.split(';') if s.strip() and not s.strip().startswith('--')]
        
        cursor = connection.cursor()
        
        for statement in statements:
            # Skip USE statement and comments
            if statement.upper().startswith('USE') or statement.startswith('--'):
                continue
            
            try:
                print(f"Executing: {statement[:50]}...")
                cursor.execute(statement)
                connection.commit()
                print("✓ Success")
            except pymysql.err.OperationalError as e:
                if 'Duplicate column name' in str(e):
                    print(f"⚠ Column already exists, skipping...")
                else:
                    raise
        
        # Verify the changes
        cursor.execute("DESCRIBE exceptions")
        columns = cursor.fetchall()
        
        print("\n=== Current exceptions table structure ===")
        ai_columns = [col for col in columns if col[0].startswith('ai_')]
        if ai_columns:
            print("✓ AI analysis columns found:")
            for col in ai_columns:
                print(f"  - {col[0]} ({col[1]})")
        else:
            print("⚠ No AI analysis columns found")
        
        cursor.close()
        connection.close()
        
        print("\n✓ Migration completed successfully")
        
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_migration()
