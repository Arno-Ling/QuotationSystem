# Implementation Plan: 模具委外采购系统 — 轻量脚本版 MVP

> **本次范围**：阶段 0（骨架）+ 阶段 1（生产决策）+ 阶段 3 简化版（委外询价闭环）
> 不包含：自制分支、材料方、质检、异常处理、对账、全流程看板
> 预计工期：**8 个工作日**
> 产出：**我方 + 加工方** 二端可用的完整委外闭环

## Overview

本计划按 **"能跑起来"优先原则** 推进：
- 先搭三端登录骨架 + 项目录入（阶段 0）
- 再做生产决策（阶段 1，用硬编码规则替代 AI）
- 最后做委外询价完整闭环（阶段 3 简化版：群发询价 → 加工方回复 → 报价对比 → 采购经理审批 → 中标）

### 3 个核心确认

| 项 | 方案 |
|---|------|
| AI 决策 | **硬编码规则**：`热处理/表面处理/线割 → 委外`；`磨/铣/车 → 自制`（MVP 不调 LLM） |
| 前端 | **纯 HTML + vanilla JS + fetch**（静态文件由 FastAPI 直接 serve，不用 React） |
| 询价流程 | **群发 → 回收 → 表格推采购经理审批 → 经理勾中标家** |

### 技术栈

- Python 3.10+ / FastAPI / pymysql（直接 SQL，不用 SQLAlchemy ORM，最快）
- MySQL 3306（沿用现有 `mold_procurement` 库）
- 静态 HTML/JS/CSS（`backend/static/` 目录）
- JWT 认证（`python-jose` 已有）

### 代码组织（新结构，保持简单）

```
backend/
├── mvp/                          # 新增：本次 MVP 全部新代码
│   ├── __init__.py
│   ├── main.py                   # 独立的 FastAPI 入口（不动原 main.py）
│   ├── auth.py                   # 登录 + JWT
│   ├── db.py                     # pymysql 连接工具
│   ├── routes/
│   │   ├── internal.py           # 我方路由 /api/internal/*
│   │   ├── processor.py          # 加工方路由 /api/processor/*
│   │   └── common.py             # 登录、健康检查
│   └── rules.py                  # 阶段 1 硬编码决策规则
├── static/                       # 新增：HTML/JS/CSS
│   ├── login.html
│   ├── internal/                 # 我方页面
│   │   ├── home.html
│   │   ├── project-detail.html
│   │   ├── decisions.html
│   │   └── outsource-compare.html
│   └── processor/                # 加工方页面
│       ├── home.html
│       └── invitation-detail.html
└── migrations/
    ├── 004_mvp_core.sql          # 阶段 0
    ├── 005_production_decision.sql  # 阶段 1
    ├── 006_outsource.sql         # 阶段 3
    └── run_mvp_migrations.py
```

**为什么不改之前 Phase 1 的 `interfaces/` 和 `adapters/`**：那些是为 Harness 升级预留的，本次 MVP 先不用；阶段 0-3 跑通后再重构为走 Protocol，代价低。

---

## Tasks

### 🏗️ 阶段 0 — 骨架（预计 2 天）

#### 任务 0.1 — 数据库迁移（5 张表）

- [ ] **0.1.1** 编写 `backend/migrations/004_mvp_core.sql`
  - 建表 `tenants`（租户：internal / processor / material 三类）
  - 建表 `users`（关联 tenant_id，username + password_hash）
  - 建表 `projects`（项目主档：name / customer / deadline / status / tenant_id / 报价单价 / 数量）
  - 建表 `project_parts`（项目下零件清单：part_no / material / qty / processes_json）
  - 建表 `attachments`（通用附件：related_type / related_id / file_path / uploaded_by）
  - 所有表用 `CREATE TABLE IF NOT EXISTS` 保证幂等
  - 字符集 utf8mb4，InnoDB
  - 预计：30 分钟

