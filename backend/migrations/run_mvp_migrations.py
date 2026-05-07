"""
Run MVP migrations 004, 005, 006 in order.

Idempotent: safe to run multiple times.
Usage:
    python backend/migrations/run_mvp_migrations.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pymysql
from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

MIGRATIONS = [
    ("004_mvp_core.sql", [
        "tenants", "users", "projects", "project_parts", "attachments",
    ]),
    ("005_production_decision.sql", [
        "supplier_capabilities", "production_decisions",
    ]),
    ("006_outsource.sql", [
        "outsource_requests", "outsource_request_invitations",
        "outsource_quotations", "outsource_orders",
        "outsource_order_status_events",
    ]),
]


def _split_statements(sql: str) -> list[str]:
    """Split SQL file into statements by `;`, skipping comments and blank lines."""
    out: list[str] = []
    cur: list[str] = []
    for raw in sql.splitlines():
        s = raw.strip()
        if not s or s.startswith("--"):
            continue
        cur.append(raw)
        if s.rstrip().endswith(";"):
            stmt = "\n".join(cur).strip().rstrip(";").strip()
            if stmt:
                out.append(stmt)
            cur = []
    if cur:
        stmt = "\n".join(cur).strip()
        if stmt:
            out.append(stmt)
    return out


def _summary(stmt: str, n: int = 70) -> str:
    s = re.sub(r"\s+", " ", stmt).strip()
    return s[:n] + ("..." if len(s) > n else "")


def _db_config() -> dict:
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "mold_procurement"),
        "charset": "utf8mb4",
    }


def run_one(filename: str, expected_tables: list[str]) -> bool:
    """Run one migration file. Returns True on success."""
    path = Path(__file__).parent / filename
    print("-" * 70)
    print(f"Migration: {filename}")
    print("-" * 70)

    if not path.exists():
        print(f"  [ERROR] file not found: {path}")
        return False

    sql = path.read_text(encoding="utf-8")
    stmts = _split_statements(sql)
    if not stmts:
        print("  (empty / placeholder — skipped)")
        return True

    print(f"  Parsed {len(stmts)} statements")

    config = _db_config()
    try:
        conn = pymysql.connect(**config)
    except pymysql.err.OperationalError as e:
        print(f"  [ERROR] cannot connect: {e}")
        return False

    try:
        with conn.cursor() as cur:
            for i, stmt in enumerate(stmts, 1):
                print(f"    [{i}/{len(stmts)}] {_summary(stmt)}")
                try:
                    cur.execute(stmt)
                    conn.commit()
                except pymysql.err.Error as e:
                    print(f"       [ERROR] {e}")
                    conn.rollback()
                    return False

            # Verify expected tables
            if expected_tables:
                placeholders = ",".join(["%s"] * len(expected_tables))
                cur.execute(
                    f"""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = %s AND table_name IN ({placeholders})
                    """,
                    (config["database"], *expected_tables),
                )
                found = {r[0] for r in cur.fetchall()}
                ok = True
                print(f"\n  Verifying {len(expected_tables)} tables:")
                for t in expected_tables:
                    mark = "[OK]" if t in found else "[MISSING]"
                    print(f"    {mark} {t}")
                    if t not in found:
                        ok = False
                if not ok:
                    return False
    finally:
        conn.close()

    return True


def main() -> int:
    cfg = _db_config()
    print("=" * 70)
    print("MVP Migrations (0 / 1 / 3)")
    print("=" * 70)
    print(f"Target: {cfg['user']}@{cfg['host']}:{cfg['port']}/{cfg['database']}\n")

    for fname, tables in MIGRATIONS:
        if not run_one(fname, tables):
            print(f"\n[FAIL] Migration {fname} failed. Stopping.")
            return 1
        print()

    print("=" * 70)
    print("[OK] All MVP migrations completed successfully.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
