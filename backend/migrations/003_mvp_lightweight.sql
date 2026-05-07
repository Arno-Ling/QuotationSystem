-- =============================================================================
-- Migration 003: Lightweight Script MVP
-- =============================================================================
-- Adds 5 new tables for the Lightweight Script MVP:
--   1. drawings           - Drawing metadata + file path + version
--   2. boms               - BOM (Bill of Materials), supports version overlay
--   3. ai_analyses        - Generic AI analysis results (exceptions/quotations/...)
--   4. workflow_runs      - Lightweight workflow run records (upgradable)
--   5. notifications      - Email / in-app notifications
--
-- Does NOT modify:
--   - exceptions / quotations / suppliers     (from init.sql)
--   - workflow_approval_tasks / _records      (from migration 002)
--   - workflow_state_events                   (from migration 002)
--
-- Requirements: design.md §Data Models, §决策 1
-- Idempotent: all CREATE TABLE statements use IF NOT EXISTS
-- =============================================================================

USE mold_procurement;

-- -----------------------------------------------------------------------------
-- 1. drawings
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS drawings (
    id                  VARCHAR(36) PRIMARY KEY                         COMMENT 'UUID',
    project_id          VARCHAR(36)                                     COMMENT '关联项目ID',
    part_id             VARCHAR(36)                                     COMMENT '关联零件ID',
    file_name           VARCHAR(255) NOT NULL                           COMMENT '原始文件名',
    file_path           VARCHAR(512) NOT NULL                           COMMENT 'uploads/... 存储路径',
    file_format         VARCHAR(16) NOT NULL                            COMMENT 'pdf/dwg/step/...',
    version             INT NOT NULL DEFAULT 1                          COMMENT '版本号',
    parent_drawing_id   VARCHAR(36)                                     COMMENT '父版本 ID（版本叠加）',
    ocr_status          VARCHAR(32) DEFAULT 'pending'                   COMMENT 'pending/done/failed',
    ocr_text            LONGTEXT                                        COMMENT 'OCR 提取文本',
    extracted_meta      JSON                                            COMMENT '工序/材料/BOM 摘要',
    uploaded_by         VARCHAR(36)                                     COMMENT '上传人',
    uploaded_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_project (project_id),
    INDEX idx_part (part_id),
    INDEX idx_parent (parent_drawing_id),
    INDEX idx_ocr_status (ocr_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='图纸表（支持版本追溯）';


-- -----------------------------------------------------------------------------
-- 2. boms (BOM with version overlay)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS boms (
    id                  VARCHAR(36) PRIMARY KEY,
    drawing_id          VARCHAR(36) NOT NULL                            COMMENT '所属图纸',
    bom_type            VARCHAR(32) NOT NULL                            COMMENT 'raw_material/hardware/cost_sheet',
    version             INT NOT NULL DEFAULT 1,
    items_json          JSON NOT NULL                                   COMMENT '[{material,qty,unit,spec},...]',
    parent_bom_id       VARCHAR(36)                                     COMMENT '上一版 BOM（用于 diff）',
    diff_json           JSON                                            COMMENT '{added,changed,removed}',
    status              VARCHAR(32) NOT NULL DEFAULT 'active'           COMMENT 'active/superseded',
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_drawing (drawing_id),
    INDEX idx_parent (parent_bom_id),
    INDEX idx_type_status (bom_type, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='BOM 表（支持版本叠加：raw_material + hardware + cost_sheet）';


-- -----------------------------------------------------------------------------
-- 3. ai_analyses (generic AI analysis results)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ai_analyses (
    id                  VARCHAR(36) PRIMARY KEY,
    subject_type        VARCHAR(32) NOT NULL                            COMMENT 'exception/quotation/drawing/outsourcing',
    subject_id          VARCHAR(36) NOT NULL                            COMMENT '关联对象ID',
    agent_key           VARCHAR(64) NOT NULL                            COMMENT 'simple_exception_agent / ...',
    result_json         JSON NOT NULL                                   COMMENT 'Agent 输出完整结果',
    steps_json          JSON                                            COMMENT 'Skill 调用链 snapshot',
    model_name          VARCHAR(64)                                     COMMENT 'LLM 模型',
    duration_ms         INT                                             COMMENT '总耗时',
    status              VARCHAR(32) NOT NULL                            COMMENT 'success/failed/timeout',
    error_message       TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_subject (subject_type, subject_id),
    INDEX idx_agent (agent_key, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='AI 分析结果（通用：异常/报价/图纸/委外决策均用此表）';


-- -----------------------------------------------------------------------------
-- 4. workflow_runs (lightweight workflow; future = workflow_instances)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflow_runs (
    id                  BINARY(16) PRIMARY KEY                          COMMENT 'UUID v4',
    workflow_key        VARCHAR(128) NOT NULL                           COMMENT 'exception_handling_v1 / quotation_review_v1 / ...',
    version             INT NOT NULL DEFAULT 1,
    status              VARCHAR(32) NOT NULL                            COMMENT 'pending/running/waiting_approval/completed/failed/cancelled',
    inputs_json         JSON                                            COMMENT '启动入参',
    outputs_json        JSON                                            COMMENT '最终结果',
    context_json        JSON                                            COMMENT '运行时状态（StateStore 持久化）',
    current_step        VARCHAR(128)                                    COMMENT '当前步骤名',
    next_step           VARCHAR(128)                                    COMMENT '审批回调要跑的下一步（RESUME_REGISTRY key）',
    trigger_source      VARCHAR(64)                                     COMMENT 'api/schedule/event',
    trigger_user        VARCHAR(128),
    lease_owner         VARCHAR(128)                                    COMMENT '多进程场景预留',
    lease_expires_at    DATETIME,
    error_message       TEXT,
    started_at          DATETIME NOT NULL,
    ended_at            DATETIME,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_key_status (workflow_key, status),
    INDEX idx_status (status),
    INDEX idx_lease (lease_owner, lease_expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='轻量工作流运行记录（未来可升级为 workflow_instances）';


-- -----------------------------------------------------------------------------
-- 5. notifications
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications (
    id                     VARCHAR(36) PRIMARY KEY,
    channel                VARCHAR(32) NOT NULL                         COMMENT 'email/in_app/sms',
    recipient              VARCHAR(255) NOT NULL                        COMMENT '收件人（邮箱/user_id/手机号）',
    subject                VARCHAR(255),
    body                   TEXT NOT NULL,
    related_subject_type   VARCHAR(32)                                  COMMENT 'exception/approval/quotation/...',
    related_subject_id     VARCHAR(36),
    status                 VARCHAR(32) NOT NULL DEFAULT 'pending'       COMMENT 'pending/sent/permanently_failed',
    retry_count            INT NOT NULL DEFAULT 0,
    last_error             TEXT,
    sent_at                DATETIME,
    created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_status_created (status, created_at),
    INDEX idx_recipient (recipient),
    INDEX idx_related (related_subject_type, related_subject_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='通知表（邮件/站内信）';


-- =============================================================================
-- Verification queries (optional, for manual validation)
-- =============================================================================
-- SHOW TABLES LIKE 'drawings';
-- SHOW TABLES LIKE 'boms';
-- SHOW TABLES LIKE 'ai_analyses';
-- SHOW TABLES LIKE 'workflow_runs';
-- SHOW TABLES LIKE 'notifications';
