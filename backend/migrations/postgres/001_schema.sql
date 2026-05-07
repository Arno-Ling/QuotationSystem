-- =============================================================================
-- 模具委外采购系统 — PostgreSQL 建表脚本（weiwai 库）
-- =============================================================================
-- 使用方式：
--   1. 在 pgAdmin 或 psql 中连接 weiwai 数据库（postgres / 361615）
--   2. 直接执行本文件（pgAdmin 里 Query Tool → 粘贴/打开 → F5）
--   3. 验证：末尾的 SELECT 查询应列出 19 张表
--
-- 设计要点：
--   - AUTO_INCREMENT → SERIAL / BIGSERIAL
--   - TINYINT(1)     → BOOLEAN
--   - JSON           → JSONB
--   - BINARY(16)     → UUID
--   - DATETIME       → TIMESTAMP
--   - ON UPDATE CURRENT_TIMESTAMP → trigger 函数 trigger_set_updated_at
--   - MySQL 反引号 `key` → PG 双引号 "key"（关键字）
--
-- 表的创建顺序按依赖关系：
--   suppliers → tenants → users/projects → project_parts/attachments
--   → supplier_capabilities / production_decisions
--   → outsource_requests → invitations → quotations → orders → events
--   → workflow_* (无硬依赖，独立)
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 0. 通用 trigger：自动维护 updated_at
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- 第一组：基础表（suppliers / tenants / users / projects）
-- =============================================================================

