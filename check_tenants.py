import os, pymysql
from dotenv import load_dotenv
load_dotenv('backend/.env')
c = pymysql.connect(host=os.getenv('DB_HOST'), user=os.getenv('DB_USER'),
                    password=os.getenv('DB_PASSWORD'), database=os.getenv('DB_NAME'),
                    cursorclass=pymysql.cursors.DictCursor)
cur = c.cursor()
cur.execute("""
  SELECT t.id AS tenant_id, t.name, t.tenant_type, t.supplier_id,
         s.id AS sid, s.name AS supplier_name
  FROM tenants t
  LEFT JOIN suppliers s ON t.supplier_id = s.id
""")
for r in cur.fetchall():
    print(f"  tenant#{r['tenant_id']:<3} {r['tenant_type']:<10} {r['name'][:35]:<40} → supplier#{r['supplier_id']}")

print()
cur.execute("SELECT id, name FROM suppliers WHERE name LIKE %s OR name LIKE %s", ('%华欣泽%', '%元茂%'))
for r in cur.fetchall():
    print(f"  supplier#{r['id']:<3} {r['name']}")

print()
cur.execute("""
  SELECT inv.id, inv.request_id, inv.supplier_id, inv.tenant_id, inv.invitation_status
  FROM outsource_request_invitations inv
  ORDER BY inv.id DESC LIMIT 10
""")
print("Latest invitations:")
for r in cur.fetchall():
    print(f"  inv#{r['id']} req={r['request_id']} sid={r['supplier_id']} tid={r['tenant_id']} status={r['invitation_status']}")