- [ ] **0.1.2** 编写 `backend/migrations/run_mvp_migrations.py`
  - 复用 `run_003_migration.py` 的 SQL 分割逻辑
  - 依次跑 `004_mvp_core.sql` / `005_production_decision.sql` / `006_outsource.sql`（后两个文件先建空）
  - 验证所有新表存在
  - 预计：20 分钟

- [ ] **0.1.3** 种子数据脚本 `backend/migrations/seed_mvp.py`
  - 插入 1 条 internal 租户（"我方"）+ 2 条 processor 租户（从 11 家供应商里选 2 家）
  - 每个租户 1 个测试用户（密码 `test123`，bcrypt 加密）
  - 打印登录凭证让用户知道用什么登
  - 预计：30 分钟

#### 任务 0.2 — MVP 应用骨架

- [ ] **0.2.1** 新建 `backend/mvp/db.py`
  - 函数 `get_conn()`: pymysql 连接，读 `backend/.env`
  - 函数 `execute(sql, params)` / `fetch_one(sql, params)` / `fetch_all(sql, params)` 简易封装
  - 不用 ORM，全部直接 SQL
  - 预计：30 分钟

- [ ] **0.2.2** 新建 `backend/mvp/auth.py`
  - `POST /api/auth/login`：接收 `{username, password}`，查 DB → bcrypt 验证 → 生成 JWT（载荷：`user_id / tenant_id / tenant_type / username`）
  - 中间件 `get_current_user(authorization: str = Header(...))`: 从 Bearer Token 解码 JWT，返回用户对象；失败抛 401
  - 预计：1 小时

- [ ] **0.2.3** 新建 `backend/mvp/main.py`
  - FastAPI 实例，独立于 `backend/main.py`
  - 挂载 `static/` 目录到 `/static`
  - 挂载路由：`auth.router`、`internal.router`、`processor.router`、`common.router`
  - `GET /`  重定向到 `/static/login.html`
  - `GET /home` 根据 JWT 里的 `tenant_type` 跳到 `/static/internal/home.html` 或 `/static/processor/home.html`
  - 运行命令：`uvicorn mvp.main:app --reload --port 8001`（与旧 main.py 共存，不冲突）
  - 预计：1 小时

#### 任务 0.3 — 我方：项目管理（CRUD + 确认流程）

- [ ] **0.3.1** 新建 `backend/mvp/routes/internal.py`，实现项目 API（仅 tenant_type=internal 可访问）
  - `GET  /api/internal/projects` 列表（分页，按创建时间倒序）
  - `POST /api/internal/projects` 创建（入参：name, customer, deadline, unit_price, quantity；状态 = `drafted`）
  - `GET  /api/internal/projects/{id}` 详情（含零件列表 + 附件列表）
  - `PATCH /api/internal/projects/{id}` 编辑基本信息
  - `POST /api/internal/projects/{id}/parts` 添加零件（入参：part_no, material, qty, processes 数组）
  - `DELETE /api/internal/projects/{id}/parts/{part_id}` 删除零件
  - `POST /api/internal/projects/{id}/attachments` 上传图纸（multipart，保存到 `backend/uploads/drawings/`）
  - `POST /api/internal/projects/{id}/confirm` 确认：校验至少 1 个零件 + 至少 1 份图纸 + 报价已填 → status=`confirmed`
  - 预计：3 小时

- [ ] **0.3.2** 登录页 `backend/static/login.html`
  - 极简表单：账号 + 密码 + 登录按钮
  - 成功后存 token 到 localStorage，跳 `/home`
  - 失败显示错误
  - 预计：30 分钟

- [ ] **0.3.3** 我方首页 `backend/static/internal/home.html`
  - 顶部导航：欢迎 + 退出登录
  - 项目列表表格：ID / 名称 / 客户 / 状态（drafted/confirmed）/ 操作（查看/编辑）
  - 【新建项目】按钮 → 弹窗或跳详情页
  - 预计：1 小时

