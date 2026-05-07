-- =============================================================================
-- Migration 006: Outsource Requests & Orders (Stage 3 — 委外询价闭环)
-- =============================================================================
-- 5 new tables:
--   1. outsource_requests             - 委外询价单
--   2. outsource_request_invitations  - 询价邀请（询价单 × 加工方）
--   3. outsource_quotations           - 加工方报价
--   4. outsource_orders               - 正式委外加工单
--   5. outsource_order_status_events  - 加工单状态日志
-- =============================================================================

USE mold_procurement;

-- -----------------------------------------------------------------------------
-- 1. outsource_requests  (委外询价单)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS outsource_requests (
    id                         INT AUTO_INCREMENT PRIMARY KEY,
    project_id                 INT NOT NULL,
    title                      VARCHAR(255) NOT NULL,
    required_processes_json    JSON NOT NULL              COMMENT '["热处理","线割",...]',
    quantity                   INT,
    deadline                   DATE,
    status                     VARCHAR(32) NOT NULL DEFAULT 'draft'
                                                           COMMENT 'draft / inviting / comparing / pending_award / awarded / cancelled',
    closed_at                  DATETIME                   COMMENT '截止报价时间',
    approval_task_id           BIGINT                     COMMENT '关联采购经理审批任务',
    winning_quotation_id       INT                        COMMENT '中标报价 ID（awarded 时）',
    created_by                 INT,
    created_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_project (project_id),
    INDEX idx_status (status),
    CONSTRAINT fk_req_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='委外询价单';


-- -----------------------------------------------------------------------------
-- 2. outsource_request_invitations  (询价邀请)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS outsource_request_invitations (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    request_id        INT NOT NULL,
    supplier_id       INT NOT NULL,
    tenant_id         INT                            COMMENT '对应 processor 租户（便于加工方查询）',
    invitation_status VARCHAR(32) NOT NULL DEFAULT 'sent'
                                                     COMMENT 'sent / quoted / no_response / cancelled',
    sent_at           DATETIME NOT NULL,
    quoted_at         DATETIME,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_request_supplier (request_id, supplier_id),
    INDEX idx_request (request_id),
    INDEX idx_tenant_status (tenant_id, invitation_status),
    CONSTRAINT fk_inv_request  FOREIGN KEY (request_id)  REFERENCES outsource_requests(id) ON DELETE CASCADE,
    CONSTRAINT fk_inv_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='询价邀请（群发）';


-- -----------------------------------------------------------------------------
-- 3. outsource_quotations  (加工方报价)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS outsource_quotations (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    invitation_id     INT NOT NULL UNIQUE              COMMENT '一个邀请一个报价',
    unit_price        DECIMAL(14,2) NOT NULL,
    lead_time_days    INT NOT NULL                     COMMENT '交期（天）',
    note              TEXT,
    submitted_by      INT                              COMMENT '加工方账号 users.id',
    submitted_at      DATETIME NOT NULL,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_invitation (invitation_id),
    CONSTRAINT fk_quote_invitation FOREIGN KEY (invitation_id) REFERENCES outsource_request_invitations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='加工方针对询价邀请的报价';


-- -----------------------------------------------------------------------------
-- 4. outsource_orders  (正式委外加工单)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS outsource_orders (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    request_id        INT NOT NULL,
    quotation_id      INT NOT NULL                     COMMENT '中标报价',
    supplier_id       INT NOT NULL,
    tenant_id         INT                              COMMENT '对应 processor 租户',
    order_no          VARCHAR(64) NOT NULL UNIQUE,
    unit_price        DECIMAL(14,2) NOT NULL,
    quantity          INT NOT NULL,
    total_amount      DECIMAL(14,2)                    COMMENT 'unit_price * quantity',
    lead_time_days    INT NOT NULL,
    status            VARCHAR(32) NOT NULL DEFAULT 'awarded'
                                                       COMMENT 'awarded / accepted / producing / delivered / cancelled',
    awarded_at        DATETIME NOT NULL,
    accepted_at       DATETIME,
    delivered_at      DATETIME,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_request (request_id),
    INDEX idx_supplier_status (supplier_id, status),
    INDEX idx_tenant_status (tenant_id, status),
    CONSTRAINT fk_order_request  FOREIGN KEY (request_id)   REFERENCES outsource_requests(id),
    CONSTRAINT fk_order_quote    FOREIGN KEY (quotation_id) REFERENCES outsource_quotations(id),
    CONSTRAINT fk_order_supplier FOREIGN KEY (supplier_id)  REFERENCES suppliers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='正式委外加工单';


-- -----------------------------------------------------------------------------
-- 5. outsource_order_status_events  (加工单状态日志)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS outsource_order_status_events (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    order_id       INT NOT NULL,
    from_status    VARCHAR(32),
    to_status      VARCHAR(32) NOT NULL,
    changed_by     INT                                  COMMENT '操作人 users.id',
    note           VARCHAR(512),
    occurred_at    DATETIME NOT NULL,
    INDEX idx_order (order_id, occurred_at),
    CONSTRAINT fk_evt_order FOREIGN KEY (order_id) REFERENCES outsource_orders(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='委外加工单状态变更日志';
