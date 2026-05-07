"""
Internal tenant routes (我方视角).

Stage 0 - projects CRUD + parts + attachments + confirm.
Stage 1 will extend with production_decisions + approvals.
Stage 3 will extend with outsource requests/orders.
"""
from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from mvp import db
from mvp.auth import CurrentUser, require_tenant_type

router = APIRouter(prefix="/api/internal", tags=["internal"])

_require_internal = require_tenant_type("internal")

UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
DRAWINGS_DIR = UPLOADS_DIR / "drawings"
DRAWINGS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    customer: str = Field(..., min_length=1, max_length=255)
    deadline: Optional[str] = None                       # YYYY-MM-DD
    unit_price: Optional[float] = None
    quantity: Optional[int] = None
    description: str = ""


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    customer: Optional[str] = None
    deadline: Optional[str] = None
    unit_price: Optional[float] = None
    quantity: Optional[int] = None
    description: Optional[str] = None


class PartCreate(BaseModel):
    part_no: str = Field(..., min_length=1, max_length=64)
    part_name: Optional[str] = None
    material: Optional[str] = None
    qty: int = Field(default=1, ge=1)
    processes: list[str] = Field(default_factory=list)
    spec: Optional[str] = None


class ProcessCreate(BaseModel):
    """创建/更新一道工序。工序号由后端按 P<seq>-<method>[-<faces>] 生成。"""
    method_name: str = Field(..., min_length=1, max_length=32)
    faces: Optional[str] = None                       # "A,B,C" / None
    notes: Optional[str] = None
    est_hours: Optional[float] = None
    seq_no: Optional[int] = None                      # 省略则自动追加为下一个


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

# 租户前缀字典：tenant name → 项目号首字母
# 瑞利捷 M  / 其他客户可以追加；未命中取名字首字的拼音首字母或 'X'
_TENANT_PREFIX_BY_NAME = {
    "我方-模具制造厂":   "M",   # 瑞利捷模具（MVP 内部租户）
    "瑞利捷":           "M",
}


def _tenant_prefix(tenant_name: str | None) -> str:
    if not tenant_name:
        return "X"
    # 精确匹配
    if tenant_name in _TENANT_PREFIX_BY_NAME:
        return _TENANT_PREFIX_BY_NAME[tenant_name]
    # 模糊匹配：名字里包含关键字
    for key, prefix in _TENANT_PREFIX_BY_NAME.items():
        if key in tenant_name:
            return prefix
    # 回退：取 ASCII 首字母，或中文第一字的 fallback
    for ch in tenant_name:
        if ch.isascii() and ch.isalpha():
            return ch.upper()
    return "X"


def _next_project_no(tenant_id: int, tenant_name: str | None) -> tuple[str, int, str]:
    """生成项目编号：<租户前缀><YY>-<4位序号>，例 M26-0013。
    租户内 年内 序号从 1 开始累加。返回 (project_no, tenant_seq, year_suffix)。
    """
    prefix = _tenant_prefix(tenant_name)
    year_suffix = datetime.now().strftime("%y")   # 例如 '26'

    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(MAX(tenant_seq), 0)
                FROM projects
                WHERE tenant_id = %s AND year_suffix = %s
                """,
                (tenant_id, year_suffix),
            )
            max_seq = cur.fetchone()[0] or 0

    seq = max_seq + 1
    return f"{prefix}{year_suffix}-{seq:04d}", seq, year_suffix


def _gen_project_no() -> str:
    """[legacy] Kept for any caller; new flow uses _next_project_no()."""
    return f"PRJ-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


@router.get("/projects")
async def list_projects(
    user: CurrentUser = Depends(_require_internal),
    status_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    offset = max(0, (page - 1) * page_size)
    where = "WHERE tenant_id = %s"
    params: list[Any] = [user.tenant_id]
    if status_filter:
        where += " AND status = %s"
        params.append(status_filter)

    rows = db.fetch_all(
        f"""
        SELECT id, project_no, name, customer, deadline, unit_price, quantity,
               status, created_at, updated_at
        FROM projects {where}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
        """,
        (*params, page_size, offset),
    )
    total_row = db.fetch_one(
        f"SELECT COUNT(*) AS cnt FROM projects {where}",
        tuple(params),
    )
    return {
        "items": rows,
        "total": total_row["cnt"] if total_row else 0,
        "page": page,
        "page_size": page_size,
    }


@router.post("/projects", status_code=201)
async def create_project(
    payload: ProjectCreate,
    user: CurrentUser = Depends(_require_internal),
):
    # 生成租户内 年内 自增项目号：例 M26-0013
    project_no, tenant_seq, year_suffix = _next_project_no(user.tenant_id, user.tenant_name)
    new_id = db.execute(
        """
        INSERT INTO projects (tenant_id, project_no, tenant_seq, year_suffix,
                              name, customer, deadline,
                              unit_price, quantity, description, status, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'drafted', %s)
        RETURNING id
        """,
        (user.tenant_id, project_no, tenant_seq, year_suffix,
         payload.name, payload.customer,
         payload.deadline, payload.unit_price, payload.quantity,
         payload.description, user.user_id),
    )
    return {"id": new_id, "project_no": project_no, "status": "drafted"}


@router.get("/projects/{project_id}")
async def get_project(
    project_id: int,
    user: CurrentUser = Depends(_require_internal),
):
    project = db.fetch_one(
        """
        SELECT id, project_no, name, customer, deadline, unit_price, quantity,
               description, status, created_by, confirmed_at, created_at, updated_at
        FROM projects WHERE id = %s AND tenant_id = %s
        """,
        (project_id, user.tenant_id),
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    parts = db.fetch_all(
        """
        SELECT id, part_no, part_name, material, qty, processes_json, spec,
               created_at
        FROM project_parts WHERE project_id = %s ORDER BY id ASC
        """,
        (project_id,),
    )
    for p in parts:
        raw = p.get("processes_json")
        p["processes"] = (
            json.loads(raw) if isinstance(raw, str) and raw else (raw or [])
        )
        p.pop("processes_json", None)

        # 新：从 project_processes 返回结构化工序
        proc_rows = db.fetch_all(
            """
            SELECT pp.id, pp.seq_no, pp.process_code, pp.method_name,
                   pp.faces, pp.notes, pp.est_hours,
                   pm.is_internal_capable, pm.category
            FROM project_processes pp
            LEFT JOIN process_methods pm ON pm.name = pp.method_name
            WHERE pp.part_id = %s
            ORDER BY pp.seq_no ASC
            """,
            (p["id"],),
        )
        for pr in proc_rows:
            if pr.get("est_hours") is not None:
                pr["est_hours"] = float(pr["est_hours"])
        p["process_list"] = proc_rows

    attachments = db.fetch_all(
        """
        SELECT id, file_name, file_path, file_size, mime_type, category, created_at
        FROM attachments
        WHERE related_type = 'project' AND related_id = %s
        ORDER BY created_at DESC
        """,
        (project_id,),
    )

    return {
        "project": project,
        "parts": parts,
        "attachments": attachments,
    }


@router.patch("/projects/{project_id}")
async def update_project(
    project_id: int,
    payload: ProjectUpdate,
    user: CurrentUser = Depends(_require_internal),
):
    project = db.fetch_one(
        "SELECT id, status FROM projects WHERE id = %s AND tenant_id = %s",
        (project_id, user.tenant_id),
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project["status"] not in ("drafted",):
        raise HTTPException(status_code=409,
                            detail=f"Cannot edit project in status '{project['status']}'")

    updates: list[str] = []
    params: list[Any] = []
    for field, value in payload.model_dump(exclude_unset=True).items():
        updates.append(f"{field} = %s")
        params.append(value)
    if not updates:
        return {"updated": False}

    params.extend([project_id, user.tenant_id])
    db.execute(
        f"UPDATE projects SET {', '.join(updates)} "
        f"WHERE id = %s AND tenant_id = %s",
        tuple(params),
    )
    return {"updated": True}


@router.post("/projects/{project_id}/parts", status_code=201)
async def add_part(
    project_id: int,
    payload: PartCreate,
    user: CurrentUser = Depends(_require_internal),
):
    project = db.fetch_one(
        "SELECT id, status FROM projects WHERE id = %s AND tenant_id = %s",
        (project_id, user.tenant_id),
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project["status"] != "drafted":
        raise HTTPException(status_code=409,
                            detail="Only 'drafted' projects can have parts added")

    new_id = db.execute(
        """
        INSERT INTO project_parts (project_id, part_no, part_name, material,
                                   qty, processes_json, spec)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (project_id, payload.part_no, payload.part_name, payload.material,
         payload.qty, json.dumps(payload.processes, ensure_ascii=False),
         payload.spec),
    )
    return {"id": new_id}