- [ ] **0.3.4** 我方项目详情页 `backend/static/internal/project-detail.html`
  - 基本信息：名称、客户、交期、报价、数量（可编辑）
  - 零件列表表格：part_no / 材料 / 数量 / 工序列表 / 删除按钮
  - 【添加零件】按钮 → 弹窗：填零件号、材料、数量、工序（文本框用逗号分隔："磨,铣,热处理"）
  - 图纸区：已上传列表 + 【上传图纸】按钮
  - 【确认项目】按钮：只有零件≥1 && 图纸≥1 && 报价已填时可用；点击后调 `confirm` 接口，成功后状态变 `confirmed`
  - 预计：2 小时

- [ ] **0.3.5** 加工方首页占位 `backend/static/processor/home.html`
  - 仅显示欢迎信息 + 【我的询价单】tab（阶段 3 填充）+ 【我的加工单】tab（阶段 3 填充）
  - 预计：15 分钟

#### 任务 0.4 — 阶段 0 验收

- [ ] **0.4.1** Checkpoint 1：阶段 0 跑通测试
  - 手动测试清单：
    1. 跑迁移：所有 5 张表创建成功
    2. 跑种子：生成 3 个测试用户
    3. 启动 `uvicorn mvp.main:app --port 8001`
    4. 浏览器打开 `http://localhost:8001`  → 跳登录页
    5. 用 internal 账号登录 → 跳到我方首页（空列表）
    6. 【新建项目】→ 填写基本信息 → 创建成功
    7. 详情页【添加零件】2 次 → 【上传图纸】1 次 → 【确认项目】→ 状态变 confirmed
    8. 退出 → 用 processor 账号登录 → 跳到加工方首页（空）
  - 预计：30 分钟

**阶段 0 产物**：三端可登录，我方能录入完整项目并确认。

---

### 🎯 阶段 1 — 生产决策（预计 3 天）

#### 任务 1.1 — 数据库迁移

- [ ] **1.1.1** 编写 `backend/migrations/005_production_decision.sql`
  - 建表 `supplier_capabilities`（supplier_id / process_name）
  - 建表 `production_decisions`（project_id / part_id / process_name / ai_suggestion / ai_reason / final_decision / confirmed_by / confirmed_at / status）
  - 种子：把需求文档里 11 家供应商的工艺能力录入 `supplier_capabilities`
    - 如"青岛和兴嘉业金属制品" → `["模架"]`
    - "苏州元茂精密机械" → `["全加工零件"]`
    - "城阳区睿德华" → `["快丝", "小磨床"]`
    - 完整映射见附录 A
  - 预计：30 分钟

- [ ] **1.1.2** 在 `seed_mvp.py` 补充供应商数据
  - 如果本次 MVP 的 2 个 processor 租户名称与这 11 家中的某 2 家对上，则关联 `supplier_id`；否则新增 2 条 `suppliers` 记录专用于 MVP 测试
  - 预计：20 分钟

#### 任务 1.2 — 决策规则引擎（硬编码）

- [ ] **1.2.1** 新建 `backend/mvp/rules.py`
  - 常量 `FORCE_OUTSOURCE_PROCESSES = {"热处理", "表面处理", "线割"}`（内部不具备能力）
  - 常量 `PREFER_INTERNAL_PROCESSES = {"磨", "铣", "车", "钻", "镗"}`
  - 函数 `suggest_decision(process_name: str) -> tuple[str, str]`:
    - 如果 process_name 在 FORCE_OUTSOURCE_PROCESSES → 返回 `("outsource", "公司不具备XXX能力，强制委外")`
    - 如果 process_name 在 PREFER_INTERNAL_PROCESSES → 返回 `("self_made", "常规工序，内部可完成")`
    - 其他 → 返回 `("outsource", "该工序建议委外处理")`（保守策略）
  - 预计：20 分钟

