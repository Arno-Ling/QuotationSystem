"""
管理后台 API — 我方 admin 专用

维护对象：
  - 加工方式字典 (process_methods)
  - 供应商 (suppliers)
  - 供应商工艺能力 (supplier_capabilities)
  - 合作租户 (tenants)
  - 用户 (users)

仅 tenant_type='internal' 可访问；更进一步只要 role='admin'。
"""
from __future__ import annotations

from typing import Any, Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from mvp import db
from mvp.auth import CurrentUser, require_tenant_type

router = APIRouter(prefix="/api/internal/admin", tags=["admin"])
_require_internal = require_tenant_type("internal")


def _require_admin(user: CurrentUser) -> None:
    if (user.role or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可访问管理后台")


# =============================================================================
# 1. 加工方式字典 process_methods
# =============================================================================

class MethodPayload(BaseModel):
    name: str = Field(..., max_length=32)
    category: str = Field(..., pattern="^(cutting|grinding|edm|heat|surface|other)$")
    is_internal_capable: bool = True
    remark: Optional[str] = None


@router.get("/process-methods")
async def list_methods(user: CurrentUser = Depends(_require_internal)):
    rows = db.fetch_all(
        "SELECT * FROM process_methods ORDER BY category, name"
    )
    return {"items": rows, "total": len(rows)}


@router.post("/process-methods", status_code=201)
async def create_method(payload: MethodPayload, user: CurrentUser = Depends(_require_internal)):
    _require_admin(user)
    try:
        new_id = db.execute(
            """
            INSERT INTO process_methods (name, category, is_internal_capable, remark)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (payload.name, payload.category, payload.is_internal_capable, payload.remark),
        )
    except Exception as e:
        if "unique" in str(e).lower() or "name_key" in str(e).lower():
            raise HTTPException(status_code=409, detail=f"加工方式 '{payload.name}' 已存在")
        raise
    return {"id": new_id}


@router.patch("/process-methods/{method_id}")
async def update_method(method_id: int, payload: MethodPayload,
                         user: CurrentUser = Depends(_require_internal)):
    _require_admin(user)
    db.execute(
        """
        UPDATE process_methods
        SET name = %s, category = %s, is_internal_capable = %s, remark = %s
        WHERE id = %s
        """,
        (payload.name, payload.category, payload.is_internal_capable,
         payload.remark, method_id),
    )
    return {"updated": True}


@router.delete("/process-methods/{method_id}")
async def delete_method(method_id: int, user: CurrentUser = Depends(_require_internal)):
    _require_admin(user)
    # 安全检查：有工序在用时禁删
    row = db.fetch_one("SELECT name FROM process_methods WHERE id=%s", (method_id,))
    if row is None:
        raise HTTPException(status_code=404)
    used = db.fetch_one(
        "SELECT COUNT(*) AS c FROM project_processes WHERE method_name=%s",
        (row["name"],),
    )
    if used and used["c"] > 0:
        raise HTTPException(status_code=409,
                            detail=f"有 {used['c']} 个工序在用该加工方式，不可删除")
    # 也检查 supplier_capabilities
    cap = db.fetch_one(
        "SELECT COUNT(*) AS c FROM supplier_capabilities WHERE process_name=%s",
        (row["name"],),
    )
    if cap and cap["c"] > 0:
        raise HTTPException(status_code=409,
                            detail=f"有 {cap['c']} 个供应商能力标签在用，请先清除")
    db.execute("DELETE FROM process_methods WHERE id=%s", (method_id,))
    return {"deleted": True}


# =============================================================================
# 2. 供应商 suppliers
# =============================================================================

class SupplierPayload(BaseModel):
    name: str = Field(..., max_length=255)
    category: Optional[str] = None
    address: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    rating: Optional[float] = Field(None, ge=0, le=5)


@router.get("/suppliers")
async def list_suppliers(user: CurrentUser = Depends(_require_internal)):
    rows = db.fetch_all(
        """
        SELECT s.*,
               (SELECT STRING_AGG(process_name, ', ' ORDER BY process_name)
                FROM supplier_capabilities c WHERE c.supplier_id = s.id) AS capabilities_csv,
               (SELECT COUNT(*) FROM supplier_capabilities c WHERE c.supplier_id = s.id) AS cap_count,
               EXISTS(SELECT 1 FROM tenants t WHERE t.supplier_id = s.id) AS is_tenant
        FROM suppliers s
        ORDER BY s.name
        """
    )
    for r in rows:
        if r.get("rating") is not None:
            r["rating"] = float(r["rating"])
    return {"items": rows, "total": len(rows)}


@router.post("/suppliers", status_code=201)
async def create_supplier(payload: SupplierPayload,
                           user: CurrentUser = Depends(_require_internal)):
    _require_admin(user)
    try:
        new_id = db.execute(
            """
            INSERT INTO suppliers (name, category, address, contact_name,
                                    contact_phone, rating)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (payload.name, payload.category, payload.address,
             payload.contact_name, payload.contact_phone, payload.rating),
        )
    except Exception as e:
        if "unique" in str(e).lower() or "name_key" in str(e).lower():
            raise HTTPException(status_code=409, detail="供应商名称已存在")
        raise
    return {"id": new_id}


@router.patch("/suppliers/{supplier_id}")
async def update_supplier(supplier_id: int, payload: SupplierPayload,
                           user: CurrentUser = Depends(_require_internal)):
    _require_admin(user)
    db.execute(
        """
        UPDATE suppliers
        SET name = %s, category = %s, address = %s,
            contact_name = %s, contact_phone = %s, rating = %s
        WHERE id = %s
        """,
        (payload.name, payload.category, payload.address,
         payload.contact_name, payload.contact_phone, payload.rating,
         supplier_id),
    )
    return {"updated": True}


@router.delete("/suppliers/{supplier_id}")
async def delete_supplier(supplier_id: int,
                           user: CurrentUser = Depends(_require_internal)):
    _require_admin(user)
    # 关联检查
    checks = [
        ("tenants",                 "supplier_id", "已有租户关联该供应商"),
        ("outsource_orders",        "supplier_id", "已有加工单关联该供应商"),
        ("material_purchase_orders","supplier_id", "已有采购单关联该供应商"),
    ]
    for tbl, col, msg in checks:
        row = db.fetch_one(f"SELECT COUNT(*) AS c FROM {tbl} WHERE {col}=%s",
                            (supplier_id,))
        if row and row["c"] > 0:
            raise HTTPException(status_code=409,
                                detail=f"{msg}（{row['c']} 条），无法删除")

    # 级联清理能力
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM supplier_capabilities WHERE supplier_id=%s",
                        (supplier_id,))
            cur.execute("DELETE FROM suppliers WHERE id=%s", (supplier_id,))
    return {"deleted": True}


