# PostgreSQL 建表脚本（weiwai 库）

## 文件说明

| 文件 | 作用 | 顺序 |
|---|---|---|
| `001_schema.sql` | 19 张表 + 触发器函数 | **先跑** |
| `002_seed.sql` | 种子数据：11 供应商 / 3 租户 / 5 用户 / 32 条工艺能力 | **后跑** |

## 执行方法（推荐：pgAdmin）

1. 打开 **pgAdmin 4** → 连接本地 PostgreSQL（`localhost:5432` / `postgres` / `361615`）
2. 左侧选中 **weiwai** 数据库 → 右键 → **Query Tool**
3. 点 Query Tool 的 **打开文件**（📁 图标）→ 选 `backend/migrations/postgres/001_schema.sql`
4. 按 **F5** 或点 ▶ 执行
5. 底部应看到 19 行表名（`attachments ~ workflow_state_events`）
6. 再打开 `002_seed.sql` → F5 执行
7. 末尾校验应显示：
   ```
   supplier_capabilities  32
   suppliers              11
   tenants                 3
   users                   5
   ```

## 执行方法（或：psql 命令行）

```bash
# Windows（需先加 psql 到 PATH，一般在 C:\Program Files\PostgreSQL\16\bin）
psql -h localhost -p 5432 -U postgres -d weiwai -f backend/migrations/postgres/001_schema.sql
psql -h localhost -p 5432 -U postgres -d weiwai -f backend/migrations/postgres/002_seed.sql
```

## 登录账号（密码统一 test123）

| 账号 | 角色 | 租户 |
|---|---|---|
| alice    | 管理员/采购 | 我方 |
| bob      | 生产经理   | 我方 |
| carol    | 采购经理   | 我方 |
| huaxinze | 加工方操作员 | 青岛华欣泽（有线割/热处理等 6 种能力） |
| yuanmao  | 加工方操作员 | 苏州元茂（全加工/磨/铣/车） |

## 表清单（19 张）

**基础**：suppliers · tenants · users · projects · project_parts · attachments

**生产决策**：supplier_capabilities · production_decisions

**委外询价闭环**：outsource_requests · outsource_request_invitations · outsource_quotations · outsource_orders · outsource_order_status_events

**工作流/审批**：workflow_definitions · workflow_instances · workflow_node_executions · workflow_approval_records · workflow_approval_tasks · workflow_state_events

## 重要提醒

**后端代码目前还是 MySQL（pymysql）**。这两个 SQL 文件只是把表结构和种子数据建到 PostgreSQL 里。如果要让 MVP 服务连 PostgreSQL，后面还需要：

1. 换驱动：`pymysql` → `psycopg2`
2. 改 `backend/mvp/db.py`：连接字符串、`lastrowid` → `RETURNING id`
3. 改 `backend/mvp/routes/internal.py / processor.py`：若干 MySQL 方言（`ON DUPLICATE KEY UPDATE` → `ON CONFLICT`、`GROUP_CONCAT` → `STRING_AGG`、`SHOW TABLES LIKE` → `to_regclass`）
4. 改 `.env`：`DB_PORT=3306` → `5432`，加 `DB_NAME=weiwai`

这一步先让数据库就位，后端切换分开处理。