- [ ] **1.2.2** 为 `rules.py` 加一个小测试 `backend/tests/test_rules.py`
  - 验证：热处理→outsource；磨→self_made；未知工序→outsource
  - 能独立跑 `python -m pytest backend/tests/test_rules.py`
  - 预计：15 分钟

#### 任务 1.3 — 生产决策 API

- [ ] **1.3.1** 在 `internal.py` 加决策 API
  - `POST /api/internal/projects/{id}/decide` 触发决策：
    - 前置：项目 status = confirmed
    - 读 project_parts → 对每个零件的每道工序调 `suggest_decision()`
    - 批量 INSERT `production_decisions`（status=`pending_review`）
    - 返回创建的决策行数
  - `GET /api/internal/projects/{id}/decisions` 返回当前项目所有决策行（按零件+工序分组）
  - `PATCH /api/internal/decisions/{decision_id}` 人工修改单行：入参 `{final_decision, reason}`；decisions.final_decision 和 status=`reviewed`
  - `POST /api/internal/projects/{id}/decisions/submit` 提交审批：
    - 前置：所有决策 status=`reviewed`
    - 创建一条 `workflow_approval_tasks`（kind=`production_decision`、node_id=`decision_{project_id}`、assignee=ROLE=PRODUCTION_MANAGER）
    - 复用已有的 migration 002 审批表
  - 预计：3 小时

- [ ] **1.3.2** 审批处理 API
  - `GET /api/internal/approvals/pending` 当前用户待办列表（读 workflow_approval_tasks，按 assignee_id=当前 user_id 或 assignee_type=ROLE 且角色匹配）
  - `GET /api/internal/approvals/{task_id}` 单个审批详情（包含 production_decisions 列表）
  - `POST /api/internal/approvals/{task_id}/action` 执行审批：
    - 入参 `{action: "approve"|"reject", comment}`
    - INSERT `workflow_approval_records`
    - UPDATE `workflow_approval_tasks.status=completed`
    - 如果 approve 且 kind=`production_decision`：
      - 把 decisions.status 全部置 `finalized`
      - 为所有 `final_decision=outsource` 的行聚合创建一张 `outsource_requests`（草稿）→ 阶段 3 继续
    - 如果 reject：decisions 退回 `pending_review`
  - 预计：2 小时

#### 任务 1.4 — 前端页面

- [ ] **1.4.1** 决策结果页 `backend/static/internal/decisions.html`
  - 顶部：项目基本信息
  - 表格：零件号 / 工序 / AI建议 / 理由 / 最终决策（下拉：自制/委外）/ 操作
  - 每行【改为自制】/【改为委外】按钮 → 调 PATCH API
  - 底部【提交审批】按钮（所有行都已审核时才可点）
  - 预计：1.5 小时

- [ ] **1.4.2** 待办页 `backend/static/internal/approvals.html`
  - 表格：任务ID / 类型 / 项目 / 创建时间 / 操作
  - 点击打开详情弹窗或新页 `approval-detail.html`
  - 详情页展示决策清单（只读）+ 备注输入框 + 【同意】/【拒绝】按钮
  - 预计：1.5 小时

- [ ] **1.4.3** 项目详情页加【触发决策】按钮
  - 只在 status=confirmed 时显示
  - 点击调 `POST /api/internal/projects/{id}/decide` → 成功后跳 `decisions.html?project_id=xxx`
  - 预计：20 分钟

#### 任务 1.5 — 阶段 1 验收

- [ ] **1.5.1** Checkpoint 2：阶段 1 跑通测试
  - 手动测试清单：
    1. 用阶段 0 建的项目（2 个零件 + 6 道工序其中包含 1 个"热处理"）
    2. 点【触发决策】→ 跳到 decisions 页，看到 6 行
    3. 热处理那行应该是 outsource + 红色提示
    4. 改一行自制为委外 → 提交审批
    5. 退出，用 production_manager 角色的用户登录（阶段 0 种子里加一个）
    6. 待办页看到新任务 → 点进详情 → 同意
    7. 回到项目详情，应该看到 1 张草稿状态的 outsource_requests
  - 预计：30 分钟

