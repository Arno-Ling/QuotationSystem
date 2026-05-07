"""Stage 3 end-to-end smoke test: outsource full loop."""
import io
import sys
# Force UTF-8 stdout (Windows cmd defaults to cp936 / GBK)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True)

import requests

BASE = "http://localhost:8001"


def login(username, pw="test123"):
    r = requests.post(f"{BASE}/api/auth/login", json={"username": username, "password": pw})
    r.raise_for_status()
    d = r.json()
    return d["access_token"], d.get("role"), d.get("tenant_type"), d.get("display_name")


def H(t): return {"Authorization": f"Bearer {t}"}


# ---------------------------------------------------------------------------
# Setup: start from an already-decided project (create fresh one)
# ---------------------------------------------------------------------------

print("[SETUP] Log in and create a project")
alice_tok, _, _, _ = login("alice")
bob_tok, _, _, _ = login("bob")
carol_tok, _, _, _ = login("carol")
huaxinze_tok, _, _, _ = login("huaxinze")
yuanmao_tok, _, _, _ = login("yuanmao")
print(f"  [OK] logged in 5 users")

r = requests.post(f"{BASE}/api/internal/projects", headers=H(alice_tok), json={
    "name": "Stage 3 测试模具",
    "customer": "测试客户",
    "deadline": "2026-07-30",
    "unit_price": 12000,
    "quantity": 20,
})
project_id = r.json()["id"]
print(f"  [OK] created project #{project_id}")

for part in [
    {"part_no": "X-01", "part_name": "外壳", "material": "45#钢", "qty": 1,
     "processes": ["磨", "热处理"], "spec": "100x100x50"},
    {"part_no": "X-02", "part_name": "轴", "material": "Cr12MoV", "qty": 2,
     "processes": ["车", "线割", "表面处理"], "spec": "D20x100"},
]:
    r = requests.post(f"{BASE}/api/internal/projects/{project_id}/parts", headers=H(alice_tok), json=part)
    r.raise_for_status()
print(f"  [OK] added 2 parts (5 道工序, 3 道需委外)")

# Upload fake drawing
from pathlib import Path
fd = Path("_fake.txt")
fd.write_text("fake")
with fd.open("rb") as f:
    requests.post(
        f"{BASE}/api/internal/projects/{project_id}/attachments",
        headers=H(alice_tok),
        files={"file": ("drawing.pdf", f, "application/pdf")},
        data={"category": "drawing"},
    )
fd.unlink(missing_ok=True)

# Confirm + decide + submit + bob approve
requests.post(f"{BASE}/api/internal/projects/{project_id}/confirm", headers=H(alice_tok))
requests.post(f"{BASE}/api/internal/projects/{project_id}/decide", headers=H(alice_tok))
r = requests.post(f"{BASE}/api/internal/projects/{project_id}/decisions/submit", headers=H(alice_tok))
dec_task = r.json()["task_id"]
r = requests.post(
    f"{BASE}/api/internal/approvals/{dec_task}/action",
    headers=H(bob_tok),
    json={"action": "approve", "comment": "方案可行"},
)
req_id = r.json().get("outsource_request_id")
assert req_id, f"Expected outsource_request_id, got {r.json()}"
print(f"  [OK] bob approved decisions → outsource_request #{req_id}")

# ---------------------------------------------------------------------------
# Stage 3 main flow
# ---------------------------------------------------------------------------

print(f"\n[STAGE 3] Test outsource flow for request #{req_id}")

# 1. List candidates
r = requests.get(
    f"{BASE}/api/internal/outsource-requests/{req_id}/candidates",
    headers=H(alice_tok),
)
r.raise_for_status()
cand = r.json()
print(f"  [OK] candidates: {cand['total']} suppliers match {cand['required']}")
for c in cand["items"][:5]:
    print(f"       #{c['id']} {c['name']} — {c['coverage']} ({c['matched_processes']})")

# 2. Broadcast
r = requests.post(
    f"{BASE}/api/internal/outsource-requests/{req_id}/send",
    headers=H(alice_tok),
)
r.raise_for_status()
print(f"  [OK] broadcast: {r.json()}")

# 3. Huaxinze logs in, checks his invitations
r = requests.get(f"{BASE}/api/processor/invitations", headers=H(huaxinze_tok))
r.raise_for_status()
invs_h = r.json()["items"]
print(f"  [OK] huaxinze sees {len(invs_h)} invitation(s)")

