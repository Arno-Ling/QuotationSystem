"""
Run migration 002: create workflow engine tables.

Idempotent: safe to run multiple times (uses CREATE TABLE IF NOT EXISTS).

Usage:
    python backend/database/migrations/run_workflow_migration.py

Requirements: REQ-021
"""
import os
import sys
from pathlib import Path

import pymysql
from dotenv import load_dotenv

# Ensure backend/ is on the path
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(BACKEND_DIR / ".env")


MIGRATION_FILE = Path(__file__).parent / "002_add_workflow_tables.sql"
EXPECTED_TABLES = [
    "workflow_definitions",
    "workflow_instances",
    "workflow_node_executions",
    "workflow_approval_records",
    "workflow_approval_tasks",
    "workflow_state_events",
]


def run_migration() -> bool:
    """Execute the workflow tables migration.

    Returns True on success, False on failure.
    """
    config = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "mold_procurement"),
        "charset": "utf8mb4",
    }

    print("=" * 70)
    print("Workflow Engine - Migration 002")
    print("=" * 70)
    print(f"Target DB: {config['user']}@{config['host']}:{config['port']}/{config['database']}")
    print(f"SQL file : {MIGRATION_FILE}")
    print()

    if not MIGRATION_FILE.exists():
        print(f"[ERROR] Migration file not found: {MIGRATION_FILE}")
        return False

    sql_script = MIGRATION_FILE.read_text(encoding="utf-8")

    # Split on semicolons; strip comments/blank lines inside each statement
    statements = []
    current = []
    for raw_line in sql_script.splitlines():
        line = raw_line.strip()
        # Skip pure comment lines
        if line.startswith("--") or not line:
            continue
        current.append(raw_line)
        if line.rstrip().endswith(";"):
            stmt = "\n".join(current).strip()
            # Strip trailing ;
            if stmt.endswith(";"):
                stmt = stmt[:-1].strip()
            if stmt:
                statements.append(stmt)
            current = []

    print(f"Parsed {len(statements)} SQL statements")

    try:
        conn = pymysql.connect(**config)
    except pymysql.err.OperationalError as e:
        print(f"[ERROR] Cannot connect to database: {e}")
        return False

    try:
        with conn.cursor() as cursor:
            for i, stmt in enumerate(statements, 1):
                head = stmt.splitlines()[0][:60]
                print(f"  [{i}/{len(statements)}] {head}...")
                try:
                    cursor.execute(stmt)
                    conn.commit()
                except pymysql.err.Error as e:
                    print(f"     [ERROR] {e}")
                    conn.rollback()
                    return False
            print()

            # Verify all expected tables exist
            print("Verifying tables:")
            cursor.execute("SHOW TABLES LIKE 'workflow_%'")
            found = {row[0] for row in cursor.fetchall()}

            all_ok = True
            for table in EXPECTED_TABLES:
                mark = "[OK]" if table in found else "[MISSING]"
                print(f"  {mark} {table}")
                if table not in found:
                    all_ok = False

            if all_ok:
                print()
                print("Migration 002 completed successfully.")
                print(f"  - {len(EXPECTED_TABLES)} tables created")
                return True
            else:
                print()
                print("[ERROR] Some tables were not created")
                return False

    finally:
        conn.close()


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
