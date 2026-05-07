"""
Stage 2-BASIS — 基础数据库 CRUD API（我方视角）

覆盖 5 张表 + 1 个过期提醒入口：
  - /material-prices       原料价格
  - /process-costs         工艺参考价
  - /equipment-capacity    设备产能
  - /moq-rules             MOQ 规则
  - /inventory             库存（正常 + MOQ 余量）
  - /alerts                15 天内过期的价格 + 低库存

设计原则：
  - 仅 internal 租户可访问
  - 全部使用 %s + RETURNING id（PG）
  - 简单分页 page / page_size；无搜索参数时全部
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from mvp import db
from mvp.auth import CurrentUser, require_tenant_type

router = APIRouter(prefix="/api/internal/basis", tags=["basis"])
_require_internal = require_tenant_type("internal")


# =============================================================================
# 1. material_prices
# =============================================================================

class MatPriceCreate(BaseModel):
    material_code: str = Field(..., max_length=64)
    material_name: str = Field(..., max_length=128)
    spec: Optional[str] = None
    unit: str = "kg"
    unit_price: float = Field(..., gt=0)
    supplier_id: Optional[int] = None
    valid_from: str                                # YYYY-MM-DD
    valid_to: Optional[str] = None
    source: str = "manual"
    remark: Optional[str] = None


class MatPriceUpdate(BaseModel):
    unit_price: Optional[float] = None
    valid_to: Optional[str] = None
    remark: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/material-prices")
async def list_mat_prices(
    q: Optional[str] = None,
    only_active: bool = True,
    user: CurrentUser = Depends(_require_internal),
):
    where = ["1=1"]
    params: list[Any] = []
    if only_active:
        where.append("mp.is_active = TRUE")
    if q:
        where.append("(mp.material_code ILIKE %s OR mp.material_name ILIKE %s OR mp.spec ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])

    rows = db.fetch_all(
        f"""
        SELECT mp.*, s.name AS supplier_name,
               (mp.valid_to IS NOT NULL
                 AND mp.valid_to - CURRENT_DATE <= 15
                 AND mp.valid_to >= CURRENT_DATE) AS expiring_soon,
               (mp.valid_to IS NOT NULL AND mp.valid_to < CURRENT_DATE) AS expired
        FROM material_prices mp
        LEFT JOIN suppliers s ON s.id = mp.supplier_id
        WHERE {' AND '.join(where)}
        ORDER BY mp.material_code, mp.valid_from DESC
        """,
        tuple(params),
    )
    for r in rows:
        r["unit_price"] = float(r["unit_price"])
    return {"items": rows, "total": len(rows)}


@router.post("/material-prices", status_code=201)
async def create_mat_price(payload: MatPriceCreate, user: CurrentUser = Depends(_require_internal)):
    try:
        new_id = db.execute(
            """
            INSERT INTO material_prices
                (material_code, material_name, spec, unit, unit_price, supplier_id,
                 valid_from, valid_to, source, remark)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (payload.material_code, payload.material_name, payload.spec, payload.unit,
             payload.unit_price, payload.supplier_id,
             payload.valid_from, payload.valid_to, payload.source, payload.remark),
        )
    except Exception as e:
        if "uk_mat_price_key" in str(e):
            raise HTTPException(status_code=409, detail="同一材料/规格/供应商/生效日期已存在")
        raise
    return {"id": new_id}


@router.patch("/material-prices/{price_id}")
async def update_mat_price(price_id: int, payload: MatPriceUpdate,
                            user: CurrentUser = Depends(_require_internal)):
    updates: list[str] = []
    params: list[Any] = []
    for k, v in payload.model_dump(exclude_unset=True).items():
        updates.append(f"{k} = %s")
        params.append(v)
    if not updates:
        return {"updated": False}
    params.append(price_id)
    db.execute(
        f"UPDATE material_prices SET {', '.join(updates)} WHERE id = %s",
        tuple(params),
    )
    return {"updated": True}


@router.delete("/material-prices/{price_id}")
async def delete_mat_price(price_id: int, user: CurrentUser = Depends(_require_internal)):
    """软删除：is_active = FALSE"""
    db.execute("UPDATE material_prices SET is_active = FALSE WHERE id = %s", (price_id,))
    return {"deactivated": True}


# =============================================================================
# 2. process_costs
# =============================================================================

class ProcCostCreate(BaseModel):
    method_name: str
    supplier_id: Optional[int] = None
    cost_type: str = "per_hour"        # per_hour / per_piece / per_face
    unit_cost: float = Field(..., gt=0)
    est_time_hours: Optional[float] = None
    valid_from: str
    valid_to: Optional[str] = None
    notes: Optional[str] = None