# 4. Yuanmao logs in, checks
r = requests.get(f"{BASE}/api/processor/invitations", headers=H(yuanmao_tok))
invs_y = r.json()["items"]
print(f"  [OK] yuanmao sees {len(invs_y)} invitation(s)")

# 5. Each submits a quote
for user_tok, invs, price, lead, note in [
    (huaxinze_tok, invs_h, 5000, 15, "工艺齐全，可含热处理"),
    (yuanmao_tok,  invs_y, 4800, 20, "价格优惠，但工期稍长"),
]:
    # find the invitation for our req
    target = next((i for i in invs if i["request_id"] == req_id), None)
    if not target:
        print(f"  [WARN] user has no invitation for request #{req_id}")
        continue
    r = requests.post(
        f"{BASE}/api/processor/invitations/{target['id']}/quote",
        headers=H(user_tok),
        json={"unit_price": price, "lead_time_days": lead, "note": note},
    )
    r.raise_for_status()
    print(f"  [OK] submitted quote: ¥{price} / {lead} 天")

# 6. Alice closes quoting → creates award task
r = requests.post(
    f"{BASE}/api/internal/outsource-requests/{req_id}/close-quoting",
    headers=H(alice_tok),
)
r.raise_for_status()
award_task = r.json()["task_id"]
print(f"  [OK] alice closed quoting → task_id={award_task}")

# 7. Carol (purchasing_manager) sees the task
r = requests.get(f"{BASE}/api/internal/approvals/pending", headers=H(carol_tok))
r.raise_for_status()
carols_tasks = r.json()["items"]
my_task = next((t for t in carols_tasks if t["id"] == award_task), None)
assert my_task, f"Carol should see task {award_task}"
print(f"  [OK] carol sees her award task")

# 8. Carol opens detail → sees quote comparison
r = requests.get(f"{BASE}/api/internal/approvals/{award_task}", headers=H(carol_tok))
r.raise_for_status()
detail = r.json()
quotes = detail["payload"]["quotations"]
print(f"  [OK] carol sees {len(quotes)} quotations sorted by price")
for q in quotes:
    print(f"       {q['supplier_name']}: ¥{q['unit_price']} / {q['lead_time_days']} 天")

# 9. Carol picks the cheapest (actually first in sorted list) and approves
assert len(quotes) >= 2
winner = quotes[0]
r = requests.post(
    f"{BASE}/api/internal/approvals/{award_task}/award",
    headers=H(carol_tok),
    json={
        "action": "approve",
        "awarded_invitation_id": winner["invitation_id"],
        "comment": "价格最优",
    },
)
r.raise_for_status()
result = r.json()
print(f"  [OK] carol awarded: {result}")
order_id = result["outsource_order_id"]

# 10. Winning processor sees the new order
winner_is_huaxinze = winner["supplier_name"] == "青岛华欣泽机械模具有限公司"
winner_tok = huaxinze_tok if winner_is_huaxinze else yuanmao_tok
winner_name = "huaxinze" if winner_is_huaxinze else "yuanmao"

r = requests.get(f"{BASE}/api/processor/orders", headers=H(winner_tok))
r.raise_for_status()
orders = r.json()["items"]
my_order = next((o for o in orders if o["id"] == order_id), None)
assert my_order, f"{winner_name} should see order {order_id}"
print(f"  [OK] {winner_name} sees order #{order_id} = {my_order['order_no']} status={my_order['status']}")

# 11. Progress status
for to_status in ["accepted", "producing", "delivered"]:
    r = requests.post(
        f"{BASE}/api/processor/orders/{order_id}/status",
        headers=H(winner_tok),
        json={"to_status": to_status, "note": f"transitioning to {to_status}"},
    )
    r.raise_for_status()
    print(f"  [OK] {winner_name} transitioned order to '{to_status}'")

# 12. Verify final state from internal side
r = requests.get(f"{BASE}/api/internal/outsource-orders/{order_id}", headers=H(alice_tok))
r.raise_for_status()
final = r.json()
print(f"\n[FINAL] Order #{order_id} = {final['order']['order_no']}")
print(f"  supplier:  {final['order']['supplier_name']}")
print(f"  price:     ¥{final['order']['unit_price']} × {final['order']['quantity']} = ¥{final['order']['total_amount']}")
print(f"  lead:      {final['order']['lead_time_days']} 天")
print(f"  status:    {final['order']['status']}")
print(f"  events:    {len(final['events'])} transitions")

assert final["order"]["status"] == "delivered"

print("\n" + "=" * 70)
print("[PASS] Stage 3 end-to-end test complete")
print("=" * 70)