# =============================================================================
# 3. 供应商工艺能力（批量编辑）
# =============================================================================

class CapabilitiesPayload(BaseModel):
    supplier_id: int
    method_names: list[str]     # 完整替换该供应商的能力


@router.put("/supplier-capabilities")
async def set_capabilities(payload: CapabilitiesPayload,
                            user: CurrentUser = Depends(_require_internal)):
    _require_admin(user)
    # 校验 supplier 存在
    sup = db.fetch_one("SELECT id FROM suppliers WHERE id=%s", (payload.supplier_id,))
    if sup is None:
        raise HTTPException(status_code=404, detail="Supplier not found")

    # 校验所有 method_names 都在 process_methods 里
    if payload.method_names:
        rows = db.fetch_all(
            "SELECT name FROM process_methods WHERE name = ANY(%s)",
            (payload.method_names,),
        )
        known = {r["name"] for r in rows}
        unknown = set(payload.method_names) - known
        if unknown:
            raise HTTPException(status_code=400,
                                detail=f"未知加工方式：{', '.join(unknown)}")

    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM supplier_capabilities WHERE supplier_id=%s",
                         (payload.supplier_id,))
            for name in payload.method_names:
                cur.execute(
                    "INSERT INTO supplier_capabilities (supplier_id, process_name) VALUES (%s, %s)",
                    (payload.supplier_id, name),
                )
    return {"count": len(payload.method_names)}


# =============================================================================
# 4. 合作租户（materials + processors 外部账号）
# =============================================================================

class TenantPayload(BaseModel):
    tenant_type: str = Field(..., pattern="^(internal|processor|material)$")
    name: str = Field(..., max_length=255)
    supplier_id: Optional[int] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None


@router.get("/tenants")
async def list_tenants(user: CurrentUser = Depends(_require_internal)):
    rows = db.fetch_all(
        """
        SELECT t.*, s.name AS supplier_name,
               (SELECT COUNT(*) FROM users u WHERE u.tenant_id = t.id) AS user_count
        FROM tenants t
        LEFT JOIN suppliers s ON t.supplier_id = s.id
        ORDER BY t.tenant_type, t.name
        """
    )
    return {"items": rows, "total": len(rows)}


