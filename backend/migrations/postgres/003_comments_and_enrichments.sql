-- =============================================================================
-- Migration 003: 表注释 + 命名规范 + 4 张新表
-- =============================================================================
-- 包含：
--   A. 给 19 张已建表 + 关键列加 COMMENT
--   B. 项目号/零件号/工序号 命名规范支持（新增 seq 字段 + 唯一约束）
--   C. 新增 4 张表：
--      - process_methods  加工方式字典（精铣、钻孔、粗铣、磨、线割、热处理……）
--      - roles            内部角色字典
--      - project_processes 工序清单（每零件 × 每工序一行，含面 A-F + 加工方式）
--      - notifications    通知中心
-- =============================================================================


-- =============================================================================
-- A. 表 & 列注释（全部 19 张表）
-- =============================================================================

-- suppliers -------------------------------------------------------------------
COMMENT ON TABLE  suppliers              IS '供应商主档（含材料方 + 加工方，tenant 表的 supplier_id 引用这里）';
COMMENT ON COLUMN suppliers.name         IS '公司全名（唯一）';
COMMENT ON COLUMN suppliers.category     IS '主营类别：模架 / 全加工零件 / 快丝 / 慢丝 / 热处理 / 钣金 等';
COMMENT ON COLUMN suppliers.rating       IS '综合评分 0.00-5.00（历史订单满意度）';

-- tenants ---------------------------------------------------------------------
COMMENT ON TABLE  tenants                IS '租户表：三种视角 internal（我方） / processor（加工方） / material（材料方）';
COMMENT ON COLUMN tenants.tenant_type    IS 'internal / processor / material';
COMMENT ON COLUMN tenants.supplier_id    IS '若 processor/material 类型，关联 suppliers.id';

-- users -----------------------------------------------------------------------
COMMENT ON TABLE  users                  IS '用户账号（登录凭证 + 角色）';
COMMENT ON COLUMN users.tenant_id        IS '所属租户';
COMMENT ON COLUMN users.role             IS '我方角色：admin / production_manager / purchasing_manager / project_manager / quality_manager / technical_director；加工/材料方：operator';
COMMENT ON COLUMN users.password_hash    IS 'bcrypt cost=12';

-- projects --------------------------------------------------------------------
COMMENT ON TABLE  projects               IS '项目主档（一个项目可包含多个零件，最终导出一套模具/订单）';
COMMENT ON COLUMN projects.project_no    IS '项目编号，命名规范：<租户前缀><YY>-<4位序号>，例 M26-0013 = 瑞利捷/2026年/第13个';
COMMENT ON COLUMN projects.status        IS 'drafted 草稿 / confirmed 确认 / deciding 决策中 / decided 决策完成 / completed / cancelled';
COMMENT ON COLUMN projects.unit_price    IS '客户确认的单件报价（元）';
COMMENT ON COLUMN projects.deadline      IS '客户要求交付日期';

-- project_parts ---------------------------------------------------------------
COMMENT ON TABLE  project_parts          IS '项目零件清单：一个项目包含 N 个零件（每零件下面再有多道工序）';
COMMENT ON COLUMN project_parts.part_no  IS '零件号，项目内唯一。规范：<类型>-<2位序>，例 die-02（模芯第 2 件）、part-01（普通件第 1 件）、ins-03（镶件第 3 件）';
COMMENT ON COLUMN project_parts.material IS '材质：如 45# / Cr12MoV / SKD61 / S136';
COMMENT ON COLUMN project_parts.qty      IS '该零件数量';
COMMENT ON COLUMN project_parts.processes_json IS '【已废弃，历史字段】早期工序存这里；新版使用 project_processes 表';
COMMENT ON COLUMN project_parts.spec     IS '规格/尺寸文字说明';

-- attachments -----------------------------------------------------------------
COMMENT ON TABLE  attachments            IS '通用附件表（图纸、报价单 PDF、质检报告等）';
COMMENT ON COLUMN attachments.related_type IS 'project / project_part / outsource_request / outsource_quotation / ...';
COMMENT ON COLUMN attachments.category   IS 'drawing 图纸 / report 报告 / quote_sheet 报价单';

