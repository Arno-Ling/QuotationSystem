-- =============================================================================
-- Migration 002: Add Workflow Engine tables
-- =============================================================================
-- Adds 6 tables required by Harness Workflow Engine:
--   1. workflow_definitions     - Declarative workflow specs (versioned)
--   2. workflow_instances       - Runtime instances with lease-based mutex
--   3. workflow_node_executions - Per-node execution records (execution_id unique)
--   4. workflow_approval_records- Append-only approval action history
--   5. workflow_approval_tasks  - Pending approval tasks ("my todo")
--   6. workflow_state_events    - Audit log for all state transitions
--
-- Requirements: REQ-021, REQ-024, REQ-025, REQ-026, REQ-031, REQ-058
-- =============================================================================

USE mold_procurement;

-- -----------------------------------------------------------------------------
-- 1. workflow_definitions
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflow_definitions (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    `key`         VARCHAR(128) NOT NULL                              COMMENT '业务唯一 key',
    version       INT NOT NULL DEFAULT 1                             COMMENT '版本号',
    name          VARCHAR(255) NOT NULL,
    description   TEXT,
    spec_json     JSON NOT NULL                                      COMMENT '完整 WorkflowDefinition',
    spec_hash     CHAR(64) NOT NULL                                  COMMENT 'SHA-256，用于查重',
    is_active     TINYINT(1) NOT NULL DEFAULT 1                      COMMENT '软删除标记',
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_key_version (`key`, version),
    KEY idx_hash (spec_hash),
    KEY idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='工作流声明式定义（按 key+version 版本化）';

-- -----------------------------------------------------------------------------
-- 2. workflow_instances
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflow_instances (
    id                BINARY(16) PRIMARY KEY                         COMMENT 'UUID v4',
    definition_id     BIGINT NOT NULL,
    workflow_key      VARCHAR(128) NOT NULL,
    version           INT NOT NULL,
    status            VARCHAR(32) NOT NULL                           COMMENT 'WorkflowStatus 枚举',
    trigger_source    VARCHAR(64)                                    COMMENT 'api/schedule/event',
    trigger_user      VARCHAR(128),
    inputs_json       JSON NOT NULL,
    outputs_json      JSON,
    context_json      JSON NOT NULL                                  COMMENT 'WorkflowContext 快照',
    current_nodes     JSON                                           COMMENT '["node_a","node_b"]',
    error_message     TEXT,
    lease_owner       VARCHAR(128)                                   COMMENT '进程/节点标识（租约持有者）',
    lease_expires_at  DATETIME                                       COMMENT '租约过期时间',
    started_at        DATETIME NOT NULL,
    ended_at          DATETIME,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_status (status),
    KEY idx_key_status (workflow_key, status),
    KEY idx_lease (lease_owner, lease_expires_at),
    CONSTRAINT fk_instance_def FOREIGN KEY (definition_id) REFERENCES workflow_definitions(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='工作流实例（带租约机制保证单进程执行）';

-- -----------------------------------------------------------------------------
-- 3. workflow_node_executions
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflow_node_executions (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    instance_id   BINARY(16) NOT NULL,
    node_id       VARCHAR(128) NOT NULL,
    node_type     VARCHAR(32) NOT NULL                               COMMENT 'NodeType 枚举',
    attempt       INT NOT NULL DEFAULT 1                             COMMENT '第 N 次重试',
    status        VARCHAR(32) NOT NULL                               COMMENT 'NodeStatus 枚举',
    input_json    JSON                                               COMMENT '渲染后的 params',
    output_json   JSON                                               COMMENT '节点输出',
    error_message TEXT,
    started_at    DATETIME NOT NULL,
    ended_at      DATETIME,
    duration_ms   INT,
    execution_id  CHAR(36) NOT NULL                                  COMMENT '幂等键（UUID）',
    UNIQUE KEY uk_execution (execution_id),
    KEY idx_instance_node (instance_id, node_id),
    KEY idx_instance_status (instance_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='节点执行记录（execution_id 唯一约束保证幂等）';

-- -----------------------------------------------------------------------------
-- 4. workflow_approval_records（append-only）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflow_approval_records (
    id                BINARY(16) PRIMARY KEY                         COMMENT 'UUID',
    instance_id       BINARY(16) NOT NULL,
    node_id           VARCHAR(128) NOT NULL,
    action            VARCHAR(32) NOT NULL                           COMMENT 'ApprovalAction 枚举',
    actor_id          VARCHAR(128) NOT NULL                          COMMENT '执行动作的人',
    assignee_type     VARCHAR(32) NOT NULL                           COMMENT 'user/shared_account/role',
    assignee_id       VARCHAR(128) NOT NULL,
    comment           TEXT,
    delegate_to       VARCHAR(128)                                   COMMENT '仅 DELEGATE/FORWARD 有值',
    metadata_json     JSON                                           COMMENT '扩展字段',
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_instance_node (instance_id, node_id),
    KEY idx_actor (actor_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='审批历史（只追加，禁止 UPDATE/DELETE）';

-- -----------------------------------------------------------------------------
-- 5. workflow_approval_tasks（my pending todo list）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflow_approval_tasks (
    id                 BIGINT AUTO_INCREMENT PRIMARY KEY,
    instance_id        BINARY(16) NOT NULL,
    node_id            VARCHAR(128) NOT NULL,
    assignee_type      VARCHAR(32) NOT NULL,
    assignee_id        VARCHAR(128) NOT NULL,
    status             VARCHAR(32) NOT NULL                          COMMENT 'pending/claimed/completed/timeout/withdrawn/delegated',
    claimed_by         VARCHAR(128),
    claimed_at         DATETIME,
    completed_at       DATETIME,
    completion_action  VARCHAR(32)                                   COMMENT '完成时的动作',
    due_at             DATETIME                                      COMMENT '超时时间',
    created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_instance_node_assignee (instance_id, node_id, assignee_type, assignee_id),
    KEY idx_assignee_pending (assignee_type, assignee_id, status),
    KEY idx_due (status, due_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='审批待办（支持"我的待办"查询和超时扫描）';

-- -----------------------------------------------------------------------------
-- 6. workflow_state_events（audit log）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflow_state_events (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    instance_id   BINARY(16) NOT NULL,
    node_id       VARCHAR(128)                                       COMMENT 'NULL 表示工作流级事件',
    event_type    VARCHAR(64) NOT NULL                               COMMENT 'workflow_started/node_completed/...',
    from_status   VARCHAR(32),
    to_status     VARCHAR(32),
    payload_json  JSON,
    occurred_at   DATETIME(3) NOT NULL                               COMMENT '毫秒精度',
    KEY idx_instance_time (instance_id, occurred_at),
    KEY idx_type_time (event_type, occurred_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='状态变更事件（只追加，支持审计和事件回放）';

-- =============================================================================
-- Verification queries (optional, for manual validation)
-- =============================================================================
-- SHOW TABLES LIKE 'workflow_%';
-- DESCRIBE workflow_definitions;
-- DESCRIBE workflow_instances;
-- DESCRIBE workflow_node_executions;
-- DESCRIBE workflow_approval_records;
-- DESCRIBE workflow_approval_tasks;
-- DESCRIBE workflow_state_events;
