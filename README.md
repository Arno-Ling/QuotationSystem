# 模具委外采购管理系统（MVP）

一个面向模具制造场景的轻量委外采购系统。我方、加工方、材料方三端闭环，覆盖从项目建模到对账的全流程。

---

## 架构概览

```
┌──────────────────────────────────────────────────────┐
│  前端：原生 HTML + JS + common.css（深蓝玻璃拟态）    │
│  我方 / 加工方 / 材料方 三套页面                       │
└──────────────────────────────────────────────────────┘
                         │
┌──────────────────────────────────────────────────────┐
│  FastAPI (uvicorn, 端口 8001)                          │
│  auth / internal / admin / basis / processor /         │
│  material / qc / recon / inquiry / common              │
└──────────────────────────────────────────────────────┘
                         │
┌──────────────────────────────────────────────────────┐
│  PostgreSQL 18（库名 weiwai，46 张表）                 │
│  psycopg2 原生连接，全量 PG 方言                       │
└──────────────────────────────────────────────────────┘

备用：端口 8000 保留给 ExceptionAgent（LangChain + ChromaDB RAG）
```

### 技术栈

- **后端**：Python 3.10+ / FastAPI / psycopg2 / bcrypt / PyJWT
- **数据库**：PostgreSQL 18
- **前端**：原生 HTML + Vanilla JS + CSS（无打包器）
- **RAG**：ChromaDB（仅 ExceptionAgent 在用）
- **LLM**：LiteLLM + 小米 MiMo（`mimo-v2.5-pro`）

---

## 快速开始

### 前置

- PostgreSQL 18，默认账号 `postgres / 361615`，已建库 `weiwai`
- Python 3.10+

### 初始化数据库

```bash
cd backend
# psql 路径按实际情况改
set PGPASSWORD=361615
set PGCLIENTENCODING=UTF8
"C:\Program Files\PostgreSQL\18\bin\psql.exe" -h localhost -p 5432 -U postgres -d weiwai ^
  -f migrations/postgres/001_schema.sql
# 依次跑 002 ~ 012
```

迁移列表（按顺序执行）：

| 文件 | 作用 |
|---|---|
| `001_schema.sql` | 基础域（suppliers / tenants / users / projects / molds / parts / processes / faces / attachments） |
| `002_seed.sql` | 种子数据（加工方式、供应商、测试账号） |
| `003_comments_and_enrichments.sql` | 补注释与字段丰富 |
| `004_outsource_hierarchy.sql` | 5 层委外粒度 + 工作流 + 审批 |
| `005_full_domain.sql` | 基础数据库 / 自制 / 质检异常 / 对账 / 看板 |
| `006_basis_seed.sql` | basis 示例数据 |
| `007_material_tenant_seed.sql` | 材料方账号 |
| `009_simplify_roles.sql` | 角色方案 B 简化 |
| `010_shipment_photos.sql` | 加工方收料照 + 完工照 字段 |
| `011_material_sourcing.sql` | 材料供应分叉（询价单） |
| `012_roles_restore.sql` | roles 表种子 |

### 启动服务

```bash
cd backend
python -m uvicorn mvp.main:app --host 0.0.0.0 --port 8001 --reload --app-dir .
```

访问：

- 登录页 `http://localhost:8001/`
- Swagger `http://localhost:8001/docs`
- 静态资源 `http://localhost:8001/static/...`

---

## 测试账号（密码全部 `test123`）

| 角色 | 用户名 | 说明 |
|---|---|---|
| 我方 | `alice / bob / carol / dave` | 全部 `role=admin`，权限等价，共享待办池 |
| 加工方 | `huaxinze` | 华欣泽，工艺能力覆盖较广 |
| 加工方 | `yuanmao` | 元茂，工艺能力较少 |
| 材料方 | `baogang` | 宝钢 |
| 材料方 | `xinsheng` | 鑫盛 |

数据隔离不看 role 字段，只按 `tenant_type + tenant_id` 判。

---

## 已实现功能

### 阶段 1 — 项目建模与委外决策

