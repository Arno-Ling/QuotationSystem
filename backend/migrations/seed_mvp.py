"""
Seed MVP test data: 3 tenants, 5 users, 11 suppliers, supplier_capabilities.

Idempotent: re-running updates existing rows by unique keys (username / tenant name).

Usage:
    python backend/migrations/seed_mvp.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import bcrypt
import pymysql
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


def hash_password(plain: str) -> str:
    """Bcrypt hash password. Returns utf-8 string for DB storage."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# -----------------------------------------------------------------------------
# Seed data
# -----------------------------------------------------------------------------

SUPPLIERS = [
    # (name, category, address, contact, phone)
    ("青岛和兴嘉业金属制品有限公司", "模架",      "青岛市城阳区棘洪滩街道荣海三路58号", "尹总", "13210828919"),
    ("苏州元茂精密机械有限公司",     "全加工零件", "江苏省苏州市吴江区益堂路与龙桥路交叉口正东方向171米", "梁总", "18626261708"),
    ("青岛铂锐迪精密机械有限公司",   "全加工零件", "山东省青岛市即墨区东山前路与富山路交叉口正北方向212米", "车总", "15253227660"),
    ("昆山宸壮精密模具有限公司",     "全加工零件", "江苏省苏州市昆山市周市镇宋家港路388号7号厂房", "蒲总", "15850325668"),
    ("城阳区睿德华模具加工厂",       "快丝/小磨床", "城阳区靖城路", "白总", "15275256600"),
    ("青岛金源汇精密模具有限公司",   "慢丝",       "青岛东旭包装有限公司山东省青岛市即墨区通济街道圈子村", "陈总", "18953281706"),
    ("青岛铭微德精密机械有限公司",   "沙迪克慢丝", "山东省青岛市城阳区百福路185号", "刘总", "13325000740"),
    ("宁波市百德模具有限公司",       "全加工零件", "慈溪市周巷镇周东三角站南300米", "刘总", "13515746239"),
    ("昆山市卓诚辉电子科技有限公司", "全加工零件", "江苏省苏州市昆山市太湖北路998号", "陈总", "13879304042"),
    ("青岛颖泰和精密机械有限公司",   "钣金",       "山东省青岛市即墨区龙山办事处后北葛工业园204国道旁", "陈总", "18265328979"),
    ("青岛华欣泽机械模具有限公司",   "快丝/中丝/慢丝", "山东省青岛市即墨区淮涉河三路312号南60米", "金总", "13792460522"),
]

# 选 2 家作为 MVP 的加工方租户（有对应用户账号可登录）
PROCESSOR_TENANTS = [
    ("青岛华欣泽机械模具有限公司", "金总", "13792460522"),      # 快丝/中丝/慢丝/线割/热处理/表面处理
    ("苏州元茂精密机械有限公司",   "梁总", "18626261708"),      # 全加工零件/磨/铣/车
]

# 用户账号（密码统一 test123）
USERS = [
    # (tenant_name, username, display_name, role)
    ("我方-模具制造厂", "alice",    "Alice（管理员/采购）",     "admin"),
    ("我方-模具制造厂", "bob",      "Bob（生产经理）",          "production_manager"),
    ("我方-模具制造厂", "carol",    "Carol（采购经理）",        "purchasing_manager"),
    ("青岛华欣泽机械模具有限公司", "huaxinze", "华欣泽-金总", "operator"),
    ("苏州元茂精密机械有限公司",   "yuanmao",  "元茂-梁总",   "operator"),
]

# 供应商工艺能力标签（stage 1）
SUPPLIER_CAPS = {
    "青岛和兴嘉业金属制品有限公司": ["模架"],
    "苏州元茂精密机械有限公司":     ["全加工零件", "磨", "铣", "车"],
    "青岛铂锐迪精密机械有限公司":   ["全加工零件", "磨", "铣", "车"],
    "昆山宸壮精密模具有限公司":     ["全加工零件", "磨", "铣", "车"],
    "城阳区睿德华模具加工厂":       ["快丝", "小磨床", "磨"],
    "青岛金源汇精密模具有限公司":   ["慢丝", "线割"],
    "青岛铭微德精密机械有限公司":   ["慢丝", "线割"],
    "宁波市百德模具有限公司":       ["全加工零件", "磨", "铣", "车"],
    "昆山市卓诚辉电子科技有限公司": ["全加工零件"],
    "青岛颖泰和精密机械有限公司":   ["钣金"],
    "青岛华欣泽机械模具有限公司":   ["快丝", "中丝", "慢丝", "线割", "热处理", "表面处理"],
}


def _db_conn():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "mold_procurement"),
        charset="utf8mb4",
    )


def ensure_suppliers_table(cur):
    cur.execute("SHOW TABLES LIKE 'suppliers'")
    if cur.fetchone():
        return
    cur.execute(
        """
        CREATE TABLE suppliers (
            id           INT AUTO_INCREMENT PRIMARY KEY,
            name         VARCHAR(255) NOT NULL UNIQUE,
            category     VARCHAR(128),
            address      VARCHAR(512),
            contact_name VARCHAR(64),
            contact_phone VARCHAR(32),
            rating       DECIMAL(4,2),
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
          COMMENT='供应商主档'
        """
    )


