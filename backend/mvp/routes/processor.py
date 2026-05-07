"""
Processor tenant routes (加工方视角).

Stage 3:
  - 查看分配给我的询价邀请
  - 查看邀请详情（零件清单 + 图纸）
  - 提交报价
  - 查看我的加工单
  - 推进加工单状态（accepted → producing → delivered）
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from mvp import db
from mvp.auth import CurrentUser, require_tenant_type

router = APIRouter(prefix="/api/processor", tags=["processor"])

_require_processor = require_tenant_type("processor")


class QuoteSubmit(BaseModel):
    unit_price: float = Field(..., gt=0)
    lead_time_days: int = Field(..., ge=1)
    note: Optional[str] = None


class StatusTransition(BaseModel):
    to_status: str = Field(..., pattern="^(accepted|producing|delivered|cancelled)$")
    note: Optional[str] = None


# Valid order status transitions
ORDER_TRANSITIONS = {
    "awarded": {"accepted", "cancelled"},
    "accepted": {"producing", "cancelled"},
    "producing": {"delivered", "cancelled"},
    "delivered": set(),
    "cancelled": set(),
}


def _my_tenant_id(user: CurrentUser) -> int:
    """Convenience — processor user's tenant id。"""
    return user.tenant_id


# =============================================================================
# 询价邀请
# =============================================================================

@router.get("/invitations")
async def list_invitations(
    user: CurrentUser = Depends(_require_processor),
    status_filter: Optional[str] = None,
):
    """只看 tenant_id = 我的租户 的邀请。"""
    where = "WHERE i.tenant_id = %s"
    params: list[Any] = [_my_tenant_id(user)]
    if status_filter:
        where += " AND i.invitation_status = %s"
        params.append(status_filter)

    rows = db.fetch_all(
        f"""
        SELECT i.id, i.request_id, i.invitation_status,
               i.sent_at, i.quoted_at,
               r.title AS request_title, r.required_processes_json,
               r.quantity, r.deadline, r.status AS request_status,
               p.project_no, p.name AS project_name,
               q.id AS quotation_id, q.unit_price, q.lead_time_days, q.submitted_at
        FROM outsource_request_invitations i
        JOIN outsource_requests r ON i.request_id = r.id
        JOIN projects p ON r.project_id = p.id
        LEFT JOIN outsource_quotations q ON q.invitation_id = i.id
        {where}
        ORDER BY i.sent_at DESC
        LIMIT 100
        """,
        tuple(params),
    )
    for r in rows:
        raw = r.get("required_processes_json")
        r["required_processes"] = json.loads(raw) if isinstance(raw, str) and raw else (raw or [])
        r.pop("required_processes_json", None)
        if r.get("unit_price") is not None:
            r["unit_price"] = float(r["unit_price"])
        for k in ("sent_at", "quoted_at", "submitted_at"):
            if r.get(k):
                r[k] = r[k].isoformat() if hasattr(r[k], "isoformat") else r[k]

    # 统计
    stats = {
        "pending_quote": sum(1 for r in rows if r["invitation_status"] == "sent"),
        "quoted": sum(1 for r in rows if r["invitation_status"] == "quoted"),
        "expired": sum(1 for r in rows if r["invitation_status"] == "no_response"),
    }
    return {"items": rows, "total": len(rows), "stats": stats}


@router.get("/invitations/{inv_id}")
async def get_invitation(
    inv_id: int,
    user: CurrentUser = Depends(_require_processor),
):
    inv = db.fetch_one(
        """
        SELECT i.*, r.id AS req_id, r.title AS request_title,
               r.required_processes_json, r.quantity, r.deadline,
               r.status AS request_status,
               p.id AS project_id, p.project_no, p.name AS project_name,
               p.customer, p.unit_price AS client_unit_price
        FROM outsource_request_invitations i
        JOIN outsource_requests r ON i.request_id = r.id
        JOIN projects p ON r.project_id = p.id
        WHERE i.id = %s
        """,
        (inv_id,),
    )
    if inv is None:
        raise HTTPException(status_code=404)
    if inv["tenant_id"] != _my_tenant_id(user):
        raise HTTPException(status_code=403, detail="Not your invitation")

    raw = inv.get("required_processes_json")
    inv["required_processes"] = json.loads(raw) if isinstance(raw, str) and raw else (raw or [])
    inv.pop("required_processes_json", None)

    # 零件清单（用于加工方估报价）
    parts = db.fetch_all(
        """
        SELECT id, part_no, part_name, material, qty, processes_json, spec
        FROM project_parts WHERE project_id = %s
        """,
        (inv["project_id"],),
    )
    for p in parts:
        raw = p.get("processes_json")
        p["processes"] = json.loads(raw) if isinstance(raw, str) and raw else (raw or [])
        p.pop("processes_json", None)

    # 图纸列表（下载链接由 internal 端控制；MVP 简化：加工方可直接下）
    attachments = db.fetch_all(
        """
        SELECT id, file_name, file_size, mime_type, created_at
        FROM attachments
        WHERE related_type = 'project' AND related_id = %s
        ORDER BY created_at DESC
        """,
        (inv["project_id"],),
    )

    # 我的报价（若已提交）
    my_quote = db.fetch_one(
        "SELECT id, unit_price, lead_time_days, note, submitted_at FROM outsource_quotations WHERE invitation_id = %s",
        (inv_id,),
    )
    if my_quote and my_quote.get("unit_price") is not None:
        my_quote["unit_price"] = float(my_quote["unit_price"])
        if my_quote.get("submitted_at"):
            my_quote["submitted_at"] = my_quote["submitted_at"].isoformat()

    return {
        "invitation": inv,
        "parts": parts,
        "attachments": attachments,
        "my_quote": my_quote,
    }


