"""
Run migration 003: Lightweight Script MVP — create 5 new tables.

Idempotent: safe to run multiple times (uses CREATE TABLE IF NOT EXISTS).

Usage:
    python backend/migrations/run_003_migration.py

Requirements: design.md §Data Models, §决策 1
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pymysql
from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(BACKEND_DIR / ".env")


MIGRATION_FILE = Path(__file__).parent / "003_mvp_lightweight.sql"
EXPECTED_TABLES = [
    "drawings",
    "boms",
    "ai_analyses",
    "workflow_runs",
    "notifications",
]


def _split_statements(sql_script: str) -> list[str]:
    """Split the SQL script into individual statements (naive ; splitter).

    Comments (-- ...) and blank lines are stripped first.
    """
    statements: list[str] = []
    current: list[str] = []

    for raw_line in sql_script.splitlines():
        stripped = raw_line.strip()
        # Drop pure comment or empty lines
        if not stripped or stripped.startswith("--"):
            continue
        current.append(raw_line)
        if stripped.rstrip().endswith(";"):
            stmt = "\n".join(current).strip().rstrip(";").strip()
            if stmt:
                statements.append(stmt)
            current = []

    # Trailing statement without ;
    if current:
        stmt = "\n".join(current).strip()
        if stmt:
            statements.append(stmt)

    return statements


def _stmt_summary(stmt: str, max_len: int = 70) -> str:
    """Collapse whitespace and truncate for log output."""
    one_line = re.sub(r"\s+", " ", stmt).strip()
    return one_line[:max_len] + ("..." if len(one_line) > max_len else "")


def run_migration() -> bool:
    """Execute the migration. Returns True on success."""
    config = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "mold_procurement"),
        "charset": "utf8mb4",
    }

    print("=" * 70)
    print("Lightweight Script MVP - Migration 003")
    print("=" * 70)
    print(
        f"Target DB: {config['user']}@{config['host']}:{config['port']}"
        f"/{config['database']}"
    )
    print(f"SQL file : {MIGRATION_FILE}")
    print()

    if not MIGRATION_FILE.exists():
        print(f"[ERROR] Migration file not found: {MIGRATION_FILE}")
        return False

    sql_script = MIGRATION_FILE.read_text(encoding="utf-8")
    statements = _split_statements(sql_script)
    print(f"Parsed {len(statements)} SQL statements")

    try:
        conn = pymysql.connect(**config)
    except pymysql.err.OperationalError as e:
        print(f"[ERROR] Cannot connect to database: {e}")
        return False

    try:
        with conn.cursor() as cur:
            for i, stmt in enumerate(statements, 1):
                print(f"  [{i}/{len(statements)}] {_stmt_summary(stmt)}")
                try:
                    cur.execute(stmt)
                    conn.commit()
                except pymysql.err.Error as e:
                    print(f"     [ERROR] {e}")
                    conn.rollback()
                    return False
            print()

            # Verify each expected table exists in information_schema
            print("Verifying tables:")
            placeholders = ",".join(["%s"] * len(EXPECTED_TABLES))
            cur.execute(
                f"""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = %s AND table_name IN ({placeholders})
                """,
                (config["database"], *EXPECTED_TABLES),
            )
            found = {row[0] for row in cur.fetchall()}

            all_ok = True
            for table in EXPECTED_TABLES:
                mark = "[OK]" if table in found else "[MISSING]"
                print(f"  {mark} {table}")
                if table not in found:
                    all_ok = False

            if all_ok:
                print()
                print("Migration 003 completed successfully.")
                print(f"  - {len(EXPECTED_TABLES)} new tables created")
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
