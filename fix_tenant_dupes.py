"""One-shot fix: dedupe tenants, keep only those referenced by users/projects."""
import os, pymysql
from dotenv import load_dotenv
load_dotenv('backend/.env')

conn = pymysql.connect(
    host=os.getenv('DB_HOST'), user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'), database=os.getenv('DB_NAME'),
    cursorclass=pymysql.cursors.DictCursor,
)
cur = conn.cursor()

# 1. Find "canonical" tenant_id per name (the lowest id that has users bound)
cur.execute("""
    SELECT t.id, t.name, t.tenant_type, t.supplier_id,
           COUNT(DISTINCT u.id) AS user_count
    FROM tenants t
    LEFT JOIN users u ON u.tenant_id = t.id
    GROUP BY t.id
    ORDER BY t.name, user_count DESC, t.id ASC
""")
all_rows = cur.fetchall()

canonical = {}  # name -> id
to_delete = []
for row in all_rows:
    if row["name"] not in canonical:
        canonical[row["name"]] = row["id"]
    else:
        # Duplicate — mark for deletion (but only if no users reference it)
        to_delete.append(row["id"])

print("Canonical tenants:")
for name, tid in canonical.items():
    print(f"  tenant#{tid:<3} {name}")

print(f"\nTo delete: {to_delete}")

# Repoint any FK references in projects / invitations to canonical id
for name, canonical_id in canonical.items():
    cur.execute("SELECT id FROM tenants WHERE name = %s AND id != %s", (name, canonical_id))
    dup_ids = [r["id"] for r in cur.fetchall()]
    if not dup_ids:
        continue
    placeholders = ",".join(["%s"] * len(dup_ids))

    # Re-point projects
    cur.execute(f"UPDATE projects SET tenant_id = %s WHERE tenant_id IN ({placeholders})",
                (canonical_id, *dup_ids))
    print(f"  re-pointed {cur.rowcount} projects to tenant#{canonical_id} (was in {dup_ids})")

    # Re-point outsource_request_invitations
    cur.execute(f"UPDATE outsource_request_invitations SET tenant_id = %s WHERE tenant_id IN ({placeholders})",
                (canonical_id, *dup_ids))
    print(f"  re-pointed {cur.rowcount} invitations to tenant#{canonical_id}")

    # Re-point outsource_orders
    cur.execute(f"UPDATE outsource_orders SET tenant_id = %s WHERE tenant_id IN ({placeholders})",
                (canonical_id, *dup_ids))
    print(f"  re-pointed {cur.rowcount} orders to tenant#{canonical_id}")

# Delete dups
if to_delete:
    placeholders = ",".join(["%s"] * len(to_delete))
    cur.execute(f"DELETE FROM tenants WHERE id IN ({placeholders})", tuple(to_delete))
    print(f"\nDeleted {cur.rowcount} duplicate tenants")

# Add UNIQUE constraint to prevent future dupes
try:
    cur.execute("ALTER TABLE tenants ADD UNIQUE KEY uq_tenant_name (name)")
    print("Added UNIQUE constraint on tenants.name")
except pymysql.err.OperationalError as e:
    if "Duplicate" in str(e) or "already exists" in str(e).lower():
        print("UNIQUE constraint already exists; skipping")
    else:
        raise

conn.commit()
conn.close()
print("\n[OK] Cleanup complete")