@router.post("/tenants", status_code=201)
async def create_tenant(payload: TenantPayload,
                         user: CurrentUser = Depends(_require_internal)):
    _require_admin(user)
    try:
        new_id = db.execute(
            """
            INSERT INTO tenants (tenant_type, name, supplier_id,
                                 contact_name, contact_phone, contact_email)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (payload.tenant_type, payload.name, payload.supplier_id,
             payload.contact_name, payload.contact_phone, payload.contact_email),
        )
    except Exception as e:
        if "unique" in str(e).lower() or "name" in str(e).lower():
            raise HTTPException(status_code=409, detail="租户名称已存在")
        raise
    return {"id": new_id}


@router.patch("/tenants/{tenant_id}")
async def update_tenant(tenant_id: int, payload: TenantPayload,
                         user: CurrentUser = Depends(_require_internal)):
    _require_admin(user)
    db.execute(
        """
        UPDATE tenants
        SET tenant_type = %s, name = %s, supplier_id = %s,
            contact_name = %s, contact_phone = %s, contact_email = %s
        WHERE id = %s
        """,
        (payload.tenant_type, payload.name, payload.supplier_id,
         payload.contact_name, payload.contact_phone, payload.contact_email,
         tenant_id),
    )
    return {"updated": True}


@router.delete("/tenants/{tenant_id}")
async def delete_tenant(tenant_id: int,
                         user: CurrentUser = Depends(_require_internal)):
    _require_admin(user)
    # 防止自删
    if tenant_id == user.tenant_id:
        raise HTTPException(status_code=400, detail="不可删除自己所在的租户")

    row = db.fetch_one(
        "SELECT COUNT(*) AS c FROM users WHERE tenant_id=%s",
        (tenant_id,),
    )
    if row and row["c"] > 0:
        raise HTTPException(status_code=409,
                            detail=f"该租户下还有 {row['c']} 个用户，请先停用用户")
    db.execute("DELETE FROM tenants WHERE id=%s", (tenant_id,))
    return {"deleted": True}


# =============================================================================
# 5. 用户管理
# =============================================================================

class UserPayload(BaseModel):
    tenant_id: int
    username: str = Field(..., max_length=64)
    display_name: str = Field(..., max_length=64)
    role: str = "admin"
    phone: Optional[str] = None
    password: Optional[str] = None
    is_active: bool = True


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


def _hash(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


@router.get("/users")
async def list_users(user: CurrentUser = Depends(_require_internal)):
    rows = db.fetch_all(
        """
        SELECT u.id, u.tenant_id, u.username, u.display_name, u.role,
               u.phone, u.is_active, u.created_at, u.updated_at,
               t.name AS tenant_name, t.tenant_type
        FROM users u
        JOIN tenants t ON u.tenant_id = t.id
        ORDER BY t.tenant_type, u.username
        """
    )
    return {"items": rows, "total": len(rows)}


@router.post("/users", status_code=201)
async def create_user(payload: UserPayload,
                       user: CurrentUser = Depends(_require_internal)):
    _require_admin(user)
    if not payload.password:
        raise HTTPException(status_code=400, detail="新建用户必须提供 password")
    try:
        new_id = db.execute(
            """
            INSERT INTO users
                (tenant_id, username, password_hash, display_name, role, phone, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (payload.tenant_id, payload.username, _hash(payload.password),
             payload.display_name, payload.role, payload.phone, payload.is_active),
        )
    except Exception as e:
        if "username" in str(e).lower() and ("unique" in str(e).lower() or "duplicate" in str(e).lower()):
            raise HTTPException(status_code=409, detail="用户名已存在")
        raise
    return {"id": new_id}


@router.patch("/users/{user_id}")
async def update_user(user_id: int, payload: UserUpdate,
                       user: CurrentUser = Depends(_require_internal)):
    _require_admin(user)
    updates: list[str] = []
    params: list[Any] = []
    for k, v in payload.model_dump(exclude_unset=True).items():
        if k == "password":
            if v:
                updates.append("password_hash = %s")
                params.append(_hash(v))
        else:
            updates.append(f"{k} = %s")
            params.append(v)
    if not updates:
        return {"updated": False}
    params.append(user_id)
    db.execute(
        f"UPDATE users SET {', '.join(updates)} WHERE id = %s",
        tuple(params),
    )
    return {"updated": True}


@router.delete("/users/{user_id}")
async def deactivate_user(user_id: int,
                           user: CurrentUser = Depends(_require_internal)):
    """软删除：置为 is_active=FALSE"""
    _require_admin(user)
    if user_id == user.user_id:
        raise HTTPException(status_code=400, detail="不可停用自己")
    db.execute("UPDATE users SET is_active = FALSE WHERE id = %s", (user_id,))
    return {"deactivated": True}



# =============================================================================
# 6. 材料商视角（基于 material_prices 聚合）
# =============================================================================

class MaterialSupplyPayload(BaseModel):
    supplier_id: int
    material_code: str = Field(..., max_length=64)
    material_name: Optional[str] = None
    spec: Optional[str] = None
    unit: str = "kg"
    unit_price: float = Field(..., gt=0)
    valid_from: str             # YYYY-MM-DD
    valid_to: Optional[str] = None


@router.get("/material-suppliers")
async def list_material_suppliers(user: CurrentUser = Depends(_require_internal)):
    """材料商列表：有 material_prices 关联的 suppliers。

    每条包含：基础信息 + 供应的材料清单（含价格和有效期）
    """
    # 所有在 material_prices 登记过的 supplier，或者 tenant_type='material'
    rows = db.fetch_all(
        """
        SELECT s.*,
               EXISTS(SELECT 1 FROM tenants t WHERE t.supplier_id = s.id AND t.tenant_type = 'material') AS is_material_tenant,
               EXISTS(SELECT 1 FROM tenants t WHERE t.supplier_id = s.id) AS is_tenant,
               (SELECT COUNT(*) FROM material_prices mp WHERE mp.supplier_id = s.id AND mp.is_active = TRUE) AS material_count
        FROM suppliers s
        WHERE EXISTS(SELECT 1 FROM material_prices mp WHERE mp.supplier_id = s.id)
           OR EXISTS(SELECT 1 FROM tenants t WHERE t.supplier_id = s.id AND t.tenant_type = 'material')
        ORDER BY s.name
        """
    )
    for r in rows:
        if r.get("rating") is not None:
            r["rating"] = float(r["rating"])

    # 对每个 supplier 带上供应材料清单
    for r in rows:
        mats = db.fetch_all(
            """
            SELECT id, material_code, material_name, spec, unit, unit_price,
                   valid_from, valid_to, remark, is_active,
                   (valid_to IS NOT NULL AND valid_to < CURRENT_DATE) AS expired,
                   (valid_to IS NOT NULL AND valid_to - CURRENT_DATE <= 15 AND valid_to >= CURRENT_DATE) AS expiring_soon
            FROM material_prices
            WHERE supplier_id = %s AND is_active = TRUE
            ORDER BY material_code, valid_from DESC
            """,
            (r["id"],),
        )
        for m in mats:
            m["unit_price"] = float(m["unit_price"])
        r["materials"] = mats

    return {"items": rows, "total": len(rows)}


@router.post("/material-suppliers/supply", status_code=201)
async def add_material_supply(
    payload: MaterialSupplyPayload,
    user: CurrentUser = Depends(_require_internal),
):
    """给某个材料商登记一条供应材料（价格）"""
    _require_admin(user)
    # 校验 supplier 存在
    sup = db.fetch_one("SELECT id FROM suppliers WHERE id=%s", (payload.supplier_id,))
    if sup is None:
        raise HTTPException(status_code=404, detail="Supplier not found")

    try:
        new_id = db.execute(
            """
            INSERT INTO material_prices
                (material_code, material_name, spec, unit, unit_price, supplier_id,
                 valid_from, valid_to, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'manual')
            RETURNING id
            """,
            (payload.material_code, payload.material_name, payload.spec,
             payload.unit, payload.unit_price, payload.supplier_id,
             payload.valid_from, payload.valid_to),
        )
    except Exception as e:
        if "uk_mat_price_key" in str(e):
            raise HTTPException(status_code=409,
                                detail="同材料/规格/供应商/生效日期已存在")
        raise
    return {"id": new_id}


@router.delete("/material-suppliers/supply/{price_id}")
async def delete_material_supply(
    price_id: int,
    user: CurrentUser = Depends(_require_internal),
):
    """删除某条供应材料（软删：is_active=FALSE）"""
    _require_admin(user)
    db.execute("UPDATE material_prices SET is_active = FALSE WHERE id = %s", (price_id,))
    return {"deactivated": True}
