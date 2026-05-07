"""
PostgreSQL connection helper for the MVP.

Swapped from pymysql → psycopg2. Keeps the same call surface
(fetch_one / fetch_all / execute / get_conn) so routes don't need
to care which driver is underneath.

Key PG adaptations:
  - Placeholder is still %s (psycopg2 accepts it, same as pymysql).
  - execute() for INSERT returns the new row id via RETURNING id,
    callers should use db.execute_returning() when they need the id.
  - Dict-style rows via psycopg2.extras.RealDictCursor.
  - Windows-中文 GBK messages during handshake are avoided by forcing
    client_encoding=UTF8 at the libpq level.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import psycopg2
import psycopg2.extensions
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

# Avoid Windows 中文版 Postgres handshake 乱码 (server locale zh_CN.GBK)
os.environ.setdefault("PGCLIENTENCODING", "UTF8")


def _config() -> dict[str, Any]:
    return {
        "host":     os.getenv("DB_HOST", "localhost"),
        "port":     int(os.getenv("DB_PORT", "5432")),
        "user":     os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", ""),
        "dbname":   os.getenv("DB_NAME", "weiwai"),
    }


@contextmanager
def get_conn() -> Iterator[psycopg2.extensions.connection]:
    """Context-managed DB connection. Commits on normal exit, rolls back on error."""
    conn = psycopg2.connect(**_config())
    # Force UTF8 for all subsequent queries (the handshake itself is protected
    # by the PGCLIENTENCODING env var above).
    conn.set_client_encoding("UTF8")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_one(sql: str, params: tuple | list | dict | None = None) -> dict | None:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or ())
            row = cur.fetchone()
            return dict(row) if row else None


def fetch_all(sql: str, params: tuple | list | dict | None = None) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or ())
            rows = cur.fetchall()
            return [dict(r) for r in rows]


def execute(sql: str, params: tuple | list | dict | None = None) -> int:
    """Execute an INSERT/UPDATE/DELETE.

    - For INSERTs: if the SQL contains ``RETURNING id`` (recommended), the
      new row id is returned. Callers that previously relied on
      ``cur.lastrowid`` MUST append ``RETURNING id`` to their statement.
    - For UPDATE/DELETE: returns the affected row count.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            # If the statement returned rows (e.g. RETURNING id), fetch the first value
            if cur.description is not None:
                row = cur.fetchone()
                return int(row[0]) if row else 0
            return cur.rowcount
