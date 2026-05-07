"""
Dashboard API - aggregates system status for visual monitoring.

Provides a single endpoint that returns the full state of all implemented
features so the Web Dashboard can show what's running.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pymysql
from dotenv import load_dotenv
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

load_dotenv()

router = APIRouter(tags=["dashboard"])


def _db_config() -> dict[str, Any]:
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "mold_procurement"),
        "charset": "utf8mb4",
    }


def _safe_query(sql: str, params: tuple = ()) -> list[tuple]:
    """Run a SQL query; return [] on any error."""
    try:
        with pymysql.connect(**_db_config()) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return list(cur.fetchall())
    except Exception:
        return []


# ---------------------------------------------------------------------------
# API: JSON status
# ---------------------------------------------------------------------------

@router.get("/api/dashboard/status")
async def dashboard_status() -> dict[str, Any]:
    """Return the full system status as JSON."""
    # --- Agents & Skills via tool registry -----------------------------
    skills: list[dict[str, str]] = []
    agents: list[dict[str, Any]] = []
    try:
        from harness.tools import registry as tool_registry
        for tool in tool_registry.list_tools():
            skills.append({
                "name": tool.get("name", "unknown"),
                "description": tool.get("description", "")[:100],
                "permission": tool.get("permission", "read_only"),
            })
    except Exception as e:
        skills = [{"name": "_error_", "description": str(e), "permission": ""}]

    # Known agents (module presence)
    for module_path, label in [
        ("ai_modules.agents.exception_agent", "ExceptionAgent"),
        ("ai_modules.agents.quotation_agent", "QuotationAgent"),
    ]:
        try:
            __import__(module_path)
            agents.append({"name": label, "status": "loaded"})
        except Exception as e:
            agents.append({"name": label, "status": f"error: {e}"})

    # --- Database tables ----------------------------------------------
    tables_rows = _safe_query("SHOW TABLES")
    all_tables = [r[0] for r in tables_rows]

    workflow_tables = [t for t in all_tables if t.startswith("workflow_")]
    business_tables = [t for t in all_tables if not t.startswith("workflow_")]

    # Table row counts
    table_counts: dict[str, int] = {}
    for t in all_tables:
        rows = _safe_query(f"SELECT COUNT(*) FROM `{t}`")
        if rows:
            table_counts[t] = int(rows[0][0])

    # --- Workflow definitions -----------------------------------------
    definitions: list[dict[str, Any]] = []
    for row in _safe_query(
        "SELECT id, `key`, version, name, is_active, created_at "
        "FROM workflow_definitions ORDER BY created_at DESC LIMIT 20"
    ):
        definitions.append({
            "id": row[0], "key": row[1], "version": row[2],
            "name": row[3], "is_active": bool(row[4]),
            "created_at": row[5].isoformat() if row[5] else None,
        })

    # --- Workflow instances --------------------------------------------
    instances: list[dict[str, Any]] = []
    for row in _safe_query(
        "SELECT HEX(id), workflow_key, version, status, trigger_user, "
        "       started_at, ended_at FROM workflow_instances "
        "ORDER BY started_at DESC LIMIT 20"
    ):
        instances.append({
            "id": row[0], "workflow_key": row[1], "version": row[2],
            "status": row[3], "trigger_user": row[4],
            "started_at": row[5].isoformat() if row[5] else None,
            "ended_at": row[6].isoformat() if row[6] else None,
        })

    # --- Recent state events (audit log) -------------------------------
    events: list[dict[str, Any]] = []
    for row in _safe_query(
        "SELECT id, HEX(instance_id), node_id, event_type, from_status, "
        "       to_status, occurred_at FROM workflow_state_events "
        "ORDER BY occurred_at DESC LIMIT 30"
    ):
        events.append({
            "id": row[0],
            "instance_id": row[1][:8] + "..." if row[1] else None,
            "node_id": row[2], "event_type": row[3],
            "from_status": row[4], "to_status": row[5],
            "occurred_at": row[6].isoformat() if row[6] else None,
        })

    # --- Recent exceptions ----------------------------------------------
    exceptions: list[dict[str, Any]] = []
    for row in _safe_query(
        "SELECT exception_id, exception_type, description, status, "
        "       ai_confidence_score, ai_analysis_timestamp "
        "FROM exceptions ORDER BY id DESC LIMIT 10"
    ):
        exceptions.append({
            "exception_id": row[0], "exception_type": row[1],
            "description": (row[2] or "")[:80],
            "status": row[3],
            "ai_confidence_score": row[4],
            "ai_analysis_timestamp": row[5].isoformat() if row[5] else None,
        })

    # --- ChromaDB knowledge base --------------------------------------
    chroma_info: dict[str, Any] = {"available": False}
    try:
        import chromadb
        chroma_path = os.getenv("CHROMA_DB_PATH", "./chroma_db/exception_agent")
        abs_path = Path(chroma_path).resolve()
        if abs_path.exists():
            client = chromadb.PersistentClient(path=str(abs_path))
            collections = client.list_collections()
            chroma_info = {
                "available": True,
                "path": str(abs_path),
                "collections": [
                    {"name": c.name, "count": c.count()}
                    for c in collections
                ],
            }
    except Exception as e:
        chroma_info = {"available": False, "error": str(e)}

    # --- Feature completion summary -----------------------------------
    features = [
        {
            "name": "异常分析 Agent (ExceptionAgent)",
            "status": "ready",
            "description": "完整的异常根因分析+责任判定+方案推荐",
            "entrypoint": "POST /api/exception/analyze",
        },
        {
            "name": "报价分析 Agent (QuotationAgent)",
            "status": "ready",
            "description": "报价合理性分析+历史对比+议价策略",
            "entrypoint": "(代码可用, 未暴露API)",
        },
        {
            "name": "RAG 知识库 (ChromaDB)",
            "status": "ready" if chroma_info.get("available") else "unavailable",
            "description": f"向量检索，{sum(c['count'] for c in chroma_info.get('collections', []))} 个案例",
            "entrypoint": "通过 Skills 自动调用",
        },
        {
            "name": "Harness Workflow Engine (Phase A-C)",
            "status": "ready",
            "description": "DAG + 持久化 + 租约 + 状态机 + MVP 可跑",
            "entrypoint": "harness.workflow.WorkflowEngine",
        },
        {
            "name": "决策节点 DecisionNode",
            "status": "partial",
            "description": "loader 已支持, 执行器待 Phase D",
            "entrypoint": "—",
        },
        {
            "name": "并行节点 ParallelNode",
            "status": "pending",
            "description": "待 Phase D 实现",
            "entrypoint": "—",
        },
        {
            "name": "审批节点 ApprovalNode (12 种动作)",
            "status": "pending",
            "description": "待 Phase E 实现",
            "entrypoint": "—",
        },
        {
            "name": "WebSocket 实时推送",
            "status": "pending",
            "description": "待 Phase G 实现",
            "entrypoint": "—",
        },
    ]

    return {
        "timestamp": datetime.now().isoformat(),
        "agents": agents,
        "skills": skills,
        "features": features,
        "database": {
            "business_tables": business_tables,
            "workflow_tables": workflow_tables,
            "table_counts": table_counts,
        },
        "workflow": {
            "definitions": definitions,
            "instances": instances,
            "state_events": events,
        },
        "exceptions": exceptions,
        "rag": chroma_info,
    }


# ---------------------------------------------------------------------------
# HTML: Dashboard page
# ---------------------------------------------------------------------------

DASHBOARD_HTML_PATH = Path(__file__).parent / "_dashboard.html"


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page() -> str:
    """Serve the Dashboard HTML page."""
    if DASHBOARD_HTML_PATH.exists():
        return DASHBOARD_HTML_PATH.read_text(encoding="utf-8")
    return "<h1>Dashboard HTML not found</h1>"