**阶段 1 产物**：从项目 → AI 建议 → 人工改 → 审批 → 委外单草稿。

---

### 🚚 阶段 3 简化版 — 委外询价闭环（预计 3 天）

> **关键逻辑**：群发询价 → 加工方各自回复 → 系统把所有已回复报价做成表格 → 推送采购经理审批 → 经理勾中标家 → 生成正式加工单

#### 任务 3.1 — 数据库迁移

- [ ] **3.1.1** 编写 `backend/migrations/006_outsource.sql`
  - 建表 `outsource_requests`：
    - 字段：id / project_id / title / required_processes_json / quantity / deadline / status / created_at
    - status 枚举：`draft / inviting / comparing / pending_award_approval / awarded / cancelled`
    - 关联项目 + 由阶段 1 审批通过后创建
  - 建表 `outsource_request_invitations`：
    - 字段：id / request_id / supplier_id / sent_at / invitation_status（`sent / quoted / no_response`）
    - **群发时**：为所有符合工艺的 supplier 各建一条
  - 建表 `outsource_quotations`：
    - 字段：id / invitation_id / unit_price / lead_time_days / note / attachments_json / submitted_at
    - 一个邀请对应一个报价（最多一个）
  - 建表 `outsource_orders`：
    - 字段：id / request_id / winning_quotation_id / supplier_id / unit_price / lead_time_days / status / created_at
    - status 枚举：`awarded / accepted / producing / delivered / cancelled`
  - 建表 `outsource_order_status_events`：
    - 字段：id / order_id / from_status / to_status / changed_by / changed_at / note
  - 预计：45 分钟

#### 任务 3.2 — 我方：询价单管理

- [ ] **3.2.1** 在 `internal.py` 加询价单 API
  - `GET /api/internal/outsource-requests` 列表（按状态分组）
  - `GET /api/internal/outsource-requests/{id}` 详情（含邀请列表 + 报价列表）
  - `PATCH /api/internal/outsource-requests/{id}` 编辑草稿（标题、截止时间）
  - `GET /api/internal/outsource-requests/{id}/candidates` **固定算法匹配**：
    - 读 request.required_processes_json
    - 查 supplier_capabilities WHERE process_name IN (required_processes)
    - GROUP BY supplier_id，COUNT 匹配工艺数
    - 返回按匹配数降序 supplier 列表
  - `POST /api/internal/outsource-requests/{id}/send` **群发**：
    - 前置：status=draft
    - 读候选 supplier 列表（自动调上一个接口的逻辑）
    - 为每个候选插一条 `outsource_request_invitations`（invitation_status=sent）
    - UPDATE request.status=inviting
    - 返回发送的邀请数
  - `POST /api/internal/outsource-requests/{id}/close-quoting` **截止报价**：
    - 前置：status=inviting
    - UPDATE 所有未回复邀请的 invitation_status=no_response
    - UPDATE request.status=comparing
    - 自动创建一条审批任务（kind=`outsource_award`、assignee=ROLE=PURCHASING_MANAGER）
    - 载荷：该 request 所有已回复的报价数组
  - 预计：3 小时

#### 任务 3.3 — 加工方：询价邀请 + 报价

- [ ] **3.3.1** 新建 `backend/mvp/routes/processor.py`
  - `GET /api/processor/invitations` 我的询价邀请列表（只看 supplier_id = 当前租户关联的 supplier）
    - 字段：id / 项目名 / 所需工艺 / 数量 / 截止日期 / 状态
  - `GET /api/processor/invitations/{id}` 详情（含项目信息 + 零件 + 图纸链接）
    - 图纸链接带时限 token（MVP 简化：直接返回文件路径，下一版再加密）
  - `POST /api/processor/invitations/{id}/quote` 提交报价
    - 入参：`{unit_price, lead_time_days, note}`
    - INSERT outsource_quotations
    - UPDATE invitation_status=quoted
    - 预计：2 小时

