-- =============================================================================
-- Migration 005: 完善需求文档里剩余的 15 张表（基础数据/自制/质检/对账/看板）
-- =============================================================================
-- 执行方式：
--   psql -h localhost -p 5432 -U postgres -d weiwai -f backend/migrations/postgres/005_full_domain.sql
-- =============================================================================


-- =============================================================================
-- 组 1 — 基础数据库域
-- =============================================================================

-- 1.1 material_prices  原料价格库（带有效期，过期提醒）
CREATE TABLE IF NOT EXISTS material_prices (
    id                SERIAL PRIMARY KEY,
    material_code     VARCHAR(64)  NOT NULL,       -- 例 Cr12MoV / 45# / SKD61
    material_name     VARCHAR(128) NOT NULL,
    spec              VARCHAR(128),                 -- 规格 例 φ50*1000
    unit              VARCHAR(16)  NOT NULL DEFAULT 'kg',
    unit_price        DECIMAL(14,2) NOT NULL,
    supplier_id       INTEGER REFERENCES suppliers(id),
    currency          CHAR(3) NOT NULL DEFAULT 'CNY',
    valid_from        DATE NOT NULL,
    valid_to          DATE,                         -- NULL 表示长期有效
    source            VARCHAR(32) DEFAULT 'manual', -- manual 手工 / api 第三方 / contract 合同价
    remark            TEXT,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_mat_price_key UNIQUE (material_code, spec, supplier_id, valid_from)
);
CREATE INDEX IF NOT EXISTS idx_mat_price_code   ON material_prices (material_code);
CREATE INDEX IF NOT EXISTS idx_mat_price_active ON material_prices (is_active, valid_to);
DROP TRIGGER IF EXISTS tr_mat_price_updated_at ON material_prices;
CREATE TRIGGER tr_mat_price_updated_at BEFORE UPDATE ON material_prices
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE  material_prices         IS '原料价格库（按材料+规格+供应商+生效日期唯一，过期需提醒）';
COMMENT ON COLUMN material_prices.valid_to IS '价格失效日期（NULL 表示长期有效，距离今天 <=15 天触发提醒）';
COMMENT ON COLUMN material_prices.source   IS 'manual 手工 / api 第三方 / contract 合同价';


-- 1.2 process_costs  工艺成本库（每工艺每供应商一条参考价）
CREATE TABLE IF NOT EXISTS process_costs (
    id             SERIAL PRIMARY KEY,
    method_name    VARCHAR(32) NOT NULL REFERENCES process_methods(name),
    supplier_id    INTEGER REFERENCES suppliers(id),
    cost_type      VARCHAR(16) NOT NULL DEFAULT 'per_hour',   -- per_hour / per_piece / per_face
    unit_cost      DECIMAL(14,2) NOT NULL,
    est_time_hours DECIMAL(8,2),                               -- 参考工时
    valid_from     DATE NOT NULL,
    valid_to       DATE,
    notes          TEXT,
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_pcost_method_sup UNIQUE (method_name, supplier_id, cost_type, valid_from)
);
CREATE INDEX IF NOT EXISTS idx_pcost_method ON process_costs (method_name);
DROP TRIGGER IF EXISTS tr_pcost_updated_at ON process_costs;
CREATE TRIGGER tr_pcost_updated_at BEFORE UPDATE ON process_costs
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE  process_costs           IS '工艺成本库（参考价，供 AI 估算和报价比对）';
COMMENT ON COLUMN process_costs.cost_type IS 'per_hour 按小时 / per_piece 按件 / per_face 按面';
COMMENT ON COLUMN process_costs.supplier_id IS 'NULL 表示市场价/内部参考价，有值表示该供应商合同价';