- 项目 / 模具 / 零件 / 工序 / 面 五级建模
- 命名规范：
  - 项目号 `M26-0013`（公司码-年-4位序）
  - 模具号 `M26-0013-M01`
  - 零件号 `die-02` / `ins-03`（类型+序号自动生成）
  - 工序号 `P1-精铣-A,B,C`（面可多选）
- **数据驱动决策引擎**：读 `process_methods.is_internal_capable`，不调 LLM
  - 目标工艺我方不能做 → 走委外
  - 能做 → 走人工自选
  - 未知工艺 → 保守建议委外
- 工艺名模糊匹配（`P1-精铣-A,B,C` → `精铣`）

### 阶段 2 — 基础数据库（basis）

六个 tab 的集中维护页：原料价 / 工艺价 / 设备 / MOQ 规则 / 库存 / 供应商

### 阶段 3 — 5 层委外粒度

一张委外申请可按任意粒度组合选 scope：

| 粒度 | 单位 |
|---|---|
| project | 整个项目一次外协 |
| mold | 按模具 |
| part | 按零件 |
| method | 按工序（零件上的一道工艺） |
| face | 按面（A-F 六面独立） |

前端：采购经理矩阵式逐项中标 UI（`outsource-award.html`）
后端：`outsource_scope_items` + `outsource_quotation_lines` 完整支撑

### 阶段 4 — 自制分支

- 自动生成 `internal_production_orders`
- 给材料方开采购单 `material_purchase_orders`
- MOQ 余量自动入库到 `inventory.inventory_type='moq_surplus'`
- 新订单优先消耗 MOQ 余量

### 阶段 5 — 质检 + 异常

- 异常只从 `inspections.result='fail'` 触发
- ExceptionAgent 硬编码规则模拟分析（`mvp/exception_rules.py`），`analyze_exception()` 签名预留切 LLM
- 四档严重度 / 责任判定（material_supplier / processor / internal / customer / shared）
- `rework_orders` 驱动补料 / 重工 / 退货
- 质检页 `qc.html`

### 阶段 6 — 对账（后端完成，UI 未做）

- `reconciliations` + `reconciliation_items`
- 异常扣减自动并入对账明细

### 阶段 7 — 全流程看板

- 10 节点追踪：drafting / confirmed / deciding / decided / purchasing / producing / outsourcing / inspecting / exception / delivered
- 看板页 `kanban.html`

### 材料供应分叉

采购经理批准中标后，自由选择：

**A 路径 · 我方找材料方**
1. 发询价单给材料方（`material_inquiries`）
2. 材料方回报价（`material_quotations`）
3. 中标 → 自动生成 `material_purchase_orders`

**B 路径 · 加工方自采**
加工方在订单页上传采购凭证（`processor_material_proofs`）

### 3 关拍照取证（硬校验）

| 环节 | 字段 | 规则 |
|---|---|---|
| 材料方发货 | `material_shipments.photo_paths` | 没照片不让发货 |
| 加工方收料 | `outsource_orders.receive_photos` | 没照片不让接单 |
| 加工方完工 | `outsource_orders.complete_photos` | 没照片不让交货 |

`/uploads` 已挂载为静态资源。

### 系统管理（`/static/internal/admin/index.html`）

五个 tab：

- 🔧 **加工方式**：字典维护，控制 `is_internal_capable`（决策引擎唯一数据源）
- 🏭 **加工方**：供应商 + 工艺能力合并；行内 `⚙ 能力` 按钮弹窗按类别分组芯片选择
- 📦 **材料商**：按材料商视角展示 `suppliers + material_prices`，行内 `📦 材料清单` 弹窗增删
- 🏛 **合作租户**：`tenants` CRUD
- 👤 **用户**：`users` CRUD + 重置密码 / 停用

### 通用基础设施

- JWT 登录（`auth.py`）
- bcrypt 口令加密
- `require_tenant_type(...)` 依赖注入做租户隔离
- `workflow_approval_tasks` 共享待办池（assignee='ADMIN'，我方 4 人可相互代替）
- 异常 / 通知写入 `notifications`