@router.delete("/projects/{project_id}/parts/{part_id}")
async def delete_part(
    project_id: int,
    part_id: int,
    user: CurrentUser = Depends(_require_internal),
):
    project = db.fetch_one(
        "SELECT id, status FROM projects WHERE id = %s AND tenant_id = %s",
        (project_id, user.tenant_id),
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project["status"] != "drafted":
        raise HTTPException(status_code=409, detail="Project is not editable")

    db.execute(
        "DELETE FROM project_parts WHERE id = %s AND project_id = %s",
        (part_id, project_id),
    )
    return {"deleted": True}


# ---------------------------------------------------------------------------
# 工序 — Processes (project_processes 表)
# ---------------------------------------------------------------------------

def _build_process_code(seq_no: int, method_name: str, faces: str | None) -> str:
    """生成工序编号：P<seq>-<method>[-<faces>]。"""
    parts = [f"P{seq_no}", method_name]
    if faces:
        # 规范化：去空格、大写、用逗号连接
        norm_faces = ",".join(f.strip().upper() for f in faces.split(",") if f.strip())
        if norm_faces:
            parts.append(norm_faces)
    return "-".join(parts)


@router.get("/process-methods")
async def list_process_methods(user: CurrentUser = Depends(_require_internal)):
    """加工方式字典（供前端下拉用）。"""
    rows = db.fetch_all(
        """
        SELECT name, category, is_internal_capable, remark
        FROM process_methods
        ORDER BY category, name
        """
    )
    return {"items": rows, "total": len(rows)}


@router.get("/projects/{project_id}/parts/{part_id}/processes")
async def list_processes(
    project_id: int, part_id: int,
    user: CurrentUser = Depends(_require_internal),
):
    # 校验归属
    p = db.fetch_one(
        "SELECT id FROM projects WHERE id = %s AND tenant_id = %s",
        (project_id, user.tenant_id),
    )
    if p is None:
        raise HTTPException(status_code=404, detail="Project not found")

    rows = db.fetch_all(
        """
        SELECT pp.id, pp.seq_no, pp.process_code, pp.method_name,
               pp.faces, pp.notes, pp.est_hours, pm.is_internal_capable,
               pm.category
        FROM project_processes pp
        LEFT JOIN process_methods pm ON pm.name = pp.method_name
        WHERE pp.part_id = %s AND pp.project_id = %s
        ORDER BY pp.seq_no ASC
        """,
        (part_id, project_id),
    )
    for r in rows:
        if r.get("est_hours") is not None:
            r["est_hours"] = float(r["est_hours"])
    return {"items": rows, "total": len(rows)}


@router.post("/projects/{project_id}/parts/{part_id}/processes", status_code=201)
async def add_process(
    project_id: int, part_id: int,
    payload: ProcessCreate,
    user: CurrentUser = Depends(_require_internal),
):
    """新增一道工序；seq_no 省略则自动追加。"""
    p = db.fetch_one(
        "SELECT id, status FROM projects WHERE id = %s AND tenant_id = %s",
        (project_id, user.tenant_id),
    )
    if p is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if p["status"] != "drafted":
        raise HTTPException(status_code=409, detail="只有 drafted 项目可以编辑工序")

    part = db.fetch_one(
        "SELECT id FROM project_parts WHERE id = %s AND project_id = %s",
        (part_id, project_id),
    )
    if part is None:
        raise HTTPException(status_code=404, detail="Part not found")

    method = db.fetch_one(
        "SELECT name FROM process_methods WHERE name = %s",
        (payload.method_name,),
    )
    if method is None:
        raise HTTPException(status_code=400,
                            detail=f"未知加工方式：{payload.method_name}。请先到 /api/internal/process-methods 查看可选值")

    # 分配 seq_no
    if payload.seq_no is not None:
        seq_no = payload.seq_no
    else:
        row = db.fetch_one(
            "SELECT COALESCE(MAX(seq_no), 0) AS mx FROM project_processes WHERE part_id = %s",
            (part_id,),
        )
        seq_no = (row["mx"] or 0) + 1

    process_code = _build_process_code(seq_no, payload.method_name, payload.faces)

    try:
        new_id = db.execute(
            """
            INSERT INTO project_processes
                (project_id, part_id, seq_no, process_code,
                 method_name, faces, notes, est_hours)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (project_id, part_id, seq_no, process_code,
             payload.method_name,
             payload.faces if payload.faces else None,
             payload.notes, payload.est_hours),
        )
    except Exception as e:
        # 唯一约束撞车（seq_no 或 process_code 已存在）
        if "uk_proc_part_seq" in str(e) or "uk_proc_part_code" in str(e):
            raise HTTPException(status_code=409,
                                detail=f"工序号冲突：{process_code} 已存在于该零件下")
        raise

    return {
        "id": new_id,
        "seq_no": seq_no,
        "process_code": process_code,
        "method_name": payload.method_name,
        "faces": payload.faces,
    }


@router.delete("/processes/{process_id}")
async def delete_process(
    process_id: int,
    user: CurrentUser = Depends(_require_internal),
):
    # 校验归属（通过 project 查）
    row = db.fetch_one(
        """
        SELECT pp.id, p.status, p.tenant_id
        FROM project_processes pp
        JOIN projects p ON pp.project_id = p.id
        WHERE pp.id = %s
        """,
        (process_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Process not found")
    if row["tenant_id"] != user.tenant_id:
        raise HTTPException(status_code=403)
    if row["status"] != "drafted":
        raise HTTPException(status_code=409, detail="只有 drafted 项目可以编辑工序")

    db.execute("DELETE FROM project_processes WHERE id = %s", (process_id,))
    return {"deleted": True}


@router.post("/projects/{project_id}/attachments", status_code=201)
async def upload_attachment(
    project_id: int,
    file: UploadFile = File(...),
    category: str = Form("drawing"),
    user: CurrentUser = Depends(_require_internal),
):
    project = db.fetch_one(
        "SELECT id FROM projects WHERE id = %s AND tenant_id = %s",
        (project_id, user.tenant_id),
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Save file with unique name
    ext = Path(file.filename or "").suffix
    stored_name = f"{project_id}_{uuid.uuid4().hex}{ext}"
    target_dir = DRAWINGS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / stored_name

    with target_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    size = target_path.stat().st_size

    new_id = db.execute(
        """
        INSERT INTO attachments (related_type, related_id, file_name, file_path,
                                 file_size, mime_type, uploaded_by, category)
        VALUES ('project', %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (project_id, file.filename, f"drawings/{stored_name}",
         size, file.content_type, user.user_id, category),
    )
    return {
        "id": new_id,
        "file_name": file.filename,
        "file_size": size,
    }


@router.post("/projects/{project_id}/confirm")
async def confirm_project(
    project_id: int,
    user: CurrentUser = Depends(_require_internal),
):
    """项目确认 — 检查前置条件后把 status 从 drafted 置为 confirmed。
    前置：
      - 至少 1 个零件
      - 至少 1 份图纸
      - unit_price 和 quantity 已填
    """
    project = db.fetch_one(
        """
        SELECT id, status, unit_price, quantity
        FROM projects WHERE id = %s AND tenant_id = %s
        """,
        (project_id, user.tenant_id),
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project["status"] != "drafted":
        raise HTTPException(status_code=409,
                            detail=f"Project already {project['status']}")

    # Check parts
    parts_cnt = db.fetch_one(
        "SELECT COUNT(*) AS cnt FROM project_parts WHERE project_id = %s",
        (project_id,),
    )
    if not parts_cnt or parts_cnt["cnt"] < 1:
        raise HTTPException(status_code=400,
                            detail="至少需要 1 个零件才能确认项目")

    # Check drawings
    draw_cnt = db.fetch_one(
        """
        SELECT COUNT(*) AS cnt FROM attachments
        WHERE related_type = 'project' AND related_id = %s AND category = 'drawing'
        """,
        (project_id,),
    )
    if not draw_cnt or draw_cnt["cnt"] < 1:
        raise HTTPException(status_code=400,
                            detail="至少需要上传 1 份图纸才能确认项目")

    # Check price / quantity
    if not project["unit_price"] or not project["quantity"]:
        raise HTTPException(status_code=400,
                            detail="请先填写报价单价和订单数量")

    db.execute(
        """
        UPDATE projects
        SET status = 'confirmed', confirmed_at = %s
        WHERE id = %s AND tenant_id = %s
        """,
        (datetime.utcnow(), project_id, user.tenant_id),
    )
    return {"status": "confirmed"}


# ---------------------------------------------------------------------------
# File serving (drawings) - 仅受保护的接口
# ---------------------------------------------------------------------------

from fastapi.responses import FileResponse


@router.get("/attachments/{attachment_id}/download")
async def download_attachment(
    attachment_id: int,
    user: CurrentUser = Depends(_require_internal),
):
    att = db.fetch_one(
        "SELECT file_name, file_path, mime_type FROM attachments WHERE id = %s",
        (attachment_id,),
    )
    if att is None:
        raise HTTPException(status_code=404, detail="Attachment not found")

    full_path = UPLOADS_DIR / att["file_path"]
    if not full_path.exists():
        raise HTTPException(status_code=410, detail="File missing from storage")

    return FileResponse(
        path=str(full_path),
        filename=att["file_name"],
        media_type=att.get("mime_type") or "application/octet-stream",
    )


# =============================================================================
# Stage 1: Production Decisions + Approvals
# =============================================================================

from mvp.rules import suggest_decision


class DecisionUpdate(BaseModel):
    final_decision: str = Field(..., pattern="^(self_made|outsource)$")
    final_reason: Optional[str] = None


class ApprovalAction(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$")
    comment: Optional[str] = None


# ---------------------------------------------------------------------------
# POST /api/internal/projects/{id}/decide — trigger hardcoded AI decisions
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/decide")
async def trigger_decide(
    project_id: int,
    user: CurrentUser = Depends(_require_internal),
):
    """为项目的每个零件×工序生成一行决策建议。
    前置：项目 status = confirmed 或 deciding（重新触发）。
    """
    project = db.fetch_one(
        "SELECT id, status FROM projects WHERE id = %s AND tenant_id = %s",
        (project_id, user.tenant_id),
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project["status"] not in ("confirmed", "deciding"):
        raise HTTPException(status_code=409,
                            detail=f"Project status must be 'confirmed', now '{project['status']}'")

    # 读所有零件
    parts = db.fetch_all(
        "SELECT id, part_no, processes_json FROM project_parts WHERE project_id = %s",
        (project_id,),
    )
    if not parts:
        raise HTTPException(status_code=400, detail="Project has no parts")

    # 检查是否已经存在未定的决策行（重新触发时先清理 pending_review 的）
    db.execute(
        """
        DELETE FROM production_decisions
        WHERE project_id = %s AND status IN ('pending_review', 'reviewed')
        """,
        (project_id,),
    )

    created = 0
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            for pt in parts:
                procs_raw = pt.get("processes_json")
                procs = (
                    json.loads(procs_raw) if isinstance(procs_raw, str) and procs_raw
                    else (procs_raw or [])
                )
                for proc in procs:
                    sug = suggest_decision(proc)
                    cur.execute(
                        """
                        INSERT INTO production_decisions
                            (project_id, part_id, process_name,
                             ai_suggestion, ai_reason, ai_source, is_forced,
                             final_decision, status)
                        VALUES (%s, %s, %s, %s, %s, 'rules', %s, %s, 'pending_review')
                        """,
                        (project_id, pt["id"], proc,
                         sug.decision, sug.reason, 1 if sug.is_forced else 0,
                         sug.decision),  # final_decision 初始 = AI 建议
                    )
                    created += 1

            # 项目进入 deciding 状态
            cur.execute(
                "UPDATE projects SET status = 'deciding' WHERE id = %s",
                (project_id,),
            )

    return {"created": created, "status": "deciding"}


@router.get("/projects/{project_id}/decisions")
async def list_decisions(
    project_id: int,
    user: CurrentUser = Depends(_require_internal),
):
    """Return all production_decisions for a project."""
    project = db.fetch_one(
        "SELECT id, status FROM projects WHERE id = %s AND tenant_id = %s",
        (project_id, user.tenant_id),
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    rows = db.fetch_all(
        """
        SELECT d.id, d.part_id, d.process_name,
               d.ai_suggestion, d.ai_reason, d.ai_source, d.is_forced,
               d.final_decision, d.final_reason,
               d.reviewed_by, d.reviewed_at, d.status,
               d.approval_task_id, d.created_at,
               p.part_no, p.part_name, p.material
        FROM production_decisions d
        JOIN project_parts p ON d.part_id = p.id
        WHERE d.project_id = %s
        ORDER BY p.id ASC, d.id ASC
        """,
        (project_id,),
    )
    # 转 is_forced 为 bool
    for r in rows:
        r["is_forced"] = bool(r.get("is_forced"))
    return {
        "project_status": project["status"],
        "items": rows,
        "total": len(rows),
    }


@router.patch("/decisions/{decision_id}")
async def update_decision(
    decision_id: int,
    payload: DecisionUpdate,
    user: CurrentUser = Depends(_require_internal),
):
    """人工修改单行决策。强制委外行只能保持 outsource。"""
    row = db.fetch_one(
        """
        SELECT d.id, d.is_forced, d.ai_suggestion, d.status, p.tenant_id
        FROM production_decisions d
        JOIN projects p ON d.project_id = p.id
        WHERE d.id = %s
        """,
        (decision_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    if row["tenant_id"] != user.tenant_id:
        raise HTTPException(status_code=403, detail="Not your project")
    if row["status"] not in ("pending_review", "reviewed"):
        raise HTTPException(status_code=409,
                            detail=f"Cannot edit decision in status '{row['status']}'")

    if row["is_forced"] and payload.final_decision == "self_made":
        raise HTTPException(status_code=409,
                            detail="该工序为强制委外项，不允许改为自制")

    db.execute(
        """
        UPDATE production_decisions
        SET final_decision = %s,
            final_reason   = %s,
            reviewed_by    = %s,
            reviewed_at    = %s,
            status         = 'reviewed'
        WHERE id = %s
        """,
        (payload.final_decision, payload.final_reason, user.user_id,
         datetime.utcnow(), decision_id),
    )
    return {"updated": True}


@router.post("/projects/{project_id}/decisions/submit")
async def submit_decisions(
    project_id: int,
    user: CurrentUser = Depends(_require_internal),
):
    """提交批次审批 → 创建 1 条 workflow_approval_tasks 给生产经理。"""
    project = db.fetch_one(
        "SELECT id, status FROM projects WHERE id = %s AND tenant_id = %s",
        (project_id, user.tenant_id),
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project["status"] != "deciding":
        raise HTTPException(status_code=409,
                            detail=f"Project not in 'deciding' state: {project['status']}")

    # 确保所有决策行都已 reviewed（final_decision 非空即可）
    missing = db.fetch_one(
        """
        SELECT COUNT(*) AS cnt FROM production_decisions
        WHERE project_id = %s AND (final_decision IS NULL OR final_decision = '')
        """,
        (project_id,),
    )
    if missing and missing["cnt"] > 0:
        raise HTTPException(status_code=400,
                            detail=f"还有 {missing['cnt']} 行决策未审核")

    # Check existing approval task; avoid double-submit
    existing = db.fetch_one(
        """
        SELECT id FROM workflow_approval_tasks
        WHERE assignee_type = 'role' AND assignee_id = 'PRODUCTION_MANAGER'
          AND node_id = %s AND status = 'pending'
        """,
        (f"production_decision:{project_id}",),
    )
    if existing:
        return {"submitted": True, "task_id": existing["id"], "note": "已有待办，未重复创建"}

    # 创建审批任务 + 初始 SUBMIT 记录 + 状态事件 (单事务)
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            # 1) Task
            # workflow_approval_tasks.instance_id 在 PG 里是 UUID；MVP 不强绑定工作流实例，
            # 用 uuid5(project_id) 产生一个稳定的占位 UUID。
            import uuid as _uuid
            fake_instance_id = _uuid.uuid5(_uuid.NAMESPACE_URL, f"project:{project_id}")

            cur.execute(
                """
                INSERT INTO workflow_approval_tasks
                    (instance_id, node_id, assignee_type, assignee_id, status)
                VALUES (%s, %s, 'role', 'PRODUCTION_MANAGER', 'pending')
                RETURNING id
                """,
                (str(fake_instance_id), f"production_decision:{project_id}"),
            )
            task_id = cur.fetchone()[0]

            # 2) Initial SUBMIT record
            record_uuid = _uuid.uuid4()
            cur.execute(
                """
                INSERT INTO workflow_approval_records
                    (id, instance_id, node_id, action, actor_id,
                     assignee_type, assignee_id, comment, metadata_json, created_at)
                VALUES (%s, %s, %s, 'submit', %s, 'role', 'PRODUCTION_MANAGER', %s, %s, %s)
                """,
                (str(record_uuid), str(fake_instance_id),
                 f"production_decision:{project_id}",
                 str(user.user_id),
                 f"提交生产决策: project_id={project_id}",
                 json.dumps({
                     "kind": "production_decision",
                     "project_id": project_id,
                     "task_id": task_id,
                 }, ensure_ascii=False),
                 datetime.utcnow()),
            )

            # 3) State event
            cur.execute(
                """
                INSERT INTO workflow_state_events
                    (instance_id, node_id, event_type, to_status, payload_json, occurred_at)
                VALUES (%s, %s, 'approval_task_created', 'pending', %s, %s)
                """,
                (str(fake_instance_id),
                 f"production_decision:{project_id}",
                 json.dumps({"project_id": project_id, "task_id": task_id}, ensure_ascii=False),
                 datetime.utcnow()),
            )

            # 4) 把决策行 status → submitted，并关联 task_id
            cur.execute(
                """
                UPDATE production_decisions
                SET status = 'submitted', approval_task_id = %s
                WHERE project_id = %s
                """,
                (task_id, project_id),
            )

    return {"submitted": True, "task_id": task_id}


# ---------------------------------------------------------------------------
# Approval — 待办 + 查看 + 执行
# ---------------------------------------------------------------------------

@router.get("/approvals/pending")
async def list_pending_approvals(
    user: CurrentUser = Depends(_require_internal),
):
    """当前用户能看到的待办。

    匹配规则：
      - assignee_type='user' AND assignee_id=user_id
      - 或 assignee_type='role' AND assignee_id=UPPER(user.role)
    """
    role_match = (user.role or "").upper()

    rows = db.fetch_all(
        """
        SELECT t.id, t.instance_id::text AS instance_hex, t.node_id,
               t.assignee_type, t.assignee_id, t.status, t.due_at, t.created_at
        FROM workflow_approval_tasks t
        WHERE t.status = 'pending'
          AND (
               (t.assignee_type = 'user' AND t.assignee_id = %s)
            OR (t.assignee_type = 'role' AND t.assignee_id = %s)
          )
        ORDER BY t.created_at DESC
        LIMIT 100
        """,
        (str(user.user_id), role_match),
    )

    # For each task, 附加业务摘要（从 node_id 提取 project_id 并取名称）
    for r in rows:
        node = r.get("node_id") or ""
        r["kind"] = node.split(":", 1)[0] if ":" in node else node
        r["subject_id"] = node.split(":", 1)[1] if ":" in node else None
        r["due_at"] = r["due_at"].isoformat() if r["due_at"] else None
        r["created_at"] = r["created_at"].isoformat() if r["created_at"] else None

        # Try to enrich with project name
        if r["kind"] == "production_decision" and r["subject_id"]:
            try:
                p = db.fetch_one(
                    "SELECT name, project_no FROM projects WHERE id = %s",
                    (int(r["subject_id"]),),
                )
                if p:
                    r["subject_title"] = f"{p['project_no']} — {p['name']}"
            except Exception:
                r["subject_title"] = None

    return {"items": rows, "total": len(rows)}


@router.get("/approvals/{task_id}")
async def get_approval_detail(
    task_id: int,
    user: CurrentUser = Depends(_require_internal),
):
    """审批任务详情 + 业务载荷。"""
    task = db.fetch_one(
        """
        SELECT id, instance_id::text AS instance_hex, node_id,
               assignee_type, assignee_id, status, due_at, created_at
        FROM workflow_approval_tasks WHERE id = %s
        """,
        (task_id,),
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    # 权限：任务 assignee 必须匹配当前用户
    role_match = (user.role or "").upper()
    is_mine = (
        (task["assignee_type"] == "user" and task["assignee_id"] == str(user.user_id)) or
        (task["assignee_type"] == "role" and task["assignee_id"] == role_match)
    )
    if not is_mine:
        raise HTTPException(status_code=403, detail="Not your task")

    node = task["node_id"] or ""
    kind = node.split(":", 1)[0] if ":" in node else node
    subject_id = node.split(":", 1)[1] if ":" in node else None
    task["kind"] = kind
    task["subject_id"] = subject_id
    task["created_at"] = task["created_at"].isoformat() if task["created_at"] else None

    # Load payload based on kind
    payload: dict = {}
    if kind == "production_decision" and subject_id:
        project_id = int(subject_id)
        project = db.fetch_one(
            """
            SELECT id, project_no, name, customer, deadline, unit_price, quantity
            FROM projects WHERE id = %s
            """,
            (project_id,),
        )
        decisions = db.fetch_all(
            """
            SELECT d.id, d.process_name, d.ai_suggestion, d.ai_reason,
                   d.is_forced, d.final_decision, d.final_reason,
                   p.part_no, p.part_name, p.material
            FROM production_decisions d
            JOIN project_parts p ON d.part_id = p.id
            WHERE d.project_id = %s
            ORDER BY p.id ASC, d.id ASC
            """,
            (project_id,),
        )
        for d in decisions:
            d["is_forced"] = bool(d.get("is_forced"))
        payload = {"project": project, "decisions": decisions}

    elif kind == "outsource_award" and subject_id:
        # 采购经理审批：打包所有已报价邀请为表格
        request_id = int(subject_id)
        req = db.fetch_one(
            """
            SELECT r.*, p.project_no, p.name AS project_name, p.customer,
                   p.unit_price AS client_unit_price
            FROM outsource_requests r
            JOIN projects p ON r.project_id = p.id
            WHERE r.id = %s
            """,
            (request_id,),
        )
        if req:
            raw = req.get("required_processes_json")
            req["required_processes"] = json.loads(raw) if isinstance(raw, str) and raw else (raw or [])
            req.pop("required_processes_json", None)

        invs = db.fetch_all(
            """
            SELECT i.id AS invitation_id, i.supplier_id, i.invitation_status,
                   s.name AS supplier_name, s.category AS supplier_category,
                   q.id AS quotation_id, q.unit_price, q.lead_time_days,
                   q.note, q.submitted_at
            FROM outsource_request_invitations i
            JOIN suppliers s ON i.supplier_id = s.id
            LEFT JOIN outsource_quotations q ON q.invitation_id = i.id
            WHERE i.request_id = %s AND i.invitation_status = 'quoted'
            ORDER BY q.unit_price ASC
            """,
            (request_id,),
        )
        for v in invs:
            if v.get("unit_price") is not None:
                v["unit_price"] = float(v["unit_price"])
            if v.get("submitted_at"):
                v["submitted_at"] = v["submitted_at"].isoformat()
        payload = {"request": req, "quotations": invs}

    # Approval history
    history = db.fetch_all(
        """
        SELECT id::text AS record_id, action, actor_id, comment, created_at
        FROM workflow_approval_records
        WHERE instance_id = %s::uuid
        ORDER BY created_at ASC
        """,
        (task["instance_hex"],),
    )
    for h in history:
        h["created_at"] = h["created_at"].isoformat() if h["created_at"] else None

    return {
        "task": task,
        "payload": payload,
        "history": history,
    }


@router.post("/approvals/{task_id}/action")
async def act_approval(
    task_id: int,
    payload: ApprovalAction,
    user: CurrentUser = Depends(_require_internal),
):
    """APPROVE/REJECT 审批任务。"""
    task = db.fetch_one(
        """
        SELECT id, instance_id::text AS instance_hex, node_id,
               assignee_type, assignee_id, status
        FROM workflow_approval_tasks WHERE id = %s
        """,
        (task_id,),
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] != "pending":
        raise HTTPException(status_code=409,
                            detail=f"Task already {task['status']}")

    # 权限
    role_match = (user.role or "").upper()
    is_mine = (
        (task["assignee_type"] == "user" and task["assignee_id"] == str(user.user_id)) or
        (task["assignee_type"] == "role" and task["assignee_id"] == role_match)
    )
    if not is_mine:
        raise HTTPException(status_code=403, detail="Not your task")

    node = task["node_id"] or ""
    kind = node.split(":", 1)[0] if ":" in node else node
    subject_id = node.split(":", 1)[1] if ":" in node else None

    with db.get_conn() as conn:
        with conn.cursor() as cur:
            # 1) Append record
            import uuid as _uuid
            record_uuid = _uuid.uuid4()
            action_value = "approve" if payload.action == "approve" else "reject"
            cur.execute(
                """
                INSERT INTO workflow_approval_records
                    (id, instance_id, node_id, action, actor_id,
                     assignee_type, assignee_id, comment, created_at)
                VALUES (%s, %s::uuid, %s, %s, %s, %s, %s, %s, %s)
                """,
                (str(record_uuid), task["instance_hex"], node, action_value,
                 str(user.user_id), task["assignee_type"], task["assignee_id"],
                 payload.comment or "", datetime.utcnow()),
            )

            # 2) Task → completed
            cur.execute(
                """
                UPDATE workflow_approval_tasks
                SET status = 'completed',
                    claimed_by = %s,
                    completed_at = %s,
                    completion_action = %s
                WHERE id = %s
                """,
                (str(user.user_id), datetime.utcnow(), action_value, task_id),
            )

            # 3) State event
            cur.execute(
                """
                INSERT INTO workflow_state_events
                    (instance_id, node_id, event_type, from_status, to_status,
                     payload_json, occurred_at)
                VALUES (%s::uuid, %s, 'approval_action_taken', 'pending', %s, %s, %s)
                """,
                (task["instance_hex"], node,
                 "approved" if action_value == "approve" else "rejected",
                 json.dumps({
                     "actor_id": user.user_id,
                     "action": action_value,
                     "comment": payload.comment,
                 }, ensure_ascii=False),
                 datetime.utcnow()),
            )

            # 4) 业务后处理：kind = production_decision
            outsource_request_id = None
            if kind == "production_decision" and subject_id:
                project_id = int(subject_id)
                if action_value == "approve":
                    # 决策行全部 finalized
                    cur.execute(
                        """
                        UPDATE production_decisions
                        SET status = 'finalized'
                        WHERE project_id = %s
                        """,
                        (project_id,),
                    )
                    # 项目 → decided
                    cur.execute(
                        "UPDATE projects SET status = 'decided' WHERE id = %s",
                        (project_id,),
                    )

                    # 聚合 outsource 行，生成 1 张询价单草稿（阶段 3 的表可能还未建，做兼容处理）
                    cur.execute("SELECT to_regclass('public.outsource_requests') AS t")
                    reg = cur.fetchone()
                    reg_exists = reg[0] if reg else None
                    if reg_exists:
                        cur.execute(
                            """
                            SELECT COUNT(*) AS cnt
                            FROM production_decisions
                            WHERE project_id = %s AND final_decision = 'outsource'
                            """,
                            (project_id,),
                        )
                        row = cur.fetchone()
                        n_out = row["cnt"] if isinstance(row, dict) else row[0]

                        if n_out > 0:
                            # 简化：一张询价单
                            cur.execute(
                                """
                                SELECT STRING_AGG(DISTINCT d.process_name, ',' ORDER BY d.process_name) AS procs,
                                       MAX(p.quantity) AS qty,
                                       MAX(p.deadline) AS due
                                FROM production_decisions d
                                JOIN projects p ON d.project_id = p.id
                                WHERE d.project_id = %s AND d.final_decision = 'outsource'
                                """,
                                (project_id,),
                            )
                            row = cur.fetchone()
                            procs_csv = row["procs"] if isinstance(row, dict) else row[0]
                            procs = [s for s in (procs_csv or "").split(",") if s]
                            qty = (row["qty"] if isinstance(row, dict) else row[1]) or 1
                            due = (row["due"] if isinstance(row, dict) else row[2])

                            proj = db.fetch_one(
                                "SELECT project_no, name FROM projects WHERE id = %s",
                                (project_id,),
                            )
                            title = f"{proj['project_no']} - {proj['name']}" if proj else f"项目 {project_id}"

                            cur.execute(
                                """
                                INSERT INTO outsource_requests
                                    (project_id, title, required_processes_json,
                                     quantity, deadline, status)
                                VALUES (%s, %s, %s, %s, %s, 'draft')
                                RETURNING id
                                """,
                                (project_id, title,
                                 json.dumps(procs, ensure_ascii=False),
                                 qty, due),
                            )
                            outsource_request_id = cur.fetchone()[0]

                else:  # reject
                    # 决策行退回 pending_review
                    cur.execute(
                        """
                        UPDATE production_decisions
                        SET status = 'pending_review', approval_task_id = NULL
                        WHERE project_id = %s
                        """,
                        (project_id,),
                    )
                    # 项目回 deciding
                    cur.execute(
                        "UPDATE projects SET status = 'deciding' WHERE id = %s",
                        (project_id,),
                    )

    return {
        "status": "ok",
        "action": action_value,
        "outsource_request_id": outsource_request_id,
    }


# =============================================================================
# Stage 3: Outsource Requests (我方端)
# =============================================================================


class OutsourceRequestUpdate(BaseModel):
    title: Optional[str] = None
    deadline: Optional[str] = None
    quantity: Optional[int] = None


class AwardAction(BaseModel):
    """采购经理审批时的特殊载荷 — approve 时必须带 awarded_invitation_id。"""
    action: str = Field(..., pattern="^(approve|reject)$")
    comment: Optional[str] = None
    awarded_invitation_id: Optional[int] = None  # approve + 非空


def _next_order_no() -> str:
    """Generate outsource_orders.order_no."""
    return f"OO-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


# ---------------------------------------------------------------------------
# 询价单列表 / 详情
# ---------------------------------------------------------------------------

@router.get("/outsource-requests")
async def list_outsource_requests(
    user: CurrentUser = Depends(_require_internal),
    status_filter: Optional[str] = None,
):
    where = "WHERE p.tenant_id = %s"
    params: list[Any] = [user.tenant_id]
    if status_filter:
        where += " AND r.status = %s"
        params.append(status_filter)

    rows = db.fetch_all(
        f"""
        SELECT r.id, r.project_id, r.title, r.required_processes_json,
               r.quantity, r.deadline, r.status,
               r.approval_task_id, r.winning_quotation_id,
               r.created_at, r.updated_at,
               p.project_no, p.name AS project_name
        FROM outsource_requests r
        JOIN projects p ON r.project_id = p.id
        {where}
        ORDER BY r.created_at DESC
        LIMIT 50
        """,
        tuple(params),
    )
    for r in rows:
        raw = r.get("required_processes_json")
        r["required_processes"] = json.loads(raw) if isinstance(raw, str) and raw else (raw or [])
        r.pop("required_processes_json", None)
    return {"items": rows, "total": len(rows)}


@router.get("/outsource-requests/{req_id}")
async def get_outsource_request(
    req_id: int,
    user: CurrentUser = Depends(_require_internal),
):
    req = db.fetch_one(
        """
        SELECT r.*, p.project_no, p.name AS project_name, p.tenant_id
        FROM outsource_requests r
        JOIN projects p ON r.project_id = p.id
        WHERE r.id = %s
        """,
        (req_id,),
    )
    if req is None:
        raise HTTPException(status_code=404, detail="Outsource request not found")
    if req["tenant_id"] != user.tenant_id:
        raise HTTPException(status_code=403, detail="Not your project")

    raw = req.get("required_processes_json")
    req["required_processes"] = json.loads(raw) if isinstance(raw, str) and raw else (raw or [])
    req.pop("required_processes_json", None)

    # Invitations + quotations
    invs = db.fetch_all(
        """
        SELECT i.id, i.supplier_id, i.invitation_status,
               i.sent_at, i.quoted_at,
               s.name AS supplier_name, s.category AS supplier_category,
               q.id AS quotation_id, q.unit_price, q.lead_time_days, q.note,
               q.submitted_at
        FROM outsource_request_invitations i
        JOIN suppliers s ON i.supplier_id = s.id
        LEFT JOIN outsource_quotations q ON q.invitation_id = i.id
        WHERE i.request_id = %s
        ORDER BY i.id
        """,
        (req_id,),
    )
    for v in invs:
        if v.get("unit_price") is not None:
            v["unit_price"] = float(v["unit_price"])
        if v.get("sent_at"):
            v["sent_at"] = v["sent_at"].isoformat()
        if v.get("quoted_at"):
            v["quoted_at"] = v["quoted_at"].isoformat()
        if v.get("submitted_at"):
            v["submitted_at"] = v["submitted_at"].isoformat()

    # Stats
    total_inv = len(invs)
    quoted = sum(1 for v in invs if v["invitation_status"] == "quoted")

    return {
        "request": req,
        "invitations": invs,
        "stats": {
            "total_invited": total_inv,
            "quoted": quoted,
            "no_response": sum(1 for v in invs if v["invitation_status"] == "no_response"),
            "pending": total_inv - quoted - sum(1 for v in invs if v["invitation_status"] == "no_response"),
        },
    }


@router.patch("/outsource-requests/{req_id}")
async def update_outsource_request(
    req_id: int,
    payload: OutsourceRequestUpdate,
    user: CurrentUser = Depends(_require_internal),
):
    row = db.fetch_one(
        """
        SELECT r.id, r.status, p.tenant_id
        FROM outsource_requests r
        JOIN projects p ON r.project_id = p.id
        WHERE r.id = %s
        """,
        (req_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    if row["tenant_id"] != user.tenant_id:
        raise HTTPException(status_code=403)
    if row["status"] != "draft":
        raise HTTPException(status_code=409,
                            detail=f"Only draft requests can be edited; now '{row['status']}'")

    updates: list[str] = []
    params: list[Any] = []
    for f, v in payload.model_dump(exclude_unset=True).items():
        updates.append(f"{f} = %s")
        params.append(v)
    if not updates:
        return {"updated": False}
    params.append(req_id)
    db.execute(
        f"UPDATE outsource_requests SET {', '.join(updates)} WHERE id = %s",
        tuple(params),
    )
    return {"updated": True}


# ---------------------------------------------------------------------------
# 候选供应商匹配（固定算法，不用 AI）
# ---------------------------------------------------------------------------

@router.get("/outsource-requests/{req_id}/candidates")
async def list_candidates(
    req_id: int,
    user: CurrentUser = Depends(_require_internal),
):
    """返回符合工艺要求的供应商列表，按匹配工艺数降序。"""
    req = db.fetch_one(
        """
        SELECT r.id, r.required_processes_json, p.tenant_id
        FROM outsource_requests r
        JOIN projects p ON r.project_id = p.id
        WHERE r.id = %s
        """,
        (req_id,),
    )
    if req is None:
        raise HTTPException(status_code=404)
    if req["tenant_id"] != user.tenant_id:
        raise HTTPException(status_code=403)

    raw = req.get("required_processes_json")
    procs = json.loads(raw) if isinstance(raw, str) and raw else (raw or [])
    if not procs:
        return {"items": [], "total": 0, "required": []}

    placeholders = ",".join(["%s"] * len(procs))
    rows = db.fetch_all(
        f"""
        SELECT s.id, s.name, s.category, s.contact_name, s.contact_phone,
               COUNT(DISTINCT c.process_name) AS match_count,
               STRING_AGG(DISTINCT c.process_name, ',' ORDER BY c.process_name) AS matched_procs
        FROM suppliers s
        JOIN supplier_capabilities c ON c.supplier_id = s.id
        WHERE c.process_name IN ({placeholders})
        GROUP BY s.id
        ORDER BY match_count DESC, s.name ASC
        """,
        tuple(procs),
    )
    # Enrich: 是否已邀请
    invited = db.fetch_all(
        "SELECT supplier_id FROM outsource_request_invitations WHERE request_id = %s",
        (req_id,),
    )
    invited_ids = {i["supplier_id"] for i in invited}
    for r in rows:
        r["match_count"] = int(r["match_count"])
        r["matched_processes"] = (r["matched_procs"] or "").split(",") if r["matched_procs"] else []
        r.pop("matched_procs", None)
        r["already_invited"] = r["id"] in invited_ids
        r["coverage"] = f"{r['match_count']}/{len(procs)}"

    return {"items": rows, "total": len(rows), "required": procs}


# ---------------------------------------------------------------------------
# 群发询价
# ---------------------------------------------------------------------------

@router.post("/outsource-requests/{req_id}/send")
async def broadcast_invitations(
    req_id: int,
    user: CurrentUser = Depends(_require_internal),
):
    """群发给所有符合工艺的候选加工方。"""
    # Reuse candidate logic
    cand = await list_candidates(req_id, user)
    if not cand["items"]:
        raise HTTPException(status_code=400, detail="没有符合工艺要求的候选加工方")

    req = db.fetch_one(
        "SELECT status FROM outsource_requests WHERE id = %s",
        (req_id,),
    )
    if req["status"] not in ("draft",):
        raise HTTPException(status_code=409,
                            detail=f"只有 draft 状态可以群发；当前 '{req['status']}'")

    # 查 tenant 对应 supplier
    tenants_map = {
        r["supplier_id"]: r["id"]
        for r in db.fetch_all(
            "SELECT id, supplier_id FROM tenants WHERE tenant_type = 'processor' AND supplier_id IS NOT NULL",
        )
        if r["supplier_id"]
    }

    now = datetime.utcnow()
    inserted = 0
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            for c in cand["items"]:
                if c["already_invited"]:
                    continue
                cur.execute(
                    """
                    INSERT INTO outsource_request_invitations
                        (request_id, supplier_id, tenant_id, invitation_status, sent_at)
                    VALUES (%s, %s, %s, 'sent', %s)
                    """,
                    (req_id, c["id"], tenants_map.get(c["id"]), now),
                )
                inserted += 1

            cur.execute(
                "UPDATE outsource_requests SET status = 'inviting' WHERE id = %s",
                (req_id,),
            )

    return {
        "invited_count": inserted,
        "total_candidates": len(cand["items"]),
        "status": "inviting",
        "note": f"群发给 {inserted} 家能匹配工艺的加工方",
    }


# ---------------------------------------------------------------------------
# 截止报价 → 创建采购经理审批
# ---------------------------------------------------------------------------

@router.post("/outsource-requests/{req_id}/close-quoting")
async def close_quoting(
    req_id: int,
    user: CurrentUser = Depends(_require_internal),
):
    """采购员点【截止报价】→ 把所有 sent 未回复的邀请置 no_response；
    打包所有已回复报价 → 创建 1 条审批任务给采购经理 (PURCHASING_MANAGER)。
    """
    req = db.fetch_one(
        """
        SELECT r.id, r.status, r.project_id, r.title, r.quantity, r.deadline, p.tenant_id
        FROM outsource_requests r
        JOIN projects p ON r.project_id = p.id
        WHERE r.id = %s
        """,
        (req_id,),
    )
    if req is None:
        raise HTTPException(status_code=404)
    if req["tenant_id"] != user.tenant_id:
        raise HTTPException(status_code=403)
    if req["status"] != "inviting":
        raise HTTPException(status_code=409,
                            detail=f"只有 inviting 状态可以截止；当前 '{req['status']}'")

    # 需要至少 1 个报价
    quoted_count = db.fetch_one(
        """
        SELECT COUNT(*) AS cnt FROM outsource_request_invitations
        WHERE request_id = %s AND invitation_status = 'quoted'
        """,
        (req_id,),
    )
    if not quoted_count or quoted_count["cnt"] == 0:
        raise HTTPException(status_code=400, detail="还没有任何加工方回复报价，无法截止")

    with db.get_conn() as conn:
        with conn.cursor() as cur:
            # 把未回复的标 no_response
            cur.execute(
                """
                UPDATE outsource_request_invitations
                SET invitation_status = 'no_response'
                WHERE request_id = %s AND invitation_status = 'sent'
                """,
                (req_id,),
            )

            # 创建审批任务
            fake_instance_id = uuid.uuid5(
                uuid.NAMESPACE_URL, f"outsource_request:{req_id}"
            )
            node_id = f"outsource_award:{req_id}"

            # 检查是否已存在
            cur.execute(
                """
                SELECT id FROM workflow_approval_tasks
                WHERE node_id = %s AND status = 'pending'
                """,
                (node_id,),
            )
            existing = cur.fetchone()
            if existing:
                task_id = existing["id"] if isinstance(existing, dict) else existing[0]
            else:
                cur.execute(
                    """
                    INSERT INTO workflow_approval_tasks
                        (instance_id, node_id, assignee_type, assignee_id, status)
                    VALUES (%s, %s, 'role', 'PURCHASING_MANAGER', 'pending')
                    RETURNING id
                    """,
                    (str(fake_instance_id), node_id),
                )
                task_id = cur.fetchone()[0]

                # SUBMIT record
                cur.execute(
                    """
                    INSERT INTO workflow_approval_records
                        (id, instance_id, node_id, action, actor_id,
                         assignee_type, assignee_id, comment, metadata_json, created_at)
                    VALUES (%s, %s, %s, 'submit', %s, 'role', 'PURCHASING_MANAGER',
                            %s, %s, %s)
                    """,
                    (str(uuid.uuid4()), str(fake_instance_id), node_id,
                     str(user.user_id),
                     f"截止报价，请经理选择中标加工方: request_id={req_id}",
                     json.dumps({
                         "kind": "outsource_award",
                         "request_id": req_id,
                         "task_id": task_id,
                     }, ensure_ascii=False),
                     datetime.utcnow()),
                )

                # State event
                cur.execute(
                    """
                    INSERT INTO workflow_state_events
                        (instance_id, node_id, event_type, to_status, payload_json, occurred_at)
                    VALUES (%s, %s, 'approval_task_created', 'pending', %s, %s)
                    """,
                    (str(fake_instance_id), node_id,
                     json.dumps({"request_id": req_id, "task_id": task_id}, ensure_ascii=False),
                     datetime.utcnow()),
                )

            # 更新询价单状态
            cur.execute(
                """
                UPDATE outsource_requests
                SET status = 'pending_award', approval_task_id = %s, closed_at = %s
                WHERE id = %s
                """,
                (task_id, datetime.utcnow(), req_id),
            )

    return {"task_id": task_id, "status": "pending_award"}


# ---------------------------------------------------------------------------
# 重写审批处理 — 补充 outsource_award 逻辑
# 因为 act_approval 已经定义好了，所以这里用钩子方式扩展
# 实际上 act_approval 已经会路由 kind 的分支，但 outsource_award 的逻辑特殊（需要 awarded_invitation_id），
# 给它一个独立的端点。
# ---------------------------------------------------------------------------

@router.post("/approvals/{task_id}/award")
async def award_outsource(
    task_id: int,
    payload: AwardAction,
    user: CurrentUser = Depends(_require_internal),
):
    """采购经理为 outsource_award 类型任务执行审批。
    approve 时必须传 awarded_invitation_id。
    """
    task = db.fetch_one(
        """
        SELECT id, instance_id::text AS instance_hex, node_id,
               assignee_type, assignee_id, status
        FROM workflow_approval_tasks WHERE id = %s
        """,
        (task_id,),
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] != "pending":
        raise HTTPException(status_code=409, detail=f"Task already {task['status']}")

    node = task["node_id"] or ""
    if not node.startswith("outsource_award:"):
        raise HTTPException(status_code=400, detail="非 outsource_award 任务，请用 /action 接口")

    # 权限
    role_match = (user.role or "").upper()
    is_mine = (
        (task["assignee_type"] == "user" and task["assignee_id"] == str(user.user_id)) or
        (task["assignee_type"] == "role" and task["assignee_id"] == role_match)
    )
    if not is_mine:
        raise HTTPException(status_code=403, detail="Not your task")

    request_id = int(node.split(":", 1)[1])

    # approve 必须带 awarded_invitation_id
    if payload.action == "approve" and not payload.awarded_invitation_id:
        raise HTTPException(status_code=400,
                            detail="approve 时必须指定中标邀请 (awarded_invitation_id)")

    # 如果选了 awarded，校验：属于本询价单且已报价
    awarded_quote = None
    if payload.action == "approve":
        awarded_quote = db.fetch_one(
            """
            SELECT q.id AS quotation_id, q.unit_price, q.lead_time_days,
                   i.id AS invitation_id, i.supplier_id, i.tenant_id AS processor_tenant_id,
                   i.request_id,
                   r.quantity, r.deadline
            FROM outsource_request_invitations i
            JOIN outsource_quotations q ON q.invitation_id = i.id
            JOIN outsource_requests r ON i.request_id = r.id
            WHERE i.id = %s
            """,
            (payload.awarded_invitation_id,),
        )
        if not awarded_quote:
            raise HTTPException(status_code=400, detail="指定的邀请没有对应报价")
        if awarded_quote["request_id"] != request_id:
            raise HTTPException(status_code=400, detail="邀请不属于该询价单")

    now = datetime.utcnow()
    order_id = None
    order_no = None

    with db.get_conn() as conn:
        with conn.cursor() as cur:
            # 1. Append record
            action_value = payload.action
            cur.execute(
                """
                INSERT INTO workflow_approval_records
                    (id, instance_id, node_id, action, actor_id,
                     assignee_type, assignee_id, comment, metadata_json, created_at)
                VALUES (%s, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (str(uuid.uuid4()), task["instance_hex"], node, action_value,
                 str(user.user_id), task["assignee_type"], task["assignee_id"],
                 payload.comment or "",
                 json.dumps({"awarded_invitation_id": payload.awarded_invitation_id}, ensure_ascii=False),
                 now),
            )

            # 2. Task → completed
            cur.execute(
                """
                UPDATE workflow_approval_tasks
                SET status='completed', claimed_by=%s, completed_at=%s, completion_action=%s
                WHERE id=%s
                """,
                (str(user.user_id), now, action_value, task_id),
            )

            # 3. State event
            cur.execute(
                """
                INSERT INTO workflow_state_events
                    (instance_id, node_id, event_type, from_status, to_status,
                     payload_json, occurred_at)
                VALUES (%s::uuid, %s, 'approval_action_taken', 'pending', %s, %s, %s)
                """,
                (task["instance_hex"], node,
                 "approved" if action_value == "approve" else "rejected",
                 json.dumps({
                     "actor_id": user.user_id,
                     "action": action_value,
                     "awarded_invitation_id": payload.awarded_invitation_id,
                     "comment": payload.comment,
                 }, ensure_ascii=False),
                 now),
            )

            # 4. 业务后处理
            if action_value == "approve":
                # 创建 outsource_orders
                qty = awarded_quote["quantity"] or 1
                unit_price = float(awarded_quote["unit_price"])
                total = unit_price * qty
                order_no = _next_order_no()

                cur.execute(
                    """
                    INSERT INTO outsource_orders
                        (request_id, quotation_id, supplier_id, tenant_id,
                         order_no, unit_price, quantity, total_amount,
                         lead_time_days, status, awarded_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'awarded', %s)
                    RETURNING id
                    """,
                    (awarded_quote["request_id"], awarded_quote["quotation_id"],
                     awarded_quote["supplier_id"], awarded_quote["processor_tenant_id"],
                     order_no, unit_price, qty, total,
                     awarded_quote["lead_time_days"], now),
                )
                order_id = cur.fetchone()[0]

                # 加工单状态事件
                cur.execute(
                    """
                    INSERT INTO outsource_order_status_events
                        (order_id, from_status, to_status, changed_by, note, occurred_at)
                    VALUES (%s, NULL, 'awarded', %s, '采购经理批准中标', %s)
                    """,
                    (order_id, user.user_id, now),
                )

                # 询价单 → awarded
                cur.execute(
                    """
                    UPDATE outsource_requests
                    SET status='awarded', winning_quotation_id=%s
                    WHERE id=%s
                    """,
                    (awarded_quote["quotation_id"], request_id),
                )
            else:
                # reject
                cur.execute(
                    "UPDATE outsource_requests SET status='cancelled' WHERE id=%s",
                    (request_id,),
                )

    return {
        "status": "ok",
        "action": action_value,
        "outsource_order_id": order_id,
        "order_no": order_no,
    }


# ---------------------------------------------------------------------------
# 委外加工单（只读监控）
# ---------------------------------------------------------------------------

@router.get("/outsource-orders")
async def list_orders(
    user: CurrentUser = Depends(_require_internal),
    status_filter: Optional[str] = None,
):
    where = "WHERE p.tenant_id = %s"
    params: list[Any] = [user.tenant_id]
    if status_filter:
        where += " AND o.status = %s"
        params.append(status_filter)

    rows = db.fetch_all(
        f"""
        SELECT o.id, o.order_no, o.unit_price, o.quantity, o.total_amount,
               o.lead_time_days, o.status,
               o.awarded_at, o.accepted_at, o.delivered_at, o.created_at,
               s.name AS supplier_name,
               p.project_no, p.name AS project_name,
               r.title AS request_title
        FROM outsource_orders o
        JOIN outsource_requests r ON o.request_id = r.id
        JOIN projects p ON r.project_id = p.id
        JOIN suppliers s ON o.supplier_id = s.id
        {where}
        ORDER BY o.created_at DESC
        LIMIT 50
        """,
        tuple(params),
    )
    for r in rows:
        if r.get("unit_price"): r["unit_price"] = float(r["unit_price"])
        if r.get("total_amount"): r["total_amount"] = float(r["total_amount"])
        for k in ("awarded_at", "accepted_at", "delivered_at", "created_at"):
            if r.get(k):
                r[k] = r[k].isoformat() if hasattr(r[k], "isoformat") else r[k]
    return {"items": rows, "total": len(rows)}


@router.get("/outsource-orders/{order_id}")
async def get_order(
    order_id: int,
    user: CurrentUser = Depends(_require_internal),
):
    row = db.fetch_one(
        """
        SELECT o.*, s.name AS supplier_name, s.contact_name, s.contact_phone,
               p.tenant_id, p.project_no, p.name AS project_name,
               r.title AS request_title, r.required_processes_json
        FROM outsource_orders o
        JOIN outsource_requests r ON o.request_id = r.id
        JOIN projects p ON r.project_id = p.id
        JOIN suppliers s ON o.supplier_id = s.id
        WHERE o.id = %s
        """,
        (order_id,),
    )
    if row is None:
        raise HTTPException(status_code=404)
    if row["tenant_id"] != user.tenant_id:
        raise HTTPException(status_code=403)

    raw = row.get("required_processes_json")
    row["required_processes"] = json.loads(raw) if isinstance(raw, str) and raw else (raw or [])
    row.pop("required_processes_json", None)

    events = db.fetch_all(
        """
        SELECT from_status, to_status, changed_by, note, occurred_at
        FROM outsource_order_status_events
        WHERE order_id = %s ORDER BY occurred_at ASC
        """,
        (order_id,),
    )
    for e in events:
        if e.get("occurred_at"):
            e["occurred_at"] = e["occurred_at"].isoformat()

    return {"order": row, "events": events}