-- 1. suppliers
CREATE TABLE IF NOT EXISTS suppliers (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(255) NOT NULL UNIQUE,
    category      VARCHAR(128),
    address       VARCHAR(512),
    contact_name  VARCHAR(64),
    contact_phone VARCHAR(32),
    rating        DECIMAL(4,2),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
DROP TRIGGER IF EXISTS tr_suppliers_updated_at ON suppliers;
CREATE TRIGGER tr_suppliers_updated_at BEFORE UPDATE ON suppliers
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- 2. tenants
CREATE TABLE IF NOT EXISTS tenants (
    id              SERIAL PRIMARY KEY,
    tenant_type     VARCHAR(32) NOT NULL,
    name            VARCHAR(255) NOT NULL UNIQUE,
    supplier_id     INTEGER,
    contact_name    VARCHAR(64),
    contact_phone   VARCHAR(32),
    contact_email   VARCHAR(128),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tenants_type     ON tenants (tenant_type);
CREATE INDEX IF NOT EXISTS idx_tenants_supplier ON tenants (supplier_id);
DROP TRIGGER IF EXISTS tr_tenants_updated_at ON tenants;
CREATE TRIGGER tr_tenants_updated_at BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- 3. users
CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id),
    username        VARCHAR(64) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    phone           VARCHAR(32),
    display_name    VARCHAR(64) NOT NULL,
    role            VARCHAR(64),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_users_tenant ON users (tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_phone  ON users (phone);
DROP TRIGGER IF EXISTS tr_users_updated_at ON users;
CREATE TRIGGER tr_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- 4. projects
CREATE TABLE IF NOT EXISTS projects (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id),
    project_no      VARCHAR(64) NOT NULL UNIQUE,
    name            VARCHAR(255) NOT NULL,
    customer        VARCHAR(255) NOT NULL,
    deadline        DATE,
    unit_price      DECIMAL(14,2),
    quantity        INTEGER,
    description     TEXT,
    status          VARCHAR(32) NOT NULL DEFAULT 'drafted',
    created_by      INTEGER,
    confirmed_at    TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_projects_tenant_status ON projects (tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_projects_created_by    ON projects (created_by);
DROP TRIGGER IF EXISTS tr_projects_updated_at ON projects;
CREATE TRIGGER tr_projects_updated_at BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- 5. project_parts
CREATE TABLE IF NOT EXISTS project_parts (
    id              SERIAL PRIMARY KEY,
    project_id      INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    part_no         VARCHAR(64) NOT NULL,
    part_name       VARCHAR(255),
    material        VARCHAR(64),
    qty             INTEGER NOT NULL DEFAULT 1,
    processes_json  JSONB,
    spec            VARCHAR(255),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_parts_project ON project_parts (project_id);
DROP TRIGGER IF EXISTS tr_parts_updated_at ON project_parts;
CREATE TRIGGER tr_parts_updated_at BEFORE UPDATE ON project_parts
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- 6. attachments
CREATE TABLE IF NOT EXISTS attachments (
    id              SERIAL PRIMARY KEY,
    related_type    VARCHAR(32) NOT NULL,
    related_id      INTEGER NOT NULL,
    file_name       VARCHAR(255) NOT NULL,
    file_path       VARCHAR(512) NOT NULL,
    file_size       INTEGER,
    mime_type       VARCHAR(128),
    uploaded_by     INTEGER,
    category        VARCHAR(64),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_att_related     ON attachments (related_type, related_id);
CREATE INDEX IF NOT EXISTS idx_att_uploaded_by ON attachments (uploaded_by);



-- =============================================================================
-- 第二组：生产决策（阶段 1）
-- =============================================================================

-- 7. supplier_capabilities
CREATE TABLE IF NOT EXISTS supplier_capabilities (
    id            SERIAL PRIMARY KEY,
    supplier_id   INTEGER NOT NULL REFERENCES suppliers(id),
    process_name  VARCHAR(64) NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_supplier_process UNIQUE (supplier_id, process_name)
);
CREATE INDEX IF NOT EXISTS idx_cap_process ON supplier_capabilities (process_name);


-- 8. production_decisions
CREATE TABLE IF NOT EXISTS production_decisions (
    id                  SERIAL PRIMARY KEY,
    project_id          INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    part_id             INTEGER NOT NULL REFERENCES project_parts(id) ON DELETE CASCADE,
    process_name        VARCHAR(64) NOT NULL,
    ai_suggestion       VARCHAR(32) NOT NULL,
    ai_reason           TEXT,
    ai_source           VARCHAR(32) DEFAULT 'rules',
    is_forced           BOOLEAN NOT NULL DEFAULT FALSE,
    final_decision      VARCHAR(32),
    final_reason        TEXT,
    reviewed_by         INTEGER,
    reviewed_at         TIMESTAMP,
    status              VARCHAR(32) NOT NULL DEFAULT 'pending_review',
    approval_task_id    BIGINT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_dec_project       ON production_decisions (project_id);
CREATE INDEX IF NOT EXISTS idx_dec_part          ON production_decisions (part_id);
CREATE INDEX IF NOT EXISTS idx_dec_status        ON production_decisions (status);
CREATE INDEX IF NOT EXISTS idx_dec_approval_task ON production_decisions (approval_task_id);
DROP TRIGGER IF EXISTS tr_dec_updated_at ON production_decisions;
CREATE TRIGGER tr_dec_updated_at BEFORE UPDATE ON production_decisions
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- =============================================================================
-- 第三组：委外询价闭环（阶段 3）
-- =============================================================================

-- 9. outsource_requests
CREATE TABLE IF NOT EXISTS outsource_requests (
    id                       SERIAL PRIMARY KEY,
    project_id               INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title                    VARCHAR(255) NOT NULL,
    required_processes_json  JSONB NOT NULL,
    quantity                 INTEGER,
    deadline                 DATE,
    status                   VARCHAR(32) NOT NULL DEFAULT 'draft',
    closed_at                TIMESTAMP,
    approval_task_id         BIGINT,
    winning_quotation_id     INTEGER,
    created_by               INTEGER,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_req_project ON outsource_requests (project_id);
CREATE INDEX IF NOT EXISTS idx_req_status  ON outsource_requests (status);
DROP TRIGGER IF EXISTS tr_req_updated_at ON outsource_requests;
CREATE TRIGGER tr_req_updated_at BEFORE UPDATE ON outsource_requests
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- 10. outsource_request_invitations
CREATE TABLE IF NOT EXISTS outsource_request_invitations (
    id                SERIAL PRIMARY KEY,
    request_id        INTEGER NOT NULL REFERENCES outsource_requests(id) ON DELETE CASCADE,
    supplier_id       INTEGER NOT NULL REFERENCES suppliers(id),
    tenant_id         INTEGER,
    invitation_status VARCHAR(32) NOT NULL DEFAULT 'sent',
    sent_at           TIMESTAMP NOT NULL,
    quoted_at         TIMESTAMP,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_request_supplier UNIQUE (request_id, supplier_id)
);
CREATE INDEX IF NOT EXISTS idx_inv_request       ON outsource_request_invitations (request_id);
CREATE INDEX IF NOT EXISTS idx_inv_tenant_status ON outsource_request_invitations (tenant_id, invitation_status);


-- 11. outsource_quotations
CREATE TABLE IF NOT EXISTS outsource_quotations (
    id                SERIAL PRIMARY KEY,
    invitation_id     INTEGER NOT NULL UNIQUE REFERENCES outsource_request_invitations(id) ON DELETE CASCADE,
    unit_price        DECIMAL(14,2) NOT NULL,
    lead_time_days    INTEGER NOT NULL,
    note              TEXT,
    submitted_by      INTEGER,
    submitted_at      TIMESTAMP NOT NULL,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_quote_invitation ON outsource_quotations (invitation_id);


-- 12. outsource_orders
CREATE TABLE IF NOT EXISTS outsource_orders (
    id                SERIAL PRIMARY KEY,
    request_id        INTEGER NOT NULL REFERENCES outsource_requests(id),
    quotation_id      INTEGER NOT NULL REFERENCES outsource_quotations(id),
    supplier_id       INTEGER NOT NULL REFERENCES suppliers(id),
    tenant_id         INTEGER,
    order_no          VARCHAR(64) NOT NULL UNIQUE,
    unit_price        DECIMAL(14,2) NOT NULL,
    quantity          INTEGER NOT NULL,
    total_amount      DECIMAL(14,2),
    lead_time_days    INTEGER NOT NULL,
    status            VARCHAR(32) NOT NULL DEFAULT 'awarded',
    awarded_at        TIMESTAMP NOT NULL,
    accepted_at       TIMESTAMP,
    delivered_at      TIMESTAMP,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_order_request         ON outsource_orders (request_id);
CREATE INDEX IF NOT EXISTS idx_order_supplier_status ON outsource_orders (supplier_id, status);
CREATE INDEX IF NOT EXISTS idx_order_tenant_status   ON outsource_orders (tenant_id, status);
DROP TRIGGER IF EXISTS tr_order_updated_at ON outsource_orders;
CREATE TRIGGER tr_order_updated_at BEFORE UPDATE ON outsource_orders
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- 13. outsource_order_status_events
CREATE TABLE IF NOT EXISTS outsource_order_status_events (
    id           SERIAL PRIMARY KEY,
    order_id     INTEGER NOT NULL REFERENCES outsource_orders(id) ON DELETE CASCADE,
    from_status  VARCHAR(32),
    to_status    VARCHAR(32) NOT NULL,
    changed_by   INTEGER,
    note         VARCHAR(512),
    occurred_at  TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evt_order ON outsource_order_status_events (order_id, occurred_at);


-- =============================================================================
-- 第四组：工作流/审批框架（原 MySQL 002 对应）
-- =============================================================================

-- 14. workflow_definitions
CREATE TABLE IF NOT EXISTS workflow_definitions (
    id            BIGSERIAL PRIMARY KEY,
    "key"         VARCHAR(128) NOT NULL,
    version       INTEGER NOT NULL DEFAULT 1,
    name          VARCHAR(255) NOT NULL,
    description   TEXT,
    spec_json     JSONB NOT NULL,
    spec_hash     CHAR(64) NOT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_wfdef_key_version UNIQUE ("key", version)
);
CREATE INDEX IF NOT EXISTS idx_wfdef_hash   ON workflow_definitions (spec_hash);
CREATE INDEX IF NOT EXISTS idx_wfdef_active ON workflow_definitions (is_active);
DROP TRIGGER IF EXISTS tr_wfdef_updated_at ON workflow_definitions;
CREATE TRIGGER tr_wfdef_updated_at BEFORE UPDATE ON workflow_definitions
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- 15. workflow_instances
CREATE TABLE IF NOT EXISTS workflow_instances (
    id                UUID PRIMARY KEY,
    definition_id     BIGINT NOT NULL REFERENCES workflow_definitions(id),
    workflow_key      VARCHAR(128) NOT NULL,
    version           INTEGER NOT NULL,
    status            VARCHAR(32) NOT NULL,
    trigger_source    VARCHAR(64),
    trigger_user      VARCHAR(128),
    inputs_json       JSONB NOT NULL,
    outputs_json      JSONB,
    context_json      JSONB NOT NULL,
    current_nodes     JSONB,
    error_message     TEXT,
    lease_owner       VARCHAR(128),
    lease_expires_at  TIMESTAMP,
    started_at        TIMESTAMP NOT NULL,
    ended_at          TIMESTAMP,
    created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_wfinst_status     ON workflow_instances (status);
CREATE INDEX IF NOT EXISTS idx_wfinst_key_status ON workflow_instances (workflow_key, status);
CREATE INDEX IF NOT EXISTS idx_wfinst_lease      ON workflow_instances (lease_owner, lease_expires_at);
DROP TRIGGER IF EXISTS tr_wfinst_updated_at ON workflow_instances;
CREATE TRIGGER tr_wfinst_updated_at BEFORE UPDATE ON workflow_instances
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- 16. workflow_node_executions
CREATE TABLE IF NOT EXISTS workflow_node_executions (
    id            BIGSERIAL PRIMARY KEY,
    instance_id   UUID NOT NULL,
    node_id       VARCHAR(128) NOT NULL,
    node_type     VARCHAR(32) NOT NULL,
    attempt       INTEGER NOT NULL DEFAULT 1,
    status        VARCHAR(32) NOT NULL,
    input_json    JSONB,
    output_json   JSONB,
    error_message TEXT,
    started_at    TIMESTAMP NOT NULL,
    ended_at      TIMESTAMP,
    duration_ms   INTEGER,
    execution_id  UUID NOT NULL,
    CONSTRAINT uk_wfnode_exec UNIQUE (execution_id)
);
CREATE INDEX IF NOT EXISTS idx_wfnode_instance_node   ON workflow_node_executions (instance_id, node_id);
CREATE INDEX IF NOT EXISTS idx_wfnode_instance_status ON workflow_node_executions (instance_id, status);


-- 17. workflow_approval_records（append-only）
CREATE TABLE IF NOT EXISTS workflow_approval_records (
    id                UUID PRIMARY KEY,
    instance_id       UUID NOT NULL,
    node_id           VARCHAR(128) NOT NULL,
    action            VARCHAR(32) NOT NULL,
    actor_id          VARCHAR(128) NOT NULL,
    assignee_type     VARCHAR(32) NOT NULL,
    assignee_id       VARCHAR(128) NOT NULL,
    comment           TEXT,
    delegate_to       VARCHAR(128),
    metadata_json     JSONB,
    created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_wfrec_instance_node ON workflow_approval_records (instance_id, node_id);
CREATE INDEX IF NOT EXISTS idx_wfrec_actor         ON workflow_approval_records (actor_id, created_at);


-- 18. workflow_approval_tasks（my pending todo）
CREATE TABLE IF NOT EXISTS workflow_approval_tasks (
    id                 BIGSERIAL PRIMARY KEY,
    instance_id        UUID NOT NULL,
    node_id            VARCHAR(128) NOT NULL,
    assignee_type      VARCHAR(32) NOT NULL,
    assignee_id        VARCHAR(128) NOT NULL,
    status             VARCHAR(32) NOT NULL,
    claimed_by         VARCHAR(128),
    claimed_at         TIMESTAMP,
    completed_at       TIMESTAMP,
    completion_action  VARCHAR(32),
    due_at             TIMESTAMP,
    created_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_wftask_instance_node_assignee UNIQUE (instance_id, node_id, assignee_type, assignee_id)
);
CREATE INDEX IF NOT EXISTS idx_wftask_assignee_pending ON workflow_approval_tasks (assignee_type, assignee_id, status);
CREATE INDEX IF NOT EXISTS idx_wftask_due              ON workflow_approval_tasks (status, due_at);


-- 19. workflow_state_events
CREATE TABLE IF NOT EXISTS workflow_state_events (
    id            BIGSERIAL PRIMARY KEY,
    instance_id   UUID NOT NULL,
    node_id       VARCHAR(128),
    event_type    VARCHAR(64) NOT NULL,
    from_status   VARCHAR(32),
    to_status     VARCHAR(32),
    payload_json  JSONB,
    occurred_at   TIMESTAMP(3) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wfevt_instance_time ON workflow_state_events (instance_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_wfevt_type_time     ON workflow_state_events (event_type, occurred_at);


-- =============================================================================
-- 完成校验：查询所有已创建的表
-- =============================================================================
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
-- 预期输出 19 行：
--   attachments, outsource_order_status_events, outsource_orders,
--   outsource_quotations, outsource_request_invitations, outsource_requests,
--   production_decisions, project_parts, projects, supplier_capabilities,
--   suppliers, tenants, users, workflow_approval_records, workflow_approval_tasks,
--   workflow_definitions, workflow_instances, workflow_node_executions,
--   workflow_state_events



-- =============================================================================
-- 第二组：生产决策（阶段 1）
-- =============================================================================

-- 7. supplier_capabilities
CREATE TABLE IF NOT EXISTS supplier_capabilities (
    id            SERIAL PRIMARY KEY,
    supplier_id   INTEGER NOT NULL REFERENCES suppliers(id),
    process_name  VARCHAR(64) NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_supplier_process UNIQUE (supplier_id, process_name)
);
CREATE INDEX IF NOT EXISTS idx_cap_process ON supplier_capabilities (process_name);


-- 8. production_decisions
CREATE TABLE IF NOT EXISTS production_decisions (
    id                  SERIAL PRIMARY KEY,
    project_id          INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    part_id             INTEGER NOT NULL REFERENCES project_parts(id) ON DELETE CASCADE,
    process_name        VARCHAR(64) NOT NULL,
    ai_suggestion       VARCHAR(32) NOT NULL,
    ai_reason           TEXT,
    ai_source           VARCHAR(32) DEFAULT 'rules',
    is_forced           BOOLEAN NOT NULL DEFAULT FALSE,
    final_decision      VARCHAR(32),
    final_reason        TEXT,
    reviewed_by         INTEGER,
    reviewed_at         TIMESTAMP,
    status              VARCHAR(32) NOT NULL DEFAULT 'pending_review',
    approval_task_id    BIGINT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_dec_project       ON production_decisions (project_id);
CREATE INDEX IF NOT EXISTS idx_dec_part          ON production_decisions (part_id);
CREATE INDEX IF NOT EXISTS idx_dec_status        ON production_decisions (status);
CREATE INDEX IF NOT EXISTS idx_dec_approval_task ON production_decisions (approval_task_id);
DROP TRIGGER IF EXISTS tr_dec_updated_at ON production_decisions;
CREATE TRIGGER tr_dec_updated_at BEFORE UPDATE ON production_decisions
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- =============================================================================
-- 第三组：委外询价闭环（阶段 3）
-- =============================================================================

-- 9. outsource_requests
CREATE TABLE IF NOT EXISTS outsource_requests (
    id                       SERIAL PRIMARY KEY,
    project_id               INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title                    VARCHAR(255) NOT NULL,
    required_processes_json  JSONB NOT NULL,
    quantity                 INTEGER,
    deadline                 DATE,
    status                   VARCHAR(32) NOT NULL DEFAULT 'draft',
    closed_at                TIMESTAMP,
    approval_task_id         BIGINT,
    winning_quotation_id     INTEGER,
    created_by               INTEGER,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_req_project ON outsource_requests (project_id);
CREATE INDEX IF NOT EXISTS idx_req_status  ON outsource_requests (status);
DROP TRIGGER IF EXISTS tr_req_updated_at ON outsource_requests;
CREATE TRIGGER tr_req_updated_at BEFORE UPDATE ON outsource_requests
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- 10. outsource_request_invitations
CREATE TABLE IF NOT EXISTS outsource_request_invitations (
    id                SERIAL PRIMARY KEY,
    request_id        INTEGER NOT NULL REFERENCES outsource_requests(id) ON DELETE CASCADE,
    supplier_id       INTEGER NOT NULL REFERENCES suppliers(id),
    tenant_id         INTEGER,
    invitation_status VARCHAR(32) NOT NULL DEFAULT 'sent',
    sent_at           TIMESTAMP NOT NULL,
    quoted_at         TIMESTAMP,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_request_supplier UNIQUE (request_id, supplier_id)
);
CREATE INDEX IF NOT EXISTS idx_inv_request       ON outsource_request_invitations (request_id);
CREATE INDEX IF NOT EXISTS idx_inv_tenant_status ON outsource_request_invitations (tenant_id, invitation_status);


-- 11. outsource_quotations
CREATE TABLE IF NOT EXISTS outsource_quotations (
    id                SERIAL PRIMARY KEY,
    invitation_id     INTEGER NOT NULL UNIQUE REFERENCES outsource_request_invitations(id) ON DELETE CASCADE,
    unit_price        DECIMAL(14,2) NOT NULL,
    lead_time_days    INTEGER NOT NULL,
    note              TEXT,
    submitted_by      INTEGER,
    submitted_at      TIMESTAMP NOT NULL,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_quote_invitation ON outsource_quotations (invitation_id);


-- 12. outsource_orders
CREATE TABLE IF NOT EXISTS outsource_orders (
    id                SERIAL PRIMARY KEY,
    request_id        INTEGER NOT NULL REFERENCES outsource_requests(id),
    quotation_id      INTEGER NOT NULL REFERENCES outsource_quotations(id),
    supplier_id       INTEGER NOT NULL REFERENCES suppliers(id),
    tenant_id         INTEGER,
    order_no          VARCHAR(64) NOT NULL UNIQUE,
    unit_price        DECIMAL(14,2) NOT NULL,
    quantity          INTEGER NOT NULL,
    total_amount      DECIMAL(14,2),
    lead_time_days    INTEGER NOT NULL,
    status            VARCHAR(32) NOT NULL DEFAULT 'awarded',
    awarded_at        TIMESTAMP NOT NULL,
    accepted_at       TIMESTAMP,
    delivered_at      TIMESTAMP,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_order_request         ON outsource_orders (request_id);
CREATE INDEX IF NOT EXISTS idx_order_supplier_status ON outsource_orders (supplier_id, status);
CREATE INDEX IF NOT EXISTS idx_order_tenant_status   ON outsource_orders (tenant_id, status);
DROP TRIGGER IF EXISTS tr_order_updated_at ON outsource_orders;
CREATE TRIGGER tr_order_updated_at BEFORE UPDATE ON outsource_orders
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- 13. outsource_order_status_events
CREATE TABLE IF NOT EXISTS outsource_order_status_events (
    id           SERIAL PRIMARY KEY,
    order_id     INTEGER NOT NULL REFERENCES outsource_orders(id) ON DELETE CASCADE,
    from_status  VARCHAR(32),
    to_status    VARCHAR(32) NOT NULL,
    changed_by   INTEGER,
    note         VARCHAR(512),
    occurred_at  TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evt_order ON outsource_order_status_events (order_id, occurred_at);


-- =============================================================================
-- 第四组：工作流/审批框架
-- =============================================================================

-- 14. workflow_definitions
CREATE TABLE IF NOT EXISTS workflow_definitions (
    id            BIGSERIAL PRIMARY KEY,
    "key"         VARCHAR(128) NOT NULL,
    version       INTEGER NOT NULL DEFAULT 1,
    name          VARCHAR(255) NOT NULL,
    description   TEXT,
    spec_json     JSONB NOT NULL,
    spec_hash     CHAR(64) NOT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_wfdef_key_version UNIQUE ("key", version)
);
CREATE INDEX IF NOT EXISTS idx_wfdef_hash   ON workflow_definitions (spec_hash);
CREATE INDEX IF NOT EXISTS idx_wfdef_active ON workflow_definitions (is_active);
DROP TRIGGER IF EXISTS tr_wfdef_updated_at ON workflow_definitions;
CREATE TRIGGER tr_wfdef_updated_at BEFORE UPDATE ON workflow_definitions
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- 15. workflow_instances
CREATE TABLE IF NOT EXISTS workflow_instances (
    id                UUID PRIMARY KEY,
    definition_id     BIGINT NOT NULL REFERENCES workflow_definitions(id),
    workflow_key      VARCHAR(128) NOT NULL,
    version           INTEGER NOT NULL,
    status            VARCHAR(32) NOT NULL,
    trigger_source    VARCHAR(64),
    trigger_user      VARCHAR(128),
    inputs_json       JSONB NOT NULL,
    outputs_json      JSONB,
    context_json      JSONB NOT NULL,
    current_nodes     JSONB,
    error_message     TEXT,
    lease_owner       VARCHAR(128),
    lease_expires_at  TIMESTAMP,
    started_at        TIMESTAMP NOT NULL,
    ended_at          TIMESTAMP,
    created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_wfinst_status     ON workflow_instances (status);
CREATE INDEX IF NOT EXISTS idx_wfinst_key_status ON workflow_instances (workflow_key, status);
CREATE INDEX IF NOT EXISTS idx_wfinst_lease      ON workflow_instances (lease_owner, lease_expires_at);
DROP TRIGGER IF EXISTS tr_wfinst_updated_at ON workflow_instances;
CREATE TRIGGER tr_wfinst_updated_at BEFORE UPDATE ON workflow_instances
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- 16. workflow_node_executions
CREATE TABLE IF NOT EXISTS workflow_node_executions (
    id            BIGSERIAL PRIMARY KEY,
    instance_id   UUID NOT NULL,
    node_id       VARCHAR(128) NOT NULL,
    node_type     VARCHAR(32) NOT NULL,
    attempt       INTEGER NOT NULL DEFAULT 1,
    status        VARCHAR(32) NOT NULL,
    input_json    JSONB,
    output_json   JSONB,
    error_message TEXT,
    started_at    TIMESTAMP NOT NULL,
    ended_at      TIMESTAMP,
    duration_ms   INTEGER,
    execution_id  UUID NOT NULL,
    CONSTRAINT uk_wfnode_exec UNIQUE (execution_id)
);
CREATE INDEX IF NOT EXISTS idx_wfnode_instance_node   ON workflow_node_executions (instance_id, node_id);
CREATE INDEX IF NOT EXISTS idx_wfnode_instance_status ON workflow_node_executions (instance_id, status);


-- 17. workflow_approval_records（append-only）
CREATE TABLE IF NOT EXISTS workflow_approval_records (
    id                UUID PRIMARY KEY,
    instance_id       UUID NOT NULL,
    node_id           VARCHAR(128) NOT NULL,
    action            VARCHAR(32) NOT NULL,
    actor_id          VARCHAR(128) NOT NULL,
    assignee_type     VARCHAR(32) NOT NULL,
    assignee_id       VARCHAR(128) NOT NULL,
    comment           TEXT,
    delegate_to       VARCHAR(128),
    metadata_json     JSONB,
    created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_wfrec_instance_node ON workflow_approval_records (instance_id, node_id);
CREATE INDEX IF NOT EXISTS idx_wfrec_actor         ON workflow_approval_records (actor_id, created_at);


-- 18. workflow_approval_tasks（my pending todo）
CREATE TABLE IF NOT EXISTS workflow_approval_tasks (
    id                 BIGSERIAL PRIMARY KEY,
    instance_id        UUID NOT NULL,
    node_id            VARCHAR(128) NOT NULL,
    assignee_type      VARCHAR(32) NOT NULL,
    assignee_id        VARCHAR(128) NOT NULL,
    status             VARCHAR(32) NOT NULL,
    claimed_by         VARCHAR(128),
    claimed_at         TIMESTAMP,
    completed_at       TIMESTAMP,
    completion_action  VARCHAR(32),
    due_at             TIMESTAMP,
    created_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_wftask_instance_node_assignee UNIQUE (instance_id, node_id, assignee_type, assignee_id)
);
CREATE INDEX IF NOT EXISTS idx_wftask_assignee_pending ON workflow_approval_tasks (assignee_type, assignee_id, status);
CREATE INDEX IF NOT EXISTS idx_wftask_due              ON workflow_approval_tasks (status, due_at);


-- 19. workflow_state_events
CREATE TABLE IF NOT EXISTS workflow_state_events (
    id            BIGSERIAL PRIMARY KEY,
    instance_id   UUID NOT NULL,
    node_id       VARCHAR(128),
    event_type    VARCHAR(64) NOT NULL,
    from_status   VARCHAR(32),
    to_status     VARCHAR(32),
    payload_json  JSONB,
    occurred_at   TIMESTAMP(3) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wfevt_instance_time ON workflow_state_events (instance_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_wfevt_type_time     ON workflow_state_events (event_type, occurred_at);


-- =============================================================================
-- 完成校验：应返回 19 行
-- =============================================================================
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