-- 1.3 equipment_capacity  设备产能台账（判断我方能否自制）
CREATE TABLE IF NOT EXISTS equipment_capacity (
    id                SERIAL PRIMARY KEY,
    equipment_code    VARCHAR(64) NOT NULL UNIQUE,
    equipment_name    VARCHAR(128) NOT NULL,
    method_name       VARCHAR(32)  NOT NULL REFERENCES process_methods(name),
    max_workpiece_dim VARCHAR(64),                  -- 最大加工尺寸 例 "600x400x200"
    precision_grade   VARCHAR(16),                  -- IT5/IT6/IT7 ...
    daily_hours       DECIMAL(5,2) NOT NULL DEFAULT 16,  -- 日产能（小时）
    occupied_hours    DECIMAL(8,2) NOT NULL DEFAULT 0,   -- 已占用工时（滚动）
    is_available      BOOLEAN NOT NULL DEFAULT TRUE,
    notes             TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_eq_method ON equipment_capacity (method_name);
DROP TRIGGER IF EXISTS tr_eq_updated_at ON equipment_capacity;
CREATE TRIGGER tr_eq_updated_at BEFORE UPDATE ON equipment_capacity
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE  equipment_capacity IS '设备产能台账（判断我方是否具备某工艺能力的依据）';


-- 1.4 moq_rules  MOQ 规则（最小起订量 + 余量入库策略）
CREATE TABLE IF NOT EXISTS moq_rules (
    id             SERIAL PRIMARY KEY,
    material_code  VARCHAR(64) NOT NULL,
    spec           VARCHAR(128),
    supplier_id    INTEGER REFERENCES suppliers(id),
    min_qty        INTEGER NOT NULL,
    multiple_of    INTEGER NOT NULL DEFAULT 1,     -- 必须是 N 的倍数起订
    unit           VARCHAR(16) DEFAULT 'kg',
    surplus_policy VARCHAR(16) NOT NULL DEFAULT 'stock',  -- stock 入库 / return 退回 / waste 作废
    notes          TEXT,
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
DROP TRIGGER IF EXISTS tr_moq_updated_at ON moq_rules;
CREATE TRIGGER tr_moq_updated_at BEFORE UPDATE ON moq_rules
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE  moq_rules               IS 'MOQ 规则（最小起订量 + 余量去向策略）';
COMMENT ON COLUMN moq_rules.surplus_policy IS 'stock 入库当余量 / return 退回供应商 / waste 作废';


-- 1.5 inventory  库存（含 MOQ 余量虚拟入库）
CREATE TABLE IF NOT EXISTS inventory (
    id                 SERIAL PRIMARY KEY,
    material_code      VARCHAR(64) NOT NULL,
    spec               VARCHAR(128),
    batch_no           VARCHAR(64),
    qty                DECIMAL(14,2) NOT NULL,
    unit               VARCHAR(16) DEFAULT 'kg',
    inventory_type     VARCHAR(16) NOT NULL DEFAULT 'normal',  -- normal 正常 / moq_surplus MOQ 余量 / rework_return 异常退料
    source_type        VARCHAR(32),                             -- material_shipment / rework_order / ...
    source_id          INTEGER,
    warehouse_location VARCHAR(64),
    status             VARCHAR(16) NOT NULL DEFAULT 'available', -- available / reserved / consumed
    in_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    out_at             TIMESTAMP,
    remark             TEXT,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_inv_material ON inventory (material_code, status);
CREATE INDEX IF NOT EXISTS idx_inv_type     ON inventory (inventory_type, status);
DROP TRIGGER IF EXISTS tr_inv_updated_at ON inventory;
CREATE TRIGGER tr_inv_updated_at BEFORE UPDATE ON inventory
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE  inventory              IS '库存（包含正常库存 + MOQ 余量虚拟库存；新订单优先消耗 moq_surplus）';
COMMENT ON COLUMN inventory.inventory_type IS 'normal 正常 / moq_surplus MOQ余量 / rework_return 异常退料返库';


-- =============================================================================
-- 组 2 — 自制分支（生产单 + 材料采购 + 材料方发货）
-- =============================================================================

-- 2.1 internal_production_orders  自制生产单
CREATE TABLE IF NOT EXISTS internal_production_orders (
    id              SERIAL PRIMARY KEY,
    order_no        VARCHAR(64) NOT NULL UNIQUE,     -- IP-M26-0013-die02-P1-01
    project_id      INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    mold_id         INTEGER REFERENCES molds(id),
    part_id         INTEGER NOT NULL REFERENCES project_parts(id),
    process_id      INTEGER REFERENCES project_processes(id),
    face_ids        INTEGER[],                       -- 面级可选
    equipment_id    INTEGER REFERENCES equipment_capacity(id),
    assignee_user_id INTEGER REFERENCES users(id),
    qty             INTEGER NOT NULL DEFAULT 1,
    status          VARCHAR(32) NOT NULL DEFAULT 'pending',
       -- pending / material_ready / producing / finished / cancelled
    planned_start   DATE,
    planned_end     DATE,
    started_at      TIMESTAMP,
    finished_at     TIMESTAMP,
    remark          TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ipo_project ON internal_production_orders (project_id);
CREATE INDEX IF NOT EXISTS idx_ipo_status  ON internal_production_orders (status);
DROP TRIGGER IF EXISTS tr_ipo_updated_at ON internal_production_orders;
CREATE TRIGGER tr_ipo_updated_at BEFORE UPDATE ON internal_production_orders
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE  internal_production_orders IS '自制生产单（生产决策 final_decision=self_made 时生成）';
COMMENT ON COLUMN internal_production_orders.order_no IS '规范：IP-<项目号>-<零件号>-<工序号>-<2位序>';


-- 2.2 material_purchase_orders  给材料方的采购订单
CREATE TABLE IF NOT EXISTS material_purchase_orders (
    id              SERIAL PRIMARY KEY,
    po_no           VARCHAR(64) NOT NULL UNIQUE,     -- MP-M26-0013-01
    project_id      INTEGER NOT NULL REFERENCES projects(id),
    mold_id         INTEGER REFERENCES molds(id),
    supplier_id     INTEGER NOT NULL REFERENCES suppliers(id),  -- 材料方
    tenant_id       INTEGER REFERENCES tenants(id),
    material_code   VARCHAR(64) NOT NULL,
    spec            VARCHAR(128),
    qty             DECIMAL(14,2) NOT NULL,
    unit            VARCHAR(16) DEFAULT 'kg',
    unit_price      DECIMAL(14,2),
    total_amount    DECIMAL(14,2),
    required_date   DATE,
    status          VARCHAR(32) NOT NULL DEFAULT 'drafted',
       -- drafted 草稿 / sent 已下单 / accepted 已接单 / shipped 已发货 / received 已收货 / cancelled
    created_by      INTEGER REFERENCES users(id),
    moq_surplus_qty DECIMAL(14,2) DEFAULT 0,         -- 触发 MOQ 余量后多买的数量
    remark          TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_mpo_project ON material_purchase_orders (project_id);
CREATE INDEX IF NOT EXISTS idx_mpo_supplier ON material_purchase_orders (supplier_id, status);
CREATE INDEX IF NOT EXISTS idx_mpo_tenant  ON material_purchase_orders (tenant_id, status);
DROP TRIGGER IF EXISTS tr_mpo_updated_at ON material_purchase_orders;
CREATE TRIGGER tr_mpo_updated_at BEFORE UPDATE ON material_purchase_orders
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE  material_purchase_orders IS '给材料方的采购单（材料方视角能看到的订单）';
COMMENT ON COLUMN material_purchase_orders.moq_surplus_qty IS '超出需求的余量数量（MOQ 触发），交付后进 inventory.moq_surplus';


-- 2.3 material_shipments  材料方发货记录（含异常补料标识）
CREATE TABLE IF NOT EXISTS material_shipments (
    id              SERIAL PRIMARY KEY,
    shipment_no     VARCHAR(64) NOT NULL UNIQUE,
    po_id           INTEGER NOT NULL REFERENCES material_purchase_orders(id),
    qty_shipped     DECIMAL(14,2) NOT NULL,
    batch_no        VARCHAR(64),
    carrier         VARCHAR(64),
    tracking_no     VARCHAR(64),
    photo_paths     TEXT[],                          -- 多张备料/发货照片路径
    shipped_at      TIMESTAMP,
    received_at     TIMESTAMP,
    is_rework       BOOLEAN NOT NULL DEFAULT FALSE,  -- 是否为"异常补料"发货
    rework_order_id INTEGER,                         -- 若是补料，关联 rework_orders
    status          VARCHAR(32) NOT NULL DEFAULT 'preparing',
       -- preparing 备料中 / shipped 已发 / received 已收 / returned 已退
    remark          TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ship_po ON material_shipments (po_id);
CREATE INDEX IF NOT EXISTS idx_ship_rework ON material_shipments (is_rework, status);
DROP TRIGGER IF EXISTS tr_ship_updated_at ON material_shipments;
CREATE TRIGGER tr_ship_updated_at BEFORE UPDATE ON material_shipments
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE  material_shipments         IS '材料方发货记录（含异常补料标识 is_rework）';
COMMENT ON COLUMN material_shipments.is_rework IS 'TRUE 表示这是异常补料发货（对账时会被特殊标记）';


-- =============================================================================
-- 组 3 — 质检 + 异常处理
-- =============================================================================

-- 3.1 inspections  质检记录
CREATE TABLE IF NOT EXISTS inspections (
    id                SERIAL PRIMARY KEY,
    inspection_no     VARCHAR(64) NOT NULL UNIQUE,
    project_id        INTEGER NOT NULL REFERENCES projects(id),
    part_id           INTEGER REFERENCES project_parts(id),
    process_id        INTEGER REFERENCES project_processes(id),
    subject_type      VARCHAR(32) NOT NULL,            -- material 材料 / internal_production 自制 / outsource 外协 / final 成品
    subject_id        INTEGER,                         -- 指向来源单据
    inspector_id      INTEGER REFERENCES users(id),
    result            VARCHAR(16),                     -- pass 合格 / fail 不合格 / concession 让步接收
    sample_qty        INTEGER,
    defect_qty        INTEGER DEFAULT 0,
    defect_type       VARCHAR(64),                     -- 尺寸超差 / 划伤 / 热处理不均 / ...
    exception_id      INTEGER,                         -- 若 fail，关联 quality_exceptions.id
    photo_paths       TEXT[],
    notes             TEXT,
    inspected_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_insp_project ON inspections (project_id);
CREATE INDEX IF NOT EXISTS idx_insp_result  ON inspections (result);

COMMENT ON TABLE  inspections            IS '质检记录（异常的唯一触发入口）';
COMMENT ON COLUMN inspections.subject_type IS 'material 原料 / internal_production 自制 / outsource 外协 / final 成品';
COMMENT ON COLUMN inspections.result     IS 'pass 合格 / fail 不合格 / concession 让步接收';


-- 3.2 quality_exceptions  质量异常主表
CREATE TABLE IF NOT EXISTS quality_exceptions (
    id                SERIAL PRIMARY KEY,
    exception_no      VARCHAR(64) NOT NULL UNIQUE,    -- QE-M26-0013-01
    inspection_id     INTEGER REFERENCES inspections(id),
    project_id        INTEGER NOT NULL REFERENCES projects(id),
    part_id           INTEGER REFERENCES project_parts(id),
    process_id        INTEGER REFERENCES project_processes(id),
    severity          VARCHAR(16) NOT NULL DEFAULT 'medium',  -- low / medium / high / critical
    exception_type    VARCHAR(64),                    -- 尺寸超差/外观缺陷/热处理硬度/材料批次...
    description       TEXT,
    ai_analysis_json  JSONB,                          -- ExceptionAgent 的溯因报告
    status            VARCHAR(32) NOT NULL DEFAULT 'pending_analysis',
       -- pending_analysis / ai_analyzed / responsibility_confirmed / resolved / closed / cancelled
    resolution_path   VARCHAR(32),                    -- rework_material 退换料 / rework_process 重工 / concession 让步 / claim 索赔
    created_by        INTEGER REFERENCES users(id),
    confirmed_by      INTEGER REFERENCES users(id),
    confirmed_at      TIMESTAMP,
    resolved_at       TIMESTAMP,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_qe_project ON quality_exceptions (project_id);
CREATE INDEX IF NOT EXISTS idx_qe_status  ON quality_exceptions (status);
DROP TRIGGER IF EXISTS tr_qe_updated_at ON quality_exceptions;
CREATE TRIGGER tr_qe_updated_at BEFORE UPDATE ON quality_exceptions
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE  quality_exceptions     IS '质量异常主表（从 inspections 触发，由 ExceptionAgent 分析）';
COMMENT ON COLUMN quality_exceptions.status IS 'pending_analysis 待分析 / ai_analyzed AI完成 / responsibility_confirmed 责任确认 / resolved 已处理 / closed / cancelled';
COMMENT ON COLUMN quality_exceptions.resolution_path IS 'rework_material 退换料(材料方) / rework_process 重工(加工方) / concession 让步 / claim 索赔';


-- 3.3 exception_evidence  异常证据包
CREATE TABLE IF NOT EXISTS exception_evidence (
    id            SERIAL PRIMARY KEY,
    exception_id  INTEGER NOT NULL REFERENCES quality_exceptions(id) ON DELETE CASCADE,
    evidence_type VARCHAR(32) NOT NULL,   -- drawing 图纸 / inspection_report 质检报告 / photo 照片 / waybill 运单 / iqc_report / other
    attachment_id INTEGER REFERENCES attachments(id),
    description   TEXT,
    source        VARCHAR(32),            -- auto_collected / manual_upload / ai_linked
    created_by    INTEGER REFERENCES users(id),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ee_exception ON exception_evidence (exception_id);

COMMENT ON TABLE  exception_evidence      IS '异常证据包（图纸/质检/照片/运单，支撑 AI 定责）';


-- 3.4 exception_responsibility  异常责任判定
CREATE TABLE IF NOT EXISTS exception_responsibility (
    id            SERIAL PRIMARY KEY,
    exception_id  INTEGER NOT NULL REFERENCES quality_exceptions(id) ON DELETE CASCADE,
    responsible_party VARCHAR(32) NOT NULL,  -- material_supplier / processor / internal / customer / shared
    responsible_tenant_id INTEGER REFERENCES tenants(id),
    responsibility_ratio  DECIMAL(5,2),      -- 百分比 0-100（shared 时多条）
    reason        TEXT,
    ai_suggested  BOOLEAN DEFAULT FALSE,
    confirmed_by  INTEGER REFERENCES users(id),
    confirmed_at  TIMESTAMP,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_er_exception ON exception_responsibility (exception_id);

COMMENT ON TABLE  exception_responsibility IS '异常责任判定（一异常可多条记录，shared 情形按比例分摊）';
COMMENT ON COLUMN exception_responsibility.responsible_party IS 'material_supplier 材料方 / processor 加工方 / internal 我方 / customer 客户 / shared 共担';


-- 3.5 rework_orders  重发料单（异常补料，强制打标）
CREATE TABLE IF NOT EXISTS rework_orders (
    id              SERIAL PRIMARY KEY,
    rework_no       VARCHAR(64) NOT NULL UNIQUE,
    exception_id    INTEGER NOT NULL REFERENCES quality_exceptions(id),
    project_id      INTEGER NOT NULL REFERENCES projects(id),
    rework_type     VARCHAR(16) NOT NULL,     -- material 材料补发 / process 重工 / return 退货
    original_po_id  INTEGER REFERENCES material_purchase_orders(id),
    original_order_id INTEGER REFERENCES outsource_orders(id),
    new_po_id       INTEGER REFERENCES material_purchase_orders(id),
    new_order_id    INTEGER REFERENCES outsource_orders(id),
    qty             DECIMAL(14,2),
    status          VARCHAR(32) NOT NULL DEFAULT 'pending',
       -- pending / in_progress / completed / cancelled
    is_chargeable   BOOLEAN NOT NULL DEFAULT TRUE,   -- 是否计入对账扣减
    created_by      INTEGER REFERENCES users(id),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_rework_project ON rework_orders (project_id);
DROP TRIGGER IF EXISTS tr_rework_updated_at ON rework_orders;
CREATE TRIGGER tr_rework_updated_at BEFORE UPDATE ON rework_orders
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE  rework_orders           IS '重发料单（补料/重工/退货，对账时自动扣减）';
COMMENT ON COLUMN rework_orders.rework_type IS 'material 材料补发 / process 重工 / return 退货';


-- =============================================================================
-- 组 4 — 对账
-- =============================================================================

-- 4.1 reconciliations  对账主表
CREATE TABLE IF NOT EXISTS reconciliations (
    id              SERIAL PRIMARY KEY,
    recon_no        VARCHAR(64) NOT NULL UNIQUE,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id),  -- 材料方 or 加工方租户
    period_from     DATE NOT NULL,
    period_to       DATE NOT NULL,
    total_amount    DECIMAL(14,2) NOT NULL DEFAULT 0,
    deduction_amount DECIMAL(14,2) NOT NULL DEFAULT 0,        -- 异常扣减合计
    net_amount      DECIMAL(14,2) NOT NULL DEFAULT 0,
    status          VARCHAR(32) NOT NULL DEFAULT 'drafted',
       -- drafted / submitted 等确认 / confirmed 对方已确认 / disputed / settled
    created_by      INTEGER REFERENCES users(id),
    confirmed_at    TIMESTAMP,
    settled_at      TIMESTAMP,
    remark          TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_recon_tenant ON reconciliations (tenant_id, status);
DROP TRIGGER IF EXISTS tr_recon_updated_at ON reconciliations;
CREATE TRIGGER tr_recon_updated_at BEFORE UPDATE ON reconciliations
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE  reconciliations         IS '对账单（按租户 + 周期）';


-- 4.2 reconciliation_items  对账明细
CREATE TABLE IF NOT EXISTS reconciliation_items (
    id              SERIAL PRIMARY KEY,
    reconciliation_id INTEGER NOT NULL REFERENCES reconciliations(id) ON DELETE CASCADE,
    source_type     VARCHAR(32) NOT NULL,      -- material_po / material_shipment / outsource_order / rework_order
    source_id       INTEGER NOT NULL,
    item_type       VARCHAR(16) NOT NULL,      -- charge 应付 / deduction 扣减
    description     TEXT,
    amount          DECIMAL(14,2) NOT NULL,
    related_exception_id INTEGER REFERENCES quality_exceptions(id),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_recon_item_recon ON reconciliation_items (reconciliation_id);

COMMENT ON TABLE  reconciliation_items    IS '对账明细（charge 应付 + deduction 扣减）';
COMMENT ON COLUMN reconciliation_items.item_type IS 'charge 应付 / deduction 异常扣减';


-- =============================================================================
-- 组 5 — 全流程看板（10 节点追踪）
-- =============================================================================

-- 5.1 workflow_tracking  流程节点状态追踪
CREATE TABLE IF NOT EXISTS workflow_tracking (
    id             SERIAL PRIMARY KEY,
    project_id     INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    node_code      VARCHAR(32) NOT NULL,
       -- 10 节点：drafting / confirmed / deciding / decided / purchasing / producing / outsourcing / inspecting / exception / delivered
    node_name      VARCHAR(64) NOT NULL,
    node_order     INTEGER NOT NULL,          -- 1..10
    status         VARCHAR(16) NOT NULL DEFAULT 'pending',
       -- pending / in_progress / done / skipped / blocked / on_hold
    started_at     TIMESTAMP,
    ended_at       TIMESTAMP,
    duration_hours DECIMAL(8,2),
    is_blocking    BOOLEAN DEFAULT FALSE,
    blocker_reason TEXT,
    actor_user_id  INTEGER REFERENCES users(id),
    remark         TEXT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_wft_project_node UNIQUE (project_id, node_code)
);
CREATE INDEX IF NOT EXISTS idx_wft_project ON workflow_tracking (project_id, node_order);
DROP TRIGGER IF EXISTS tr_wft_updated_at ON workflow_tracking;
CREATE TRIGGER tr_wft_updated_at BEFORE UPDATE ON workflow_tracking
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE  workflow_tracking        IS '流程追踪（每项目 10 节点，支持挂起/跳转/备注，全流程看板的数据源）';
COMMENT ON COLUMN workflow_tracking.node_code IS 'drafting 草稿 / confirmed 确认 / deciding 决策中 / decided 决策完 / purchasing 采购 / producing 生产 / outsourcing 外协 / inspecting 质检 / exception 异常 / delivered 交付';


-- =============================================================================
-- 完成校验
-- =============================================================================
SELECT
  (SELECT COUNT(*) FROM information_schema.tables
     WHERE table_schema='public'
       AND table_name IN (
         'material_prices','process_costs','equipment_capacity','moq_rules','inventory',
         'internal_production_orders','material_purchase_orders','material_shipments',
         'inspections','quality_exceptions','exception_evidence','exception_responsibility','rework_orders',
         'reconciliations','reconciliation_items',
         'workflow_tracking'
       )
  ) AS new_tables_created,
  (SELECT COUNT(*) FROM information_schema.tables
     WHERE table_schema='public') AS total_tables;
-- 期望：new_tables_created=16, total_tables=39