- [ ] **3.3.2** 加工方页面 `backend/static/processor/home.html`
  - tab 1：【我的询价邀请】表格 → 点进详情 → 填报价表单
  - tab 2：【我的加工单】表格 → 点进详情 → 推进状态按钮
  - 预计：30 分钟

- [ ] **3.3.3** 加工方邀请详情 `backend/static/processor/invitation-detail.html`
  - 项目信息 + 零件清单（只读）
  - 图纸下载链接
  - 报价表单：单价 / 交期(天) / 备注 / 【提交报价】按钮
  - 如果已报价，显示"已提交报价"并禁用表单
  - 预计：1 小时

#### 任务 3.4 — 我方：报价对比 + 采购经理审批

- [ ] **3.4.1** 采购经理审批（复用阶段 1 的审批框架）
  - 采购经理登录 → 待办页看到 `outsource_award` 类型任务
  - `GET /api/internal/approvals/{task_id}` 返回载荷：
    - 完整的报价表格：每行一个加工方 = { supplier_name, unit_price, lead_time, note, total, submitted_at }
    - 按价格升序排序（或留前端排序）
  - `POST /api/internal/approvals/{task_id}/action` 审批：
    - 入参扩展 `{action, comment, awarded_quotation_id?}`
    - 如果 action=approve：**必须传 awarded_quotation_id**
      - INSERT outsource_orders（关联 winning_quotation）
      - UPDATE request.status=awarded
      - 触发通知加工方（MVP：只写日志，不发真实邮件）
    - 如果 action=reject：UPDATE request.status=cancelled
  - 预计：1.5 小时

- [ ] **3.4.2** 采购经理审批页 `backend/static/internal/outsource-compare.html`
  - 顶部询价单基本信息
  - **报价对比表格**：供应商名 / 单价 / 交期 / 备注 / 总金额 / 提交时间 / 【选为中标】单选
  - 已有"基准价"则用绿色/红色标出偏离
  - 备注输入框 + 【批准中标】/【拒绝全部】按钮
  - 预计：1.5 小时

#### 任务 3.5 — 加工方：加工单推进

- [ ] **3.5.1** 在 `processor.py` 加加工单 API
  - `GET /api/processor/orders` 我的加工单列表
  - `GET /api/processor/orders/{id}` 详情
  - `POST /api/processor/orders/{id}/status` 更新状态
    - 入参 `{to_status, note}`，合法转换：`awarded → accepted → producing → delivered`
    - INSERT outsource_order_status_events
  - 预计：1 小时

- [ ] **3.5.2** 加工方加工单详情 `backend/static/processor/order-detail.html`
  - 顶部订单信息（单价、交期、零件）
  - 状态时间线
  - 【接受订单】/【开始生产】/【已交货】按钮（根据当前状态显示）
  - 预计：1 小时

#### 任务 3.6 — 我方：加工单监控

- [ ] **3.6.1** 在 `internal.py` 加加工单 API
  - `GET /api/internal/outsource-orders` 所有委外加工单
  - `GET /api/internal/outsource-orders/{id}` 详情 + 状态日志
  - 预计：30 分钟

- [ ] **3.6.2** 我方委外总览页 `backend/static/internal/outsource-orders.html`
  - 表格：订单ID / 项目 / 供应商 / 单价 / 交期 / 状态 / 创建时间
  - 按状态筛选
  - 预计：45 分钟

#### 任务 3.7 — 阶段 3 简化版验收

