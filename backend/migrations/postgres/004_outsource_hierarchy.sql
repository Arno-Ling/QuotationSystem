-- =============================================================================
-- Migration 004: 5 层委外粒度（项目 → 模具 → 零件 → 工序 → 面）
-- =============================================================================
-- 目的：让任何层级都能作为委外对象，加工方按项报价，采购经理按项选中标。
--
-- 层级链：
--   projects ─→ molds ─→ project_parts ─→ project_processes ─→ process_faces
--
-- 委外五种粒度 scope_level：
--   project  : 整项目打包委外     (request 下 1 项：project_id)
--   mold     : 一套模具打包委外   (project_id + mold_id)
--   part     : 单个零件所有工序   (part_id)
--   method   : 某零件某道工序     (part_id + process_id)
--   face     : 工序里的部分面     (part_id + process_id + face_ids[])
-- =============================================================================


-- =============================================================================
-- 1. molds — 模具套
-- =============================================================================
CREATE TABLE IF NOT EXISTS molds (
    id           SERIAL PRIMARY KEY,
    project_id   INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    mold_no      VARCHAR(64) NOT NULL UNIQUE,
        -- 命名规范：<project_no>-M<2 位序>  例 M26-0013-M01
    name         VARCHAR(255),
    sort_no      INTEGER,
        -- 项目内模具的排序号 (01..NN)
    status       VARCHAR(32) NOT NULL DEFAULT 'drafted',
    remark       TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_mold_project_sort UNIQUE (project_id, sort_no)
);
CREATE INDEX IF NOT EXISTS idx_mold_project ON molds (project_id);
DROP TRIGGER IF EXISTS tr_mold_updated_at ON molds;
CREATE TRIGGER tr_mold_updated_at BEFORE UPDATE ON molds
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE  molds            IS '模具套（一项目 N 套）— 可整套打包委外';
COMMENT ON COLUMN molds.mold_no    IS '命名规范：<project_no>-M<2 位序>，例 M26-0013-M01';
COMMENT ON COLUMN molds.sort_no    IS '项目内模具排序（1..N），用于自动生成 mold_no';
COMMENT ON COLUMN molds.status     IS 'drafted/producing/delivered/cancelled';


-- =============================================================================
-- 2. project_parts 改造 — 加 mold_id / part_type / sort_no
-- =============================================================================
ALTER TABLE project_parts
    ADD COLUMN IF NOT EXISTS mold_id   INTEGER REFERENCES molds(id) ON DELETE CASCADE;
ALTER TABLE project_parts
    ADD COLUMN IF NOT EXISTS part_type VARCHAR(16);
    -- die 模芯 / ins 镶件 / part 普通件 / frame 模架 / std 标准件
ALTER TABLE project_parts
    ADD COLUMN IF NOT EXISTS sort_no   INTEGER;
    -- 模具内排序（用于生成 part_no 的数字部分）

CREATE INDEX IF NOT EXISTS idx_parts_mold ON project_parts (mold_id);

COMMENT ON COLUMN project_parts.mold_id   IS '所属模具套（NULL 表示尚未分配，老数据）';
COMMENT ON COLUMN project_parts.part_type IS 'die 模芯 / ins 镶件 / part 普通件 / frame 模架 / std 标准件';
COMMENT ON COLUMN project_parts.sort_no   IS '模具内零件排序号（用于生成 die-02 中的 02）';


-- =============================================================================
-- 3. process_faces — 工序下的面清单
-- =============================================================================
CREATE TABLE IF NOT EXISTS process_faces (
    id          SERIAL PRIMARY KEY,
    process_id  INTEGER NOT NULL REFERENCES project_processes(id) ON DELETE CASCADE,
    face_label  CHAR(1) NOT NULL,
        -- A / B / C / D / E / F
    notes       TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT  uk_face_process_label UNIQUE (process_id, face_label),
    CONSTRAINT  ck_face_label CHECK (face_label IN ('A','B','C','D','E','F'))
);
CREATE INDEX IF NOT EXISTS idx_face_process ON process_faces (process_id);

COMMENT ON TABLE  process_faces IS '工序下的 6 面清单 (A-F)；没有面的工序（热处理等）不建行';
COMMENT ON COLUMN process_faces.face_label IS '面标识：A,B,C,D,E,F 之一';


-- =============================================================================
-- 4. project_processes 改造 — faces 列保留兼容；新逻辑走 process_faces 表
-- =============================================================================
COMMENT ON COLUMN project_processes.faces IS '【过渡字段】老数据或快速录入时用；结构化面请写入 process_faces 表';


