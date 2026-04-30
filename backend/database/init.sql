-- 模具委外采购系统数据库初始化脚本
-- 创建数据库
CREATE DATABASE IF NOT EXISTS mold_procurement CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE mold_procurement;

-- 用户表 (用于认证和权限管理)
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY COMMENT '用户ID',
    username VARCHAR(50) UNIQUE NOT NULL COMMENT '用户名',
    password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希',
    role VARCHAR(50) NOT NULL COMMENT '用户角色 (e.g., 项目经理, 采购员, 质检主管)',
    email VARCHAR(100) UNIQUE COMMENT '邮箱',
    phone VARCHAR(20) UNIQUE COMMENT '电话',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_username (username),
    INDEX idx_email (email),
    INDEX idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- 项目表
CREATE TABLE IF NOT EXISTS projects (
    id VARCHAR(36) PRIMARY KEY COMMENT '项目ID',
    project_name VARCHAR(255) NOT NULL COMMENT '项目名称',
    description TEXT COMMENT '项目描述',
    status VARCHAR(50) NOT NULL COMMENT '项目状态 (e.g., 待报价, 生产中, 已交付, 已完成)',
    start_date DATE COMMENT '项目开始日期',
    end_date DATE COMMENT '项目结束日期',
    manager_id VARCHAR(36) COMMENT '项目经理ID',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_status (status),
    INDEX idx_manager (manager_id),
    INDEX idx_dates (start_date, end_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='项目表';

-- 模具表 (一个项目可能包含多个模具)
CREATE TABLE IF NOT EXISTS molds (
    id VARCHAR(36) PRIMARY KEY COMMENT '模具ID',
    project_id VARCHAR(36) NOT NULL COMMENT '所属项目ID',
    mold_name VARCHAR(255) NOT NULL COMMENT '模具名称',
    mold_number VARCHAR(100) UNIQUE NOT NULL COMMENT '模具编号',
    status VARCHAR(50) NOT NULL COMMENT '模具状态',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    INDEX idx_project (project_id),
    INDEX idx_mold_number (mold_number),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='模具表';

-- 零件表 (一个模具包含多个零件)
CREATE TABLE IF NOT EXISTS parts (
    id VARCHAR(36) PRIMARY KEY COMMENT '零件ID',
    mold_id VARCHAR(36) NOT NULL COMMENT '所属模具ID',
    part_name VARCHAR(255) NOT NULL COMMENT '零件名称',
    part_number VARCHAR(100) UNIQUE NOT NULL COMMENT '零件编号',
    material VARCHAR(100) COMMENT '材料',
    quantity INT NOT NULL COMMENT '数量',
    moq INT DEFAULT 1 COMMENT '最小起订量',
    drawing_id VARCHAR(36) COMMENT '关联图纸ID',
    status VARCHAR(50) NOT NULL COMMENT '零件状态',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (mold_id) REFERENCES molds(id) ON DELETE CASCADE,
    INDEX idx_mold (mold_id),
    INDEX idx_part_number (part_number),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='零件表';

-- 供应商表
CREATE TABLE IF NOT EXISTS suppliers (
    id VARCHAR(36) PRIMARY KEY COMMENT '供应商ID',
    supplier_name VARCHAR(255) UNIQUE NOT NULL COMMENT '供应商名称',
    category VARCHAR(100) COMMENT '供应商大分类',
    address TEXT COMMENT '详细地址',
    contact_person VARCHAR(100) COMMENT '联系人',
    contact_phone VARCHAR(20) COMMENT '联系电话',
    capabilities JSON COMMENT '可提供服务/加工能力 (JSON数组)',
    rating DECIMAL(2,1) COMMENT '供应商评级',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_supplier_name (supplier_name),
    INDEX idx_category (category),
    INDEX idx_rating (rating)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='供应商表';

-- 委外询价单
CREATE TABLE IF NOT EXISTS inquiries (
    id VARCHAR(36) PRIMARY KEY COMMENT '询价单ID',
    project_id VARCHAR(36) NOT NULL COMMENT '所属项目ID',
    part_id VARCHAR(36) COMMENT '关联零件ID',
    process_id VARCHAR(36) COMMENT '关联工序ID (如果只询价工序)',
    inquiry_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '询价日期',
    due_date DATE COMMENT '期望交期',
    quantity INT NOT NULL COMMENT '询价数量',
    technical_requirements TEXT COMMENT '技术要求',
    drawing_link VARCHAR(255) COMMENT '图纸加密链接',
    status VARCHAR(50) NOT NULL COMMENT '询价状态 (e.g., 待发送, 已发送, 已报价, 已关闭)',
    created_by VARCHAR(36) COMMENT '创建人ID',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_project (project_id),
    INDEX idx_part (part_id),
    INDEX idx_status (status),
    INDEX idx_dates (inquiry_date, due_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='委外询价单';

-- 委外报价单 (供应商回复)
CREATE TABLE IF NOT EXISTS quotations (
    id VARCHAR(36) PRIMARY KEY COMMENT '报价单ID',
    inquiry_id VARCHAR(36) NOT NULL COMMENT '关联询价单ID',
    supplier_id VARCHAR(36) NOT NULL COMMENT '供应商ID',
    quotation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '报价日期',
    unit_price DECIMAL(10,4) NOT NULL COMMENT '单价',
    delivery_date DATE COMMENT '供应商承诺交期',
    total_amount DECIMAL(10,2) NOT NULL COMMENT '总金额',
    remarks TEXT COMMENT '备注',
    is_assembly_included BOOLEAN DEFAULT FALSE COMMENT '是否包含组装',
    quotation_file_path VARCHAR(255) COMMENT '报价单文件路径 (OCR/AI解析源)',
    status VARCHAR(50) NOT NULL COMMENT '报价状态 (e.g., 待审核, 已接受, 已拒绝)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (inquiry_id) REFERENCES inquiries(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE,
    INDEX idx_inquiry (inquiry_id),
    INDEX idx_supplier (supplier_id),
    INDEX idx_status (status),
    INDEX idx_dates (quotation_date, delivery_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='委外报价单';

-- 委外加工单 (最终确认的订单)
CREATE TABLE IF NOT EXISTS outsourced_orders (
    id VARCHAR(36) PRIMARY KEY COMMENT '委外加工单ID',
    project_id VARCHAR(36) NOT NULL COMMENT '所属项目ID',
    part_id VARCHAR(36) COMMENT '关联零件ID',
    process_id VARCHAR(36) COMMENT '关联工序ID',
    supplier_id VARCHAR(36) NOT NULL COMMENT '供应商ID',
    quotation_id VARCHAR(36) COMMENT '关联报价单ID',
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '下单日期',
    delivery_date DATE NOT NULL COMMENT '承诺交期',
    actual_delivery_date DATE COMMENT '实际交付日期',
    quantity INT NOT NULL COMMENT '加工数量',
    unit_price DECIMAL(10,4) NOT NULL COMMENT '单价',
    total_amount DECIMAL(10,2) NOT NULL COMMENT '总金额',
    is_assembly_included BOOLEAN DEFAULT FALSE COMMENT '是否包含组装',
    status VARCHAR(50) NOT NULL COMMENT '订单状态 (e.g., 待生产, 生产中, 已完成, 已入库, 已结算)',
    created_by VARCHAR(36) COMMENT '创建人ID',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE SET NULL,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE RESTRICT,
    FOREIGN KEY (quotation_id) REFERENCES quotations(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_project (project_id),
    INDEX idx_supplier (supplier_id),
    INDEX idx_status (status),
    INDEX idx_dates (order_date, delivery_date, actual_delivery_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='委外加工单';

-- 异常单
CREATE TABLE IF NOT EXISTS exceptions (
    id VARCHAR(36) PRIMARY KEY COMMENT '异常单ID',
    project_id VARCHAR(36) NOT NULL COMMENT '所属项目ID',
    related_entity_id VARCHAR(36) COMMENT '关联实体ID (如零件ID, 委外加工单ID)',
    entity_type VARCHAR(50) COMMENT '关联实体类型 (e.g., part, outsourced_order)',
    exception_type VARCHAR(100) NOT NULL COMMENT '异常类型 (e.g., 尺寸超差, 变形, 材料缺陷, 加工失误)',
    description TEXT NOT NULL COMMENT '异常描述',
    report_by VARCHAR(36) COMMENT '报告人ID',
    report_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '报告时间',
    responsible_party VARCHAR(100) COMMENT '责任方 (e.g., 内部, 供应商, 材料商)',
    ai_analysis_report TEXT COMMENT 'AI分析报告草案',
    evidence_package_path VARCHAR(255) COMMENT '证据包文件路径',
    resolution_plan TEXT COMMENT '解决方案',
    status VARCHAR(50) NOT NULL COMMENT '异常状态 (e.g., 待处理, 溯源中, 待确认, 已解决, 暂缓处理)',
    is_temporary_ignored BOOLEAN DEFAULT FALSE COMMENT '是否临时忽略/让步接收',
    compensation_plan TEXT COMMENT '补偿计划 (如果临时忽略)',
    due_date DATE COMMENT '待办提醒日期 (如果暂缓处理)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (report_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_project (project_id),
    INDEX idx_entity (related_entity_id, entity_type),
    INDEX idx_status (status),
    INDEX idx_exception_type (exception_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='异常单';

-- 任务表 (用于看板和流程管理)
CREATE TABLE IF NOT EXISTS tasks (
    id VARCHAR(36) PRIMARY KEY COMMENT '任务ID',
    project_id VARCHAR(36) NOT NULL COMMENT '所属项目ID',
    task_name VARCHAR(255) NOT NULL COMMENT '任务名称',
    description TEXT COMMENT '任务描述',
    assigned_to VARCHAR(36) COMMENT '负责人ID',
    status VARCHAR(50) NOT NULL COMMENT '任务状态 (e.g., 待处理, 进行中, 已完成, 已挂起)',
    priority VARCHAR(20) COMMENT '优先级 (e.g., 低, 中, 高)',
    start_date DATE COMMENT '计划开始日期',
    due_date DATE COMMENT '计划截止日期',
    actual_start_date TIMESTAMP COMMENT '实际开始时间',
    actual_end_date TIMESTAMP COMMENT '实际结束时间',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_project (project_id),
    INDEX idx_assigned (assigned_to),
    INDEX idx_status (status),
    INDEX idx_priority (priority),
    INDEX idx_dates (start_date, due_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='任务表';

-- 人机交互任务表 (Human-in-the-Loop)
CREATE TABLE IF NOT EXISTS human_review_tasks (
    id VARCHAR(36) PRIMARY KEY COMMENT '人机审核任务ID',
    project_id VARCHAR(36) NOT NULL COMMENT '所属项目ID',
    related_entity_id VARCHAR(36) COMMENT '关联实体ID (如零件ID, 委外加工单ID)',
    entity_type VARCHAR(50) COMMENT '关联实体类型 (e.g., part, outsourced_order, quotation)',
    review_type VARCHAR(100) NOT NULL COMMENT '审核类型 (e.g., outsourcing_decision, quotation_review, exception_resolution)',
    description TEXT NOT NULL COMMENT '任务描述/审核内容',
    assigned_to VARCHAR(36) COMMENT '指派给的用户ID',
    status VARCHAR(50) NOT NULL COMMENT '任务状态 (e.g., pending, approved, rejected, modification_requested)',
    feedback_action VARCHAR(50) COMMENT '人工反馈动作 (e.g., approve, reject, request_modification)',
    feedback_reason TEXT COMMENT '人工反馈理由/修改意见',
    feedback_by VARCHAR(36) COMMENT '反馈人ID',
    feedback_at TIMESTAMP COMMENT '反馈时间',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (feedback_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_project (project_id),
    INDEX idx_entity (related_entity_id, entity_type),
    INDEX idx_status (status),
    INDEX idx_review_type (review_type),
    INDEX idx_assigned (assigned_to)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='人机交互任务表';

-- 插入测试用户数据
INSERT INTO users (id, username, password_hash, role, email, phone) VALUES
('user-001', 'admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqVqN4qQzG', '管理员', 'admin@example.com', '13800138000'),
('user-002', 'manager1', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqVqN4qQzG', '项目经理', 'manager1@example.com', '13800138001'),
('user-003', 'buyer1', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqVqN4qQzG', '采购员', 'buyer1@example.com', '13800138002'),
('user-004', 'qc1', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqVqN4qQzG', '质检主管', 'qc1@example.com', '13800138003');

-- 插入测试供应商数据
INSERT INTO suppliers (id, supplier_name, category, address, contact_person, contact_phone, capabilities, rating) VALUES
('supplier-001', '青岛精密加工厂', '机械加工', '山东省青岛市', '张三', '13900139001', '["热处理", "线切割", "CNC加工"]', 4.5),
('supplier-002', '苏州模具制造有限公司', '模具制造', '江苏省苏州市', '李四', '13900139002', '["模具设计", "模具制造", "注塑"]', 4.8),
('supplier-003', '深圳表面处理中心', '表面处理', '广东省深圳市', '王五', '13900139003', '["电镀", "喷涂", "阳极氧化"]', 4.2);
