-- =============================================================================
-- Migration 004: MVP Core (Stage 0 - 骨架)
-- =============================================================================
-- Creates 5 new tables for the Lightweight MVP:
--   1. tenants           - 租户（3 种类型：internal / processor / material）
--   2. users             - 用户账号（用户名+密码或手机号，关联 tenant_id）
--   3. projects          - 项目主档（基本信息+状态）
--   4. project_parts     - 项目下的零件清单
--   5. attachments       - 通用附件表（图纸、报价单等）
--
-- Idempotent: 所有 CREATE 使用 IF NOT EXISTS
-- Charset: utf8mb4
-- Engine: InnoDB
-- =============================================================================

USE mold_procurement;

-- -----------------------------------------------------------------------------
-- 1. tenants - 租户
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenants (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    tenant_type     VARCHAR(32) NOT NULL              COMMENT 'internal / processor / material',
    name            VARCHAR(255) NOT NULL UNIQUE      COMMENT '租户名称',
    supplier_id     INT                               COMMENT '关联 suppliers 表（若是外部供应商）',
    contact_name    VARCHAR(64),
    contact_phone   VARCHAR(32),
    contact_email   VARCHAR(128),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_type (tenant_type),
    INDEX idx_supplier (supplier_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='租户表（三种视角：我方/加工方/材料方）';

-- -----------------------------------------------------------------------------
-- 2. users - 用户账号
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    tenant_id       INT NOT NULL                      COMMENT '所属租户',
    username        VARCHAR(64) NOT NULL UNIQUE       COMMENT '登录用户名',
    password_hash   VARCHAR(255) NOT NULL             COMMENT 'bcrypt 哈希',
    phone           VARCHAR(32)                       COMMENT '手机号（MVP 先不用短信验证，仅展示）',
    display_name    VARCHAR(64) NOT NULL,
    role            VARCHAR(64)                       COMMENT '角色：admin / manager / operator / production_manager / purchasing_manager 等',
    is_active       TINYINT(1) NOT NULL DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_tenant (tenant_id),
    INDEX idx_phone (phone),
    CONSTRAINT fk_users_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='用户账号表';

-- -----------------------------------------------------------------------------
-- 3. projects - 项目主档
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS projects (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    tenant_id       INT NOT NULL                      COMMENT '所属租户（internal 租户）',
    project_no      VARCHAR(64) NOT NULL UNIQUE       COMMENT '项目编号',
    name            VARCHAR(255) NOT NULL             COMMENT '项目名称',
    customer        VARCHAR(255) NOT NULL             COMMENT '客户名称',
    deadline        DATE                              COMMENT '客户要求交期',
    unit_price      DECIMAL(14,2)                     COMMENT '客户确认的报价（单件）',
    quantity        INT                               COMMENT '订单数量',
    description     TEXT,
    status          VARCHAR(32) NOT NULL DEFAULT 'drafted'
                                                      COMMENT 'drafted / confirmed / deciding / decided / completed / cancelled',
    created_by      INT,
    confirmed_at    DATETIME                          COMMENT '人工确认完成时间（从 drafted 进入 confirmed）',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_tenant_status (tenant_id, status),
    INDEX idx_created_by (created_by),
    CONSTRAINT fk_projects_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='项目主档';

-- -----------------------------------------------------------------------------
-- 4. project_parts - 项目零件清单
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS project_parts (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    project_id      INT NOT NULL,
    part_no         VARCHAR(64) NOT NULL              COMMENT '零件号',
    part_name       VARCHAR(255),
    material        VARCHAR(64)                       COMMENT '材质，例如 45# 钢',
    qty             INT NOT NULL DEFAULT 1            COMMENT '该零件数量',
    processes_json  JSON                              COMMENT '工序清单，例如 ["磨","铣","热处理"]',
    spec            VARCHAR(255)                      COMMENT '规格描述',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_project (project_id),
    CONSTRAINT fk_parts_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='项目下的零件清单';

-- -----------------------------------------------------------------------------
-- 5. attachments - 通用附件表
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS attachments (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    related_type    VARCHAR(32) NOT NULL              COMMENT 'project / outsource_request / outsource_quotation / ...',
    related_id      INT NOT NULL                      COMMENT '关联对象 ID',
    file_name       VARCHAR(255) NOT NULL             COMMENT '原始文件名',
    file_path       VARCHAR(512) NOT NULL             COMMENT '存储路径，相对 backend/uploads/',
    file_size       INT                               COMMENT '字节',
    mime_type       VARCHAR(128),
    uploaded_by     INT,
    category        VARCHAR(64)                       COMMENT 'drawing / report / quote_sheet 等',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_related (related_type, related_id),
    INDEX idx_uploaded_by (uploaded_by)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='通用附件表';