@router.post("/invitations/{inv_id}/quote")
async def submit_quote(
    inv_id: int,
    payload: QuoteSubmit,
    user: CurrentUser = Depends(_require_processor),
):
    inv = db.fetch_one(
        """
        SELECT i.*, r.status AS request_status
        FROM outsource_request_invitations i
        JOIN outsource_requests r ON i.request_id = r.id
        WHERE i.id = %s
        """,
        (inv_id,),
    )
    if inv is None:
        raise HTTPException(status_code=404)
    if inv["tenant_id"] != _my_tenant_id(user):
        raise HTTPException(status_code=403)
    if inv["request_status"] not in ("inviting",):
        raise HTTPException(status_code=409,
                            detail=f"询价单当前状态 '{inv['request_status']}' 不再接受报价")
    if inv["invitation_status"] not in ("sent", "quoted"):
        raise HTTPException(status_code=409,
                            detail=f"邀请状态 '{inv['invitation_status']}' 不允许报价")

    now = datetime.utcnow()
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            # Upsert 报价 (1 invitation → 1 quote)
            cur.execute(
                """
                INSERT INTO outsource_quotations
                    (invitation_id, unit_price, lead_time_days, note, submitted_by, submitted_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (invitation_id) DO UPDATE SET
                    unit_price = EXCLUDED.unit_price,
                    lead_time_days = EXCLUDED.lead_time_days,
                    note = EXCLUDED.note,
                    submitted_by = EXCLUDED.submitted_by,
                    submitted_at = EXCLUDED.submitted_at
                """,
                (inv_id, payload.unit_price, payload.lead_time_days,
                 payload.note, user.user_id, now),
            )
            cur.execute(
                """
                UPDATE outsource_request_invitations
                SET invitation_status = 'quoted', quoted_at = %s
                WHERE id = %s
                """,
                (now, inv_id),
            )

    return {"status": "quoted", "submitted_at": now.isoformat()}


# =============================================================================
# 加工单
# =============================================================================

@router.get("/orders")
async def list_orders(
    user: CurrentUser = Depends(_require_processor),
    status_filter: Optional[str] = None,
):
    where = "WHERE o.tenant_id = %s"
    params: list[Any] = [_my_tenant_id(user)]
    if status_filter:
        where += " AND o.status = %s"
        params.append(status_filter)

    rows = db.fetch_all(
        f"""
        SELECT o.id, o.order_no, o.unit_price, o.quantity, o.total_amount,
               o.lead_time_days, o.status,
               o.awarded_at, o.accepted_at, o.delivered_at,
               r.title AS request_title,
               p.project_no, p.name AS project_name
        FROM outsource_orders o
        JOIN outsource_requests r ON o.request_id = r.id
        JOIN projects p ON r.project_id = p.id
        {where}
        ORDER BY o.awarded_at DESC
        LIMIT 100
        """,
        tuple(params),
    )
    for r in rows:
        if r.get("unit_price"): r["unit_price"] = float(r["unit_price"])
        if r.get("total_amount"): r["total_amount"] = float(r["total_amount"])
        for k in ("awarded_at", "accepted_at", "delivered_at"):
            if r.get(k):
                r[k] = r[k].isoformat() if hasattr(r[k], "isoformat") else r[k]
    return {"items": rows, "total": len(rows)}