-- supplier_capabilities -------------------------------------------------------
COMMENT ON TABLE  supplier_capabilities  IS '供应商工艺能力标签（用于委外候选匹配）';
COMMENT ON COLUMN supplier_capabilities.process_name IS '工艺名称，例 线割 / 热处理 / 磨 / 精铣（和 process_methods.name 对应）';

-- production_decisions --------------------------------------------------------
COMMENT ON TABLE  production_decisions   IS '生产决策行：每个零件 × 每道工序一行（AI 建议 + 人工最终拍板）';
COMMENT ON COLUMN production_decisions.ai_suggestion IS 'AI 建议：self_made 自制 / outsource 委外';
COMMENT ON COLUMN production_decisions.ai_source     IS 'rules 硬编码规则 / llm LLM / manual 人工';
COMMENT ON COLUMN production_decisions.is_forced     IS '是否强制委外（热处理/表面处理等）';
COMMENT ON COLUMN production_decisions.final_decision IS '人工最终决策';
COMMENT ON COLUMN production_decisions.status        IS 'pending_review 待审核 / reviewed 已审核 / submitted 已提交审批 / finalized 终审完成';
COMMENT ON COLUMN production_decisions.approval_task_id IS '关联 workflow_approval_tasks.id（批次级）';

-- outsource_requests ----------------------------------------------------------
COMMENT ON TABLE  outsource_requests     IS '委外询价单（从生产决策的 outsource 行聚合生成）';
COMMENT ON COLUMN outsource_requests.status IS 'draft / inviting 群发中 / comparing 比对 / pending_award 待采购经理选中标 / awarded 已中标 / cancelled';
COMMENT ON COLUMN outsource_requests.required_processes_json IS '所需工艺数组，例 ["热处理","线割"]';

-- outsource_request_invitations -----------------------------------------------
COMMENT ON TABLE  outsource_request_invitations IS '询价邀请（询价单 × 加工方多对多）';
COMMENT ON COLUMN outsource_request_invitations.invitation_status IS 'sent 已发 / quoted 已报价 / no_response 未响应 / cancelled';

-- outsource_quotations --------------------------------------------------------
COMMENT ON TABLE  outsource_quotations   IS '加工方针对询价邀请的报价（一邀请一报价）';

-- outsource_orders ------------------------------------------------------------
COMMENT ON TABLE  outsource_orders       IS '正式委外加工单（采购经理选中标后生成）';
COMMENT ON COLUMN outsource_orders.status IS 'awarded 已中标 / accepted 已接单 / producing 生产中 / delivered 已交货 / cancelled';
COMMENT ON COLUMN outsource_orders.order_no IS '加工单号：MO-YYYYMMDD-XXXXXX';

-- outsource_order_status_events -----------------------------------------------
COMMENT ON TABLE  outsource_order_status_events IS '加工单状态变更日志（审计用）';

-- workflow_* -------------------------------------------------------------------
COMMENT ON TABLE  workflow_definitions   IS '工作流声明式定义（按 key+version 版本化，MVP 暂不使用）';
COMMENT ON TABLE  workflow_instances     IS '工作流实例（MVP 暂不使用）';
COMMENT ON TABLE  workflow_node_executions IS '工作流节点执行记录（MVP 暂不使用）';
COMMENT ON TABLE  workflow_approval_records IS '审批动作历史（append-only；MVP 使用）';
COMMENT ON COLUMN workflow_approval_records.action IS 'submit 提交 / approve 同意 / reject 拒绝 / withdraw 撤销 / delegate 委托 / ...';
COMMENT ON TABLE  workflow_approval_tasks IS '审批待办（MVP 使用；一个业务事件一条）';
COMMENT ON COLUMN workflow_approval_tasks.node_id IS 'MVP 里承载业务类型+主体，例 production_decision:12 或 outsource_award:5';
COMMENT ON TABLE  workflow_state_events  IS '状态变更事件（审计用）';


-- =============================================================================
-- B. 命名规范支持 — 给 projects 加租户序号列
-- =============================================================================
ALTER TABLE projects ADD COLUMN IF NOT EXISTS tenant_seq     INTEGER;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS year_suffix    CHAR(2);