-- =============================================================================
-- 5. outsource_scope_items — 委外项（核心）
-- =============================================================================
CREATE TABLE IF NOT EXISTS outsource_scope_items (
    id              SERIAL PRIMARY KEY,
    request_id      INTEGER NOT NULL REFERENCES outsource_requests(id) ON DELETE CASCADE,
    scope_level     VARCHAR(16) NOT NULL,
        -- project / mold / part / method / face
    project_id      INTEGER NOT NULL REFERENCES projects(id),
    mold_id         INTEGER REFERENCES molds(id),
    part_id         INTEGER REFERENCES project_parts(id),
    process_id      INTEGER REFERENCES project_processes(id),
    face_ids        INTEGER[],
        -- face 粒度时存 process_faces.id 数组
    quantity        INTEGER NOT NULL DEFAULT 1,
    description     TEXT,
    status          VARCHAR(32) NOT NULL DEFAULT 'draft',
        -- draft / sent / quoted / awarded / cancelled
    winning_quotation_line_id  INTEGER,
        -- 中标的报价明细行（outsource_quotation_lines.id）
    sort_no         INTEGER,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT ck_scope_level CHECK (scope_level IN ('project','mold','part','method','face')),
    -- project 级只需 project_id；mold 级需要 mold_id；part 级需要 part_id 等
    CONSTRAINT ck_scope_required CHECK (
        (scope_level = 'project' AND project_id IS NOT NULL) OR
        (scope_level = 'mold'    AND mold_id    IS NOT NULL) OR
        (scope_level = 'part'    AND part_id    IS NOT NULL) OR
        (scope_level = 'method'  AND part_id    IS NOT NULL AND process_id IS NOT NULL) OR
        (scope_level = 'face'    AND part_id    IS NOT NULL AND process_id IS NOT NULL
                                  AND face_ids  IS NOT NULL
                                  AND array_length(face_ids, 1) > 0)
    )
);
CREATE INDEX IF NOT EXISTS idx_sco_request  ON outsource_scope_items (request_id);
CREATE INDEX IF NOT EXISTS idx_sco_level    ON outsource_scope_items (scope_level);
CREATE INDEX IF NOT EXISTS idx_sco_part     ON outsource_scope_items (part_id);
CREATE INDEX IF NOT EXISTS idx_sco_mold     ON outsource_scope_items (mold_id);

DROP TRIGGER IF EXISTS tr_sco_updated_at ON outsource_scope_items;
CREATE TRIGGER tr_sco_updated_at BEFORE UPDATE ON outsource_scope_items
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

COMMENT ON TABLE  outsource_scope_items IS '委外项（一询价单 N 项）—支持 5 种粒度：项目/模具/零件/工序/面';
COMMENT ON COLUMN outsource_scope_items.scope_level  IS 'project/mold/part/method/face';
COMMENT ON COLUMN outsource_scope_items.face_ids     IS 'face 粒度时的 process_faces.id 数组';
COMMENT ON COLUMN outsource_scope_items.description  IS '该委外项的文字描述，便于加工方阅读（AI 自动生成或人工输入）';
COMMENT ON COLUMN outsource_scope_items.status       IS 'draft 草稿 / sent 发出 / quoted 有报价 / awarded 已中标 / cancelled';
COMMENT ON COLUMN outsource_scope_items.winning_quotation_line_id IS '中标的 outsource_quotation_lines.id';


-- =============================================================================
-- 6. outsource_quotation_lines — 报价明细（逐项报价）
-- =============================================================================
CREATE TABLE IF NOT EXISTS outsource_quotation_lines (
    id              SERIAL PRIMARY KEY,
    quotation_id    INTEGER NOT NULL REFERENCES outsource_quotations(id) ON DELETE CASCADE,
    scope_item_id   INTEGER NOT NULL REFERENCES outsource_scope_items(id) ON DELETE CASCADE,
    unit_price      DECIMAL(14,2) NOT NULL,
    lead_time_days  INTEGER NOT NULL,
    note            TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_qline_quote_item UNIQUE (quotation_id, scope_item_id)
);
CREATE INDEX IF NOT EXISTS idx_qline_quote ON outsource_quotation_lines (quotation_id);
CREATE INDEX IF NOT EXISTS idx_qline_item  ON outsource_quotation_lines (scope_item_id);

COMMENT ON TABLE  outsource_quotation_lines IS '报价明细行（一报价 N 行，对应 N 个委外项）';
COMMENT ON COLUMN outsource_quotation_lines.quotation_id  IS '所属报价（outsource_quotations）';
COMMENT ON COLUMN outsource_quotation_lines.scope_item_id IS '对应委外项';


-- =============================================================================
-- 7. outsource_orders 改造 — 加 scope_item_id
-- =============================================================================
ALTER TABLE outsource_orders
    ADD COLUMN IF NOT EXISTS scope_item_id     INTEGER REFERENCES outsource_scope_items(id);