@router.get("/process-costs")
async def list_process_costs(
    q: Optional[str] = None,
    only_active: bool = True,
    user: CurrentUser = Depends(_require_internal),
):
    where = ["1=1"]
    params: list[Any] = []
    if only_active:
        where.append("pc.is_active = TRUE")
    if q:
        where.append("pc.method_name ILIKE %s")
        params.append(f"%{q}%")

    rows = db.fetch_all(
        f"""
        SELECT pc.*, s.name AS supplier_name, pm.category
        FROM process_costs pc
        LEFT JOIN suppliers s ON s.id = pc.supplier_id
        LEFT JOIN process_methods pm ON pm.name = pc.method_name
        WHERE {' AND '.join(where)}
        ORDER BY pm.category, pc.method_name, pc.valid_from DESC
        """,
        tuple(params),
    )
    for r in rows:
        r["unit_cost"] = float(r["unit_cost"])
        if r.get("est_time_hours") is not None:
            r["est_time_hours"] = float(r["est_time_hours"])
    return {"items": rows, "total": len(rows)}


@router.post("/process-costs", status_code=201)
async def create_process_cost(payload: ProcCostCreate, user: CurrentUser = Depends(_require_internal)):
    try:
        new_id = db.execute(
            """
            INSERT INTO process_costs
                (method_name, supplier_id, cost_type, unit_cost, est_time_hours,
                 valid_from, valid_to, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (payload.method_name, payload.supplier_id, payload.cost_type,
             payload.unit_cost, payload.est_time_hours,
             payload.valid_from, payload.valid_to, payload.notes),
        )
    except Exception as e:
        if "uk_pcost_method_sup" in str(e):
            raise HTTPException(status_code=409, detail="同一方法/供应商/类型/生效日期已存在")
        if "fk" in str(e).lower() and "method_name" in str(e):
            raise HTTPException(status_code=400, detail=f"未知加工方式：{payload.method_name}")
        raise
    return {"id": new_id}


@router.delete("/process-costs/{pcost_id}")
async def delete_process_cost(pcost_id: int, user: CurrentUser = Depends(_require_internal)):
    db.execute("UPDATE process_costs SET is_active = FALSE WHERE id = %s", (pcost_id,))
    return {"deactivated": True}


# =============================================================================
# 3. equipment_capacity
# =============================================================================

class EquipmentCreate(BaseModel):
    equipment_code: str
    equipment_name: str
    method_name: str
    max_workpiece_dim: Optional[str] = None
    precision_grade: Optional[str] = None
    daily_hours: float = 16.0
    notes: Optional[str] = None


@router.get("/equipment-capacity")
async def list_equipment(user: CurrentUser = Depends(_require_internal)):
    rows = db.fetch_all(
        """
        SELECT ec.*, pm.category
        FROM equipment_capacity ec
        LEFT JOIN process_methods pm ON pm.name = ec.method_name
        WHERE ec.is_available = TRUE
        ORDER BY pm.category, ec.equipment_code
        """
    )
    for r in rows:
        r["daily_hours"]    = float(r["daily_hours"])
        r["occupied_hours"] = float(r["occupied_hours"])
        r["load_ratio"] = (r["occupied_hours"] / r["daily_hours"]) if r["daily_hours"] else 0
    return {"items": rows, "total": len(rows)}


@router.post("/equipment-capacity", status_code=201)
async def create_equipment(payload: EquipmentCreate, user: CurrentUser = Depends(_require_internal)):
    try:
        new_id = db.execute(
            """
            INSERT INTO equipment_capacity
                (equipment_code, equipment_name, method_name, max_workpiece_dim,
                 precision_grade, daily_hours, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (payload.equipment_code, payload.equipment_name, payload.method_name,
             payload.max_workpiece_dim, payload.precision_grade,
             payload.daily_hours, payload.notes),
        )
    except Exception as e:
        if "equipment_code" in str(e) and "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="设备编号已存在")
        raise
    return {"id": new_id}


@router.delete("/equipment-capacity/{eq_id}")
async def deactivate_equipment(eq_id: int, user: CurrentUser = Depends(_require_internal)):
    db.execute("UPDATE equipment_capacity SET is_available = FALSE WHERE id = %s", (eq_id,))
    return {"deactivated": True}


# =============================================================================
# 4. moq_rules
# =============================================================================

class MoqCreate(BaseModel):
    material_code: str
    spec: Optional[str] = None
    supplier_id: Optional[int] = None
    min_qty: int = Field(..., ge=1)
    multiple_of: int = 1
    unit: str = "kg"
    surplus_policy: str = "stock"    # stock / return / waste
    notes: Optional[str] = None


@router.get("/moq-rules")
async def list_moq(user: CurrentUser = Depends(_require_internal)):
    rows = db.fetch_all(
        """
        SELECT mq.*, s.name AS supplier_name
        FROM moq_rules mq
        LEFT JOIN suppliers s ON s.id = mq.supplier_id
        WHERE mq.is_active = TRUE
        ORDER BY mq.material_code
        """
    )
    return {"items": rows, "total": len(rows)}


@router.post("/moq-rules", status_code=201)
async def create_moq(payload: MoqCreate, user: CurrentUser = Depends(_require_internal)):
    new_id = db.execute(
        """
        INSERT INTO moq_rules
            (material_code, spec, supplier_id, min_qty, multiple_of, unit,
             surplus_policy, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (payload.material_code, payload.spec, payload.supplier_id,
         payload.min_qty, payload.multiple_of, payload.unit,
         payload.surplus_policy, payload.notes),
    )
    return {"id": new_id}


@router.delete("/moq-rules/{mq_id}")
async def deactivate_moq(mq_id: int, user: CurrentUser = Depends(_require_internal)):
    db.execute("UPDATE moq_rules SET is_active = FALSE WHERE id = %s", (mq_id,))
    return {"deactivated": True}


# =============================================================================
# 5. inventory
# =============================================================================

class InventoryCreate(BaseModel):
    material_code: str
    spec: Optional[str] = None
    batch_no: Optional[str] = None
    qty: float = Field(..., gt=0)
    unit: str = "kg"
    inventory_type: str = "normal"        # normal / moq_surplus / rework_return
    warehouse_location: Optional[str] = None
    remark: Optional[str] = None


@router.get("/inventory")
async def list_inventory(
    inventory_type: Optional[str] = None,
    available_only: bool = True,
    user: CurrentUser = Depends(_require_internal),
):
    where = ["1=1"]
    params: list[Any] = []
    if available_only:
        where.append("status = 'available'")
    if inventory_type:
        where.append("inventory_type = %s")
        params.append(inventory_type)

    rows = db.fetch_all(
        f"""
        SELECT * FROM inventory
        WHERE {' AND '.join(where)}
        ORDER BY material_code, created_at DESC
        """,
        tuple(params),
    )
    for r in rows:
        r["qty"] = float(r["qty"])
    return {"items": rows, "total": len(rows)}


@router.post("/inventory", status_code=201)
async def create_inventory(payload: InventoryCreate, user: CurrentUser = Depends(_require_internal)):
    new_id = db.execute(
        """
        INSERT INTO inventory
            (material_code, spec, batch_no, qty, unit, inventory_type,
             warehouse_location, remark)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (payload.material_code, payload.spec, payload.batch_no, payload.qty,
         payload.unit, payload.inventory_type,
         payload.warehouse_location, payload.remark),
    )
    return {"id": new_id}


# =============================================================================
# 6. alerts —— 15 天内过期的价格 + 已过期价格 + 余量可用
# =============================================================================

@router.get("/alerts")
async def list_alerts(user: CurrentUser = Depends(_require_internal)):
    expiring = db.fetch_all(
        """
        SELECT id, material_code, material_name, spec, valid_to,
               valid_to - CURRENT_DATE AS days_left
        FROM material_prices
        WHERE is_active = TRUE
          AND valid_to IS NOT NULL
          AND valid_to BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '15 days'
        ORDER BY valid_to
        """
    )
    expired = db.fetch_all(
        """
        SELECT id, material_code, material_name, spec, valid_to
        FROM material_prices
        WHERE is_active = TRUE
          AND valid_to IS NOT NULL
          AND valid_to < CURRENT_DATE
        ORDER BY valid_to DESC
        LIMIT 20
        """
    )
    moq_surplus = db.fetch_all(
        """
        SELECT id, material_code, spec, batch_no, qty, unit, warehouse_location
        FROM inventory
        WHERE inventory_type = 'moq_surplus' AND status = 'available'
        ORDER BY material_code
        """
    )
    for r in moq_surplus:
        r["qty"] = float(r["qty"])

    return {
        "expiring_soon": expiring,
        "expired":       expired,
        "moq_surplus":   moq_surplus,
        "summary": {
            "expiring_soon_count": len(expiring),
            "expired_count":       len(expired),
            "moq_surplus_count":   len(moq_surplus),
        },
    }