- [ ] **3.7.1** Checkpoint 3：端到端闭环测试
  - 手动测试清单（承接阶段 1 的草稿 request）：
    1. 我方采购员登录 → 打开那张草稿询价单
    2. 点【查看候选加工方】→ 看到符合工艺的 supplier 列表（至少 2 家，对应 MVP 种子的 2 个 processor 租户）
    3. 点【群发询价】→ 2 条邀请生成
    4. 退出，登录加工方A → 看到待报价邀请 → 填 `¥5000 / 15天` → 提交
    5. 退出，登录加工方B → 填 `¥4500 / 20天` → 提交
    6. 回我方，点【截止报价】→ 采购经理待办出现
    7. 登录采购经理账号 → 看到 2 行报价表格 → 勾加工方A → 【批准中标】
    8. 数据库里：outsource_orders 多了 1 条，supplier=A
    9. 退出，登录加工方A → 看到加工单 → 点【接受订单】→【开始生产】→【已交货】
    10. 我方总览页看到这条单最终状态 = delivered
  - 预计：30 分钟

**阶段 3 简化版产物**：我方与加工方二端完整闭环可演示。

---

## 附录 A — 供应商工艺能力映射（阶段 1 种子用）

| 供应商 | 工艺能力标签 |
|-------|-------------|
| 青岛和兴嘉业金属制品 | 模架 |
| 苏州元茂精密机械 | 全加工零件 |
| 青岛铂锐迪精密机械 | 全加工零件 |
| 昆山宸壮精密模具 | 全加工零件 |
| 城阳区睿德华 | 快丝, 小磨床 |
| 青岛金源汇精密模具 | 慢丝 |
| 青岛铭微德精密机械 | 慢丝 |
| 宁波市百德模具 | 全加工零件 |
| 昆山市卓诚辉电子科技 | 全加工零件 |
| 青岛颖泰和精密机械 | 钣金 |
| 青岛华欣泽机械模具 | 快丝, 中丝, 慢丝 |

---

## Notes

- **所有 API 必须校验 tenant_type**：`internal` 路由只允许 internal 租户访问；`processor` 路由只允许 processor 租户，返回 403 给越权。
- **审批复用 migration 002 的表**：`workflow_approval_tasks / _records / workflow_state_events` 已经有了，直接用。
- **审批 kind 字段用 node_id 承载**：MVP 期间，workflow_approval_tasks.node_id 存储业务类型（`production_decision` / `outsource_award`），不额外加列。
- **JWT 密钥**：沿用 `.env` 里的 `SECRET_KEY`。
- **端口冲突**：新 FastAPI 跑 `8001`，旧的（`/dashboard` `/api/exception/analyze`）继续在 `8000`；等 MVP 稳定后再合并到一个进程。
- **跳过了什么**：
  - 材料方视角（本次不做）
  - 自制分支（采购/生产执行/质检）
  - 报价单 OCR 解析（加工方直接填表单）
  - 多轮谈判
  - 异常处理（阶段 5）
  - 对账（阶段 4）
  - 全流程看板（阶段 6）

---

---

### ✅ 阶段 3.1 — 浏览器端到端验收（预计 0.5 天）

> 阶段 3 的后端 API 与前端页面全部完成，且 E2E 测试脚本已跑到"huaxinze sees 2 invitations"节点。这一节把完整闭环在浏览器里手动跑一次，确认零回归后再推进下一个阶段。

#### 任务 3.1.1 — 环境准备

- [ ] **3.1.1.a** 确认 MySQL 3306 服务在跑
  - `mysql -h 127.0.0.1 -P 3306 -u root -p361615 -e "USE mold_procurement; SHOW TABLES;"` 应列出 outsource_* 5 张表
- [ ] **3.1.1.b** 确认 `backend/.env` 的 `SECRET_KEY / DB_PASSWORD=361615` 填对
- [ ] **3.1.1.c** 启动 MVP 服务 `uvicorn mvp.main:app --reload --port 8001`（cwd=backend）
  - 打开 `http://localhost:8001` 能跳登录页
- [ ] **3.1.1.d** （可选）清理租户重复行，执行 `python backend/migrations/fix_tenant_dupes.py` 或直接在 MySQL 里跑一次 DELETE … WHERE id NOT IN (MIN(id) GROUP BY name)

#### 任务 3.1.2 — 我方侧闭环