ALTER TABLE outsource_orders
    ADD COLUMN IF NOT EXISTS quotation_line_id INTEGER REFERENCES outsource_quotation_lines(id);

CREATE INDEX IF NOT EXISTS idx_order_scope_item ON outsource_orders (scope_item_id);

COMMENT ON COLUMN outsource_orders.scope_item_id     IS '关联委外项（决定订单层级）';
COMMENT ON COLUMN outsource_orders.quotation_line_id IS '关联具体中标行（细粒度选中）';


-- =============================================================================
-- 8. production_decisions 改造 — 支持下沉到工序和面
-- =============================================================================
ALTER TABLE production_decisions
    ADD COLUMN IF NOT EXISTS process_id   INTEGER REFERENCES project_processes(id) ON DELETE CASCADE;
ALTER TABLE production_decisions
    ADD COLUMN IF NOT EXISTS face_ids     INTEGER[];
    -- face 粒度决策时存 process_faces.id 数组
ALTER TABLE production_decisions
    ADD COLUMN IF NOT EXISTS scope_level  VARCHAR(16) NOT NULL DEFAULT 'method';
    -- method / face（决策最小粒度目前到工序或面）

CREATE INDEX IF NOT EXISTS idx_dec_process ON production_decisions (process_id);

COMMENT ON COLUMN production_decisions.process_id  IS '决策针对哪道工序（project_processes.id）';
COMMENT ON COLUMN production_decisions.face_ids    IS 'face 粒度决策：process_faces.id 数组';
COMMENT ON COLUMN production_decisions.scope_level IS '决策粒度：method 工序级 / face 面级';


-- =============================================================================
-- 9. 辅助视图 — v_outsource_scope_display（给 UI 用，拼好全层级字符串）
-- =============================================================================
CREATE OR REPLACE VIEW v_outsource_scope_display AS
SELECT
    s.id                    AS scope_item_id,
    s.request_id,
    s.scope_level,
    s.quantity,
    s.status,
    s.description,
    p.project_no,
    p.name                  AS project_name,
    m.mold_no,
    m.name                  AS mold_name,
    pp.part_no,
    pp.part_name,
    pp.part_type,
    pr.process_code,
    pr.method_name,
    s.face_ids,
    -- 面标签聚合：把 face_ids 里的 face_label 拼成 "A,B"
    CASE
        WHEN s.scope_level = 'face' AND s.face_ids IS NOT NULL
        THEN (SELECT string_agg(pf.face_label, ',' ORDER BY pf.face_label)
              FROM process_faces pf WHERE pf.id = ANY(s.face_ids))
        ELSE NULL
    END AS face_labels,
    -- 层级描述：项目/模具/零件/工序/面 拼成一行
    CONCAT_WS(' / ',
        p.project_no,
        m.mold_no,
        CASE WHEN s.scope_level IN ('part','method','face') THEN pp.part_no END,
        CASE WHEN s.scope_level IN ('method','face')        THEN pr.process_code END,
        CASE WHEN s.scope_level = 'face'
             THEN 'FACE[' || (SELECT string_agg(pf.face_label, ',' ORDER BY pf.face_label)
                              FROM process_faces pf WHERE pf.id = ANY(s.face_ids)) || ']'
        END
    ) AS display_path
FROM outsource_scope_items s
JOIN projects p ON s.project_id = p.id
LEFT JOIN molds m  ON s.mold_id = m.id
LEFT JOIN project_parts pp ON s.part_id = pp.id
LEFT JOIN project_processes pr ON s.process_id = pr.id;

COMMENT ON VIEW v_outsource_scope_display IS 'UI 友好视图：把 5 层委外项渲染成 display_path 字符串';


-- =============================================================================
-- 完成校验
-- =============================================================================
SELECT
  (SELECT COUNT(*) FROM information_schema.tables
     WHERE table_schema='public'
       AND table_name IN ('molds','process_faces','outsource_scope_items','outsource_quotation_lines')) AS new_tables,
  (SELECT COUNT(*) FROM information_schema.columns
     WHERE table_schema='public' AND table_name='project_parts'
       AND column_name IN ('mold_id','part_type','sort_no')) AS project_parts_added,
  (SELECT COUNT(*) FROM information_schema.columns
     WHERE table_schema='public' AND table_name='production_decisions'
       AND column_name IN ('process_id','face_ids','scope_level')) AS decisions_added,
  (SELECT COUNT(*) FROM information_schema.columns
     WHERE table_schema='public' AND table_name='outsource_orders'
       AND column_name IN ('scope_item_id','quotation_line_id')) AS orders_added;
-- 期望：new_tables=4, project_parts_added=3, decisions_added=3, orders_added=2
