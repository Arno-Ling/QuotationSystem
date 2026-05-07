import os, pymysql
from dotenv import load_dotenv
load_dotenv('backend/.env')
c = pymysql.connect(host=os.getenv('DB_HOST'), user=os.getenv('DB_USER'),
                    password=os.getenv('DB_PASSWORD'), database=os.getenv('DB_NAME'),
                    cursorclass=pymysql.cursors.DictCursor)
cur = c.cursor()
cur.execute("""
  SELECT u.id, u.username, u.tenant_id, t.name AS tenant_name, t.tenant_type, t.supplier_id
  FROM users u LEFT JOIN tenants t ON u.tenant_id = t.id
  ORDER BY u.id
""")
for r in cur.fetchall():
    print(f"  user#{r['id']} {r['username']:<10} tenant#{r['tenant_id']} {r['tenant_name'][:30]:<35} type={r['tenant_type']} sid={r['supplier_id']}")
