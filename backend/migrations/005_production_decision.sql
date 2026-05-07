-- =============================================================================
-- Migration 005: Production Decision (Stage 1 — 生产决策)
-- =============================================================================
-- Creates 2 new tables for production decision flow:
--   1. supplier_capabilities  - 供应商工艺能力标签（用于阶段 3 的候选匹配）
--   2. production_decisions   - 生产决策行（每个零件×工序一行）
--
-- Idempotent: CREATE TABLE IF NOT EXISTS
-- =============================================================================

USE mold_procurement;

-- -----------------------------------------------------------------------------
-- 1. supplier_capabilities  (供应商工艺能力标签)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS supplier_capabilities (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    supplier_id     INT NOT NULL,
    process_name    VARCHAR(64) NOT NULL             COMMENT '工艺名称（如 线割 / 热处理 / 磨）',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_supplier_process (supplier_id, process_name),
    INDEX idx_process (process_name),
    CONSTRAINT fk_cap_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='供应商工艺能力标签';


-- -----------------------------------------------------------------------------
-- 2. production_decisions  (生产决策行)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS production_decisions (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    project_id          INT NOT NULL,
    part_id             INT NOT NULL                 COMMENT 'project_parts.id',
    process_name        VARCHAR(64) NOT NULL         COMMENT '具体工序名',

    -- AI 建议
    ai_suggestion       VARCHAR(32) NOT NULL         COMMENT 'self_made / outsource',
    ai_reason           TEXT                         COMMENT 'AI 建议的理由',
    ai_source           VARCHAR(32) DEFAULT 'rules'  COMMENT 'rules / llm / manual',
    is_forced           TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否强制委外(热处理/表面处理等)',

    -- 人工最终决定
    final_decision      VARCHAR(32)                  COMMENT 'self_made / outsource；初始 NULL',
    final_reason        TEXT                         COMMENT '人工修改时的理由(可选)',
    reviewed_by         INT                          COMMENT '最后修改人 users.id',
    reviewed_at         DATETIME,

    -- 生命周期
    status              VARCHAR(32) NOT NULL DEFAULT 'pending_review'
                                                     COMMENT 'pending_review / reviewed / submitted / finalized',
    approval_task_id    BIGINT                       COMMENT '关联审批任务 workflow_approval_tasks.id（批次级）',
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_project (project_id),
    INDEX idx_part (part_id),
    INDEX idx_status (status),
    INDEX idx_approval_task (approval_task_id),
    CONSTRAINT fk_dec_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    CONSTRAINT fk_dec_part    FOREIGN KEY (part_id)    REFERENCES project_parts(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='生产决策行（每个零件×工序一行）';