---

## 目录结构

```
backend/
├─ mvp/                     主 MVP 应用（端口 8001）
│  ├─ main.py               FastAPI 入口，挂路由
│  ├─ db.py                 psycopg2 连接池 + fetch/execute 封装
│  ├─ auth.py               JWT + require_tenant_type
│  ├─ rules.py              数据驱动决策引擎
│  ├─ exception_rules.py    异常分析硬编码规则
│  ├─ tracking.py           10 节点看板写入工具
│  └─ routes/
│     ├─ admin.py           系统管理（5 类 CRUD + 材料商）
│     ├─ basis.py           基础数据库 6 tab
│     ├─ internal.py        我方：项目 / 委外 / 决策 / 审批
│     ├─ processor.py       加工方：接单 / 收料 / 完工 / 上传照片
│     ├─ material.py        材料方：接单 / 发货 / 上传照片
│     ├─ qc.py              质检 + 异常
│     ├─ recon.py           对账
│     ├─ inquiry.py         材料询价分叉
│     └─ common.py          通知等公共接口
├─ static/                  前端（原生 HTML）
│  ├─ login.html
│  ├─ app.js / common.css   通用 API 封装 + 深蓝主题
│  ├─ internal/             我方页面（14 个）
│  ├─ processor/            加工方页面
│  └─ material/             材料方页面
├─ migrations/postgres/     数据库迁移 001 ~ 012
├─ ai_modules/              ExceptionAgent（端口 8000）
│  ├─ agents/exception_agent.py
│  └─ skills/exception/     分析 / RAG / 责任判定 / 方案推荐
└─ uploads/                 照片存储（运行时）
```

---

## 数据库表清单（46 张）

**基础域（12）**：`suppliers / tenants / users / roles / projects / molds / project_parts / project_processes / process_faces / process_methods / supplier_capabilities / attachments`

**委外（7）**：`outsource_requests / outsource_scope_items / outsource_request_invitations / outsource_quotations / outsource_quotation_lines / outsource_orders / outsource_order_status_events`

**决策 + 工作流（7）**：`production_decisions / workflow_approval_tasks / workflow_approval_records / workflow_state_events / workflow_definitions / workflow_instances / workflow_node_executions`

**基础数据库（5）**：`material_prices / process_costs / equipment_capacity / moq_rules / inventory`

**自制（3）**：`internal_production_orders / material_purchase_orders / material_shipments`

**质检异常（5）**：`inspections / quality_exceptions / exception_evidence / exception_responsibility / rework_orders`

**对账（2）**：`reconciliations / reconciliation_items`

**看板（1）**：`workflow_tracking`

**通知（1）**：`notifications`

**材料供应分叉（3）**：`material_inquiries / material_inquiry_invitations / material_quotations / processor_material_proofs`

---

## 已知限制 / 尚未完成

- 对账页面（阶段 6）后端完成，前端 UI 未做
- ExceptionAgent 仅硬编码规则；LLM 切换接口 (`analyze_exception()`) 已预留
- 未接入邮件 / 短信通知，`notifications` 表只做站内消息
- 无单元测试 / 集成测试，冒烟测试靠 `backend/.smoke_*.py` 手工跑

---

## Windows 环境注意事项

- PowerShell 中文 GBK 解码会显示乱码（`鏂规` 之类），但数据库 UTF-8 正常
- Python 脚本打印 ¥ 等全角字符需显式设 UTF-8：
  ```python
  import io, sys
  sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
  ```
- 跑 psql 文件用 `-f file.sql`，避免 heredoc 中文乱码
- 命令分隔符用 `;`，不要用 `&&`

---

## LLM 代理配置（可选，ExceptionAgent 用）

如需启用真实 LLM，在 `backend/.env` 里填：

```env
LLM_API_BASE=https://token-plan-cn.xiaomimimo.com/anthropic
LLM_MODEL=anthropic/mimo-v2.5-pro
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
```

---

## License

仅供内部演示 / 毕设使用。