def seed_suppliers(cur) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for name, cat, addr, contact, phone in SUPPLIERS:
        cur.execute(
            """
            INSERT INTO suppliers (name, category, address, contact_name, contact_phone)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                category      = VALUES(category),
                address       = VALUES(address),
                contact_name  = VALUES(contact_name),
                contact_phone = VALUES(contact_phone)
            """,
            (name, cat, addr, contact, phone),
        )
        cur.execute("SELECT id FROM suppliers WHERE name = %s", (name,))
        mapping[name] = cur.fetchone()[0]
    return mapping


def seed_tenants(cur, supplier_map: dict[str, int]) -> dict[str, int]:
    mapping: dict[str, int] = {}

    # 1) 我方
    internal_name = "我方-模具制造厂"
    cur.execute(
        """
        INSERT INTO tenants (tenant_type, name, contact_name, contact_phone)
        VALUES ('internal', %s, 'Alice', '13800000001')
        ON DUPLICATE KEY UPDATE
            contact_name = VALUES(contact_name),
            contact_phone = VALUES(contact_phone)
        """,
        (internal_name,),
    )
    cur.execute("SELECT id FROM tenants WHERE name = %s LIMIT 1", (internal_name,))
    mapping[internal_name] = cur.fetchone()[0]

    # 2) 加工方
    for name, contact, phone in PROCESSOR_TENANTS:
        supplier_id = supplier_map.get(name)
        cur.execute(
            """
            INSERT INTO tenants (tenant_type, name, supplier_id, contact_name, contact_phone)
            VALUES ('processor', %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                supplier_id   = VALUES(supplier_id),
                contact_name  = VALUES(contact_name),
                contact_phone = VALUES(contact_phone)
            """,
            (name, supplier_id, contact, phone),
        )
        cur.execute("SELECT id FROM tenants WHERE name = %s LIMIT 1", (name,))
        mapping[name] = cur.fetchone()[0]

    return mapping


def seed_users(cur, tenant_map: dict[str, int]) -> list[tuple[str, str]]:
    pwd_hash = hash_password("test123")
    summary: list[tuple[str, str]] = []
    for tenant_name, username, display_name, role in USERS:
        tenant_id = tenant_map.get(tenant_name)
        if not tenant_id:
            print(f"  [WARN] tenant {tenant_name} not found, skipping user {username}")
            continue
        cur.execute(
            """
            INSERT INTO users (tenant_id, username, password_hash, display_name, role, is_active)
            VALUES (%s, %s, %s, %s, %s, 1)
            ON DUPLICATE KEY UPDATE
                tenant_id     = VALUES(tenant_id),
                password_hash = VALUES(password_hash),
                display_name  = VALUES(display_name),
                role          = VALUES(role),
                is_active     = 1
            """,
            (tenant_id, username, pwd_hash, display_name, role),
        )
        summary.append((username, display_name))
    return summary


def seed_supplier_capabilities(cur, supplier_map: dict[str, int]) -> int:
    """Insert supplier capability tags. Returns total rows attempted (IGNORE duplicates)."""
    cur.execute("SHOW TABLES LIKE 'supplier_capabilities'")
    if not cur.fetchone():
        print("  [SKIP] supplier_capabilities table not found; run migration 005 first")
        return 0

    count = 0
    for supplier_name, processes in SUPPLIER_CAPS.items():
        sid = supplier_map.get(supplier_name)
        if not sid:
            continue
        for proc in processes:
            cur.execute(
                """
                INSERT IGNORE INTO supplier_capabilities (supplier_id, process_name)
                VALUES (%s, %s)
                """,
                (sid, proc),
            )
            count += 1
    return count


def main() -> int:
    print("=" * 70)
    print("Seeding MVP test data")
    print("=" * 70)

    conn = _db_conn()
    try:
        with conn.cursor() as cur:
            print("\n[1/4] Suppliers...")
            ensure_suppliers_table(cur)
            supplier_map = seed_suppliers(cur)
            print(f"  -> {len(supplier_map)} suppliers")

            print("\n[2/4] Tenants...")
            tenant_map = seed_tenants(cur, supplier_map)
            for name, tid in tenant_map.items():
                print(f"  tenant_id={tid:<4}  {name}")

            print("\n[3/4] Users (all password = test123)...")
            users = seed_users(cur, tenant_map)
            for username, display_name in users:
                print(f"  username={username:<12}  {display_name}")

            print("\n[4/4] Supplier capabilities (stage 1)...")
            n = seed_supplier_capabilities(cur, supplier_map)
            print(f"  -> attempted {n} capability rows (duplicates ignored)")

            conn.commit()
    finally:
        conn.close()

    print("\n" + "=" * 70)
    print("[OK] Seed complete. Login credentials:")
    print("=" * 70)
    print("  我方:   alice / bob / carol  →  密码 test123")
    print("  加工方: huaxinze / yuanmao    →  密码 test123")
    print()
    print("  bob  = 生产经理（阶段 1 审批生产决策）")
    print("  carol= 采购经理（阶段 3 审批报价选中标）")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