- [ ] **3.1.2.a** 用 `alice / test123` 登录 → 我方首页
- [ ] **3.1.2.b** 【新建项目】：名称"MVP 验收 1"、客户、交期（后 30 天）、报价、数量 → 保存
- [ ] **3.1.2.c** 详情页【添加零件】2 个：
  - 零件 A：工序 `磨,铣,热处理`
  - 零件 B：工序 `线割,表面处理`
- [ ] **3.1.2.d** 【上传图纸】任选一个 PDF/图片
- [ ] **3.1.2.e** 【确认项目】→ status 应变为 confirmed
- [ ] **3.1.2.f** 【触发决策】→ 跳决策页，看到 5 行（热处理/线割/表面处理=outsource；磨/铣=self_made）
- [ ] **3.1.2.g** 任意改 1 行决策 → 【提交审批】
- [ ] **3.1.2.h** 退出 → 用 `bob / test123` 登录 → 待办页【同意】→ 项目详情应看到草稿询价单

#### 任务 3.1.3 — 询价群发

- [ ] **3.1.3.a** alice 重新登录 → 顶部【询价单】→ 打开草稿
- [ ] **3.1.3.b** 【查看候选加工方】看到工艺覆盖度列表（华欣泽的线割/热处理覆盖最多会排前）
- [ ] **3.1.3.c** 【群发询价】→ 邀请数 ≥ 1

#### 任务 3.1.4 — 加工方报价

- [ ] **3.1.4.a** 退出 → 用 `huaxinze / test123` 登录 → 加工方首页
- [ ] **3.1.4.b** 【我的询价邀请】应看到刚才群发的邀请 → 打开详情
- [ ] **3.1.4.c** 图纸链接能下载
- [ ] **3.1.4.d** 填报价 `5000 / 15 / 备注` → 提交 → 显示"已提交报价"
- [ ] **3.1.4.e** （可选）`yuanmao / test123` 登录：若工艺未覆盖应**看不到**邀请，符合设计

#### 任务 3.1.5 — 审批与中标

- [ ] **3.1.5.a** alice 登录 → 打开询价单 → 【截止报价】
- [ ] **3.1.5.b** 退出 → `carol / test123`（PURCHASING_MANAGER）登录 → 待办出现 outsource_award
- [ ] **3.1.5.c** 打开对比页 → 看到报价表格（huaxinze 一行）→ 勾选 → 【批准中标】
- [ ] **3.1.5.d** 数据库验证：`SELECT * FROM outsource_orders;` 应出现 1 条 awarded 单

#### 任务 3.1.6 — 加工单推进

- [ ] **3.1.6.a** huaxinze 登录 → 【我的加工单】看到新单
- [ ] **3.1.6.b** 依次点【接受订单】→【开始生产】→【已交货】
- [ ] **3.1.6.c** alice 登录 → 顶部【加工单】→ 看到状态 = delivered

#### 任务 3.1.7 — 清理与收尾

- [ ] **3.1.7.a** 删除项目根目录的临时测试文件：`test_stage3.py / test_stage3_output.txt / check_tenants.py / check_users.py / fix_tenant_dupes.py`（若已不需要）
- [ ] **3.1.7.b** 在本 tasks.md 末尾勾选所有 3.1.* 任务

**阶段 3.1 产物**：我方 + 加工方二端闭环在浏览器里被端到端验证，零回归。

---

## 工期汇总

| 阶段 | 任务数 | 预计 |
|------|-------|-----|
| 0 骨架 | 15 个子任务 | 2 天 |
| 1 生产决策 | 12 个子任务 | 3 天 |
| 3 简化版 | 14 个子任务 | 3 天 |
| 3.1 浏览器验收 | 18 个子任务 | 0.5 天 |
| **合计** | **59 子任务** | **8.5 天** |

---

## 下一步

用户确认此计划后，从 **任务 0.1.1（migration 004_mvp_core.sql）** 开始动手。