@router.get("/orders/{order_id}")
async def get_order(
    order_id: int,
    user: CurrentUser = Depends(_require_processor),
):
    row = db.fetch_one(
        """
        SELECT o.*, r.title AS request_title, r.required_processes_json,
               p.project_no, p.name AS project_name, p.deadline AS project_deadline
        FROM outsource_orders o
        JOIN outsource_requests r ON o.request_id = r.id
        JOIN projects p ON r.project_id = p.id
        WHERE o.id = %s
        """,
        (order_id,),
    )
    if row is None:
        raise HTTPException(status_code=404)
    if row["tenant_id"] != _my_tenant_id(user):
        raise HTTPException(status_code=403)

    raw = row.get("required_processes_json")
    row["required_processes"] = json.loads(raw) if isinstance(raw, str) and raw else (raw or [])
    row.pop("required_processes_json", None)

    # 转数值 + 时间
    for k in ("unit_price", "total_amount"):
        if row.get(k) is not None:
            row[k] = float(row[k])
    for k in ("awarded_at", "accepted_at", "delivered_at", "created_at", "updated_at"):
        if row.get(k):
            row[k] = row[k].isoformat() if hasattr(row[k], "isoformat") else row[k]

    # 零件清单
    parts = db.fetch_all(
        """
        SELECT part_no, part_name, material, qty, processes_json, spec
        FROM project_parts pp
        WHERE pp.project_id = (SELECT project_id FROM outsource_requests WHERE id = %s)
        """,
        (row["request_id"],),
    )
    for p in parts:
        raw = p.get("processes_json")
        p["processes"] = json.loads(raw) if isinstance(raw, str) and raw else (raw or [])
        p.pop("processes_json", None)

    # 状态事件
    events = db.fetch_all(
        """
        SELECT from_status, to_status, note, occurred_at
        FROM outsource_order_status_events
        WHERE order_id = %s ORDER BY occurred_at ASC
        """,
        (order_id,),
    )
    for e in events:
        if e.get("occurred_at"):
            e["occurred_at"] = e["occurred_at"].isoformat()

    return {"order": row, "parts": parts, "events": events}


@router.post("/orders/{order_id}/status")
async def update_order_status(
    order_id: int,
    payload: StatusTransition,
    user: CurrentUser = Depends(_require_processor),
):
    row = db.fetch_one(
        "SELECT id, status, tenant_id FROM outsource_orders WHERE id = %s",
        (order_id,),
    )
    if row is None:
        raise HTTPException(status_code=404)
    if row["tenant_id"] != _my_tenant_id(user):
        raise HTTPException(status_code=403)

    current = row["status"]
    allowed = ORDER_TRANSITIONS.get(current, set())
    if payload.to_status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"状态转换不合法: {current} → {payload.to_status}；允许: {sorted(allowed)}",
        )

    now = datetime.utcnow()
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            # Timestamps
            ts_update = ""
            if payload.to_status == "accepted":
                ts_update = ", accepted_at = NOW()"
            elif payload.to_status == "delivered":
                ts_update = ", delivered_at = NOW()"

            cur.execute(
                f"UPDATE outsource_orders SET status = %s{ts_update} WHERE id = %s",
                (payload.to_status, order_id),
            )
            cur.execute(
                """
                INSERT INTO outsource_order_status_events
                    (order_id, from_status, to_status, changed_by, note, occurred_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (order_id, current, payload.to_status, user.user_id, payload.note, now),
            )

    return {"status": payload.to_status, "occurred_at": now.isoformat()}


# =============================================================================
# Attachment download (proxy via internal)
# =============================================================================

from fastapi.responses import FileResponse
from pathlib import Path


UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"


@router.get("/attachments/{attachment_id}/download")
async def download_attachment(
    attachment_id: int,
    user: CurrentUser = Depends(_require_processor),
):
    """加工方可下载与其邀请/订单关联的项目附件。"""
    att = db.fetch_one(
        """
        SELECT a.file_name, a.file_path, a.mime_type, a.related_id AS project_id
        FROM attachments a
        WHERE a.id = %s AND a.related_type = 'project'
        """,
        (attachment_id,),
    )
    if att is None:
        raise HTTPException(status_code=404)

    # 授权：这个 project 必须有发给我的邀请或者加工单
    has_access = db.fetch_one(
        """
        SELECT 1 AS ok FROM outsource_request_invitations i
        JOIN outsource_requests r ON i.request_id = r.id
        WHERE i.tenant_id = %s AND r.project_id = %s
        LIMIT 1
        """,
        (_my_tenant_id(user), att["project_id"]),
    )
    if not has_access:
        raise HTTPException(status_code=403, detail="您没有访问该项目附件的权限")

    full = UPLOADS_DIR / att["file_path"]
    if not full.exists():
        raise HTTPException(status_code=410, detail="File missing")

    return FileResponse(
        path=str(full),
        filename=att["file_name"],
        media_type=att.get("mime_type") or "application/octet-stream",
    )