COMMENT ON COLUMN projects.tenant_seq   IS '租户内 年内 自增序号（用于 M26-<tenant_seq:04d> 编号生成）';
COMMENT ON COLUMN projects.year_suffix  IS '两位年份（如 26）';

-- 租户内、同一年内 tenant_seq 唯一（NULL 不冲突，老数据兼容）
CREATE UNIQUE INDEX IF NOT EXISTS uk_projects_tenant_year_seq
    ON projects (tenant_id, year_suffix, tenant_seq)
    WHERE tenant_seq IS NOT NULL;


-- =============================================================================
-- C1. process_methods — 加工方式字典
-- =============================================================================
CREATE TABLE IF NOT EXISTS process_methods (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(32) NOT NULL UNIQUE,    -- 精铣 / 粗铣 / 钻孔 / 磨 / 车 / 线割 ...
    category      VARCHAR(32) NOT NULL,           -- cutting 切削 / heat 热处理 / surface 表面处理 / edm 电火花 / grinding 磨削
    is_internal_capable BOOLEAN NOT NULL DEFAULT TRUE,  -- 公司是否具备该工艺能力（热处理/表面处理 = FALSE）
    remark        VARCHAR(255),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE  process_methods        IS '加工方式字典（项目工序的 method_name 从此处取）';
COMMENT ON COLUMN process_methods.category   IS 'cutting 切削 / grinding 磨削 / edm 电火花线割 / heat 热处理 / surface 表面处理';
COMMENT ON COLUMN process_methods.is_internal_capable IS '公司自身是否具备该能力（FALSE 即默认强制委外）';

-- 初始化字典数据
INSERT INTO process_methods (name, category, is_internal_capable) VALUES
  ('精铣',  'cutting',  TRUE),
  ('粗铣',  'cutting',  TRUE),
  ('铣',    'cutting',  TRUE),
  ('车',    'cutting',  TRUE),
  ('钻孔',  'cutting',  TRUE),
  ('镗',    'cutting',  TRUE),
  ('磨',    'grinding', TRUE),
  ('小磨床','grinding', TRUE),
  ('线割',  'edm',      FALSE),
  ('快丝',  'edm',      FALSE),
  ('中丝',  'edm',      FALSE),
  ('慢丝',  'edm',      FALSE),
  ('热处理','heat',     FALSE),
  ('表面处理','surface',FALSE),
  ('抛光',  'surface',  FALSE)
ON CONFLICT (name) DO UPDATE SET
  category = EXCLUDED.category,
  is_internal_capable = EXCLUDED.is_internal_capable;


-- =============================================================================
-- C2. roles — 内部角色字典
-- =============================================================================
CREATE TABLE IF NOT EXISTS roles (
    code          VARCHAR(32) PRIMARY KEY,        -- ADMIN / PRODUCTION_MANAGER / ...
    name          VARCHAR(64) NOT NULL,
    description   VARCHAR(255),
    tenant_type   VARCHAR(32) NOT NULL DEFAULT 'internal',
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE  roles                  IS '角色字典（和 users.role 对应；MVP 只用 internal 租户的角色）';
COMMENT ON COLUMN roles.code             IS '代码，大写下划线，例 PRODUCTION_MANAGER';

INSERT INTO roles (code, name, description, tenant_type) VALUES
  ('ADMIN',              '管理员',       '最高权限，系统管理员',              'internal'),
  ('PROJECT_MANAGER',    '项目经理',     '项目立项、图纸和 BOM 录入',         'internal'),
  ('PURCHASING_MANAGER', '采购经理',     '委外中标审批、对账审核',            'internal'),
  ('PRODUCTION_MANAGER', '生产经理',     '生产决策审批、自制工序派工',        'internal'),
  ('QUALITY_MANAGER',    '质检主管',     '质检录入、异常责任判定',            'internal'),
  ('TECHNICAL_DIRECTOR', '技术总监',     '重大决策终审',                      'internal'),
  ('OPERATOR',           '操作员',       '加工方 / 材料方默认角色',           'processor')
ON CONFLICT (code) DO UPDATE SET
  name = EXCLUDED.name,
  description = EXCLUDED.description;


-- =============================================================================
-- C3. project_processes — 工序清单（每零件 × 每工序一行）
-- =============================================================================
CREATE TABLE IF NOT EXISTS project_processes (
    id             SERIAL PRIMARY KEY,
    project_id     INTEGER NOT NULL REFERENCES projects(id)      ON DELETE CASCADE,
    part_id        INTEGER NOT NULL REFERENCES project_parts(id) ON DELETE CASCADE,
    seq_no         INTEGER NOT NULL,                 -- 工序序号，零件内递增：1, 2, 3
    process_code   VARCHAR(64) NOT NULL,             -- 工序编号：P1-精铣-A / P2-钻孔 / P3-热处理（零件内唯一）
    method_name    VARCHAR(32) NOT NULL REFERENCES process_methods(name),  -- 加工方式（字典）
    faces          VARCHAR(16),                      -- 涉及的面，多个用逗号：A,B,C 或留空（NULL/"")
    notes          TEXT,
    est_hours      DECIMAL(8,2),                     -- 预估加工工时（小时）
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_proc_part_seq UNIQUE (part_id, seq_no),
    CONSTRAINT uk_proc_part_code UNIQUE (part_id, process_code)
);
CREATE INDEX IF NOT EXISTS idx_proc_project ON project_processes (project_id);
CREATE INDEX IF NOT EXISTS idx_proc_method  ON project_processes (method_name);

DROP TRIGGER IF EXISTS tr_proc_updated_at ON project_processes;
CREATE TRIGGER tr_proc_updated_at BEFORE UPDATE ON project_processes
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE  project_processes      IS '项目工序清单（每零件每工序一行，是决策和委外的最小粒度单位）';
COMMENT ON COLUMN project_processes.seq_no       IS '工序序号（零件内从 1 开始递增）';
COMMENT ON COLUMN project_processes.process_code IS '工序编号，规范 P<seq>-<method>[-<faces>]，例 P1-精铣-A,B 或 P3-热处理';
COMMENT ON COLUMN project_processes.method_name  IS '加工方式（引用 process_methods.name）';
COMMENT ON COLUMN project_processes.faces        IS '涉及零件的哪些面（A-F，多个逗号分隔；非有面工序留空）';


-- =============================================================================
-- C4. notifications — 通知中心
-- =============================================================================
CREATE TABLE IF NOT EXISTS notifications (
    id           BIGSERIAL PRIMARY KEY,
    tenant_id    INTEGER NOT NULL REFERENCES tenants(id),
    user_id      INTEGER,                            -- NULL = 全租户广播
    category     VARCHAR(32) NOT NULL,               -- approval 审批 / order 订单 / delay 延迟 / rework 补料 / system
    title        VARCHAR(255) NOT NULL,
    body         TEXT,
    link         VARCHAR(512),                       -- 点击跳转的相对路径（/static/internal/approvals.html?id=12）
    related_type VARCHAR(32),                        -- project / outsource_request / outsource_order / quality_exception
    related_id   INTEGER,
    is_read      BOOLEAN NOT NULL DEFAULT FALSE,
    read_at      TIMESTAMP,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_notif_user_unread ON notifications (user_id, is_read, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notif_tenant      ON notifications (tenant_id, is_read, created_at DESC);

COMMENT ON TABLE  notifications          IS '通知中心（系统内推送，user_id 为空表示该租户全员广播）';
COMMENT ON COLUMN notifications.category IS 'approval / order / delay / rework / system';


-- =============================================================================
-- 完成校验
-- =============================================================================
SELECT
  (SELECT COUNT(*) FROM process_methods) AS process_methods,
  (SELECT COUNT(*) FROM roles)           AS roles,
  (SELECT COUNT(*) FROM information_schema.tables
     WHERE table_schema='public'
       AND table_name IN ('process_methods','roles','project_processes','notifications')) AS new_tables;
-- 期望：process_methods=15, roles=7, new_tables=4
