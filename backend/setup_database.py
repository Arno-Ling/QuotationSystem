"""
创建数据库和表结构
"""
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', 3306))
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'mold_procurement')

print("=" * 80)
print("创建数据库和表结构")
print("=" * 80)

# 1. 连接MySQL（不指定数据库）创建数据库
print(f"\n[1/3] 连接到MySQL服务器并创建数据库 '{DB_NAME}'...")
try:
    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        charset='utf8mb4'
    )
    cursor = conn.cursor()
    
    # 创建数据库
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    conn.commit()
    print(f"✓ 数据库 '{DB_NAME}' 创建成功（或已存在）")
    
    cursor.close()
    conn.close()
except Exception as e:
    print(f"✗ 创建数据库失败: {e}")
    exit(1)

# 2. 连接到新数据库，创建exceptions表
print(f"\n[2/3] 创建 exceptions 表...")
try:
    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset='utf8mb4'
    )
    cursor = conn.cursor()
    
    # 创建exceptions表（包含AI分析字段）
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS exceptions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        exception_id VARCHAR(100) UNIQUE NOT NULL COMMENT '异常ID',
        exception_type VARCHAR(50) NOT NULL COMMENT '异常类型',
        description TEXT NOT NULL COMMENT '异常描述',
        related_entity_id VARCHAR(100) COMMENT '相关实体ID',
        entity_type VARCHAR(50) COMMENT '实体类型',
        project_id VARCHAR(100) COMMENT '项目ID',
        supplier_id VARCHAR(100) COMMENT '供应商ID',
        material VARCHAR(100) COMMENT '材料',
        process_type VARCHAR(100) COMMENT '工艺类型',
        severity VARCHAR(50) COMMENT '严重程度',
        quantity_affected INT COMMENT '受影响数量',
        responsible_party VARCHAR(100) COMMENT '责任方',
        resolution_plan TEXT COMMENT '解决方案',
        status VARCHAR(50) DEFAULT '待分析' COMMENT '状态',
        
        -- AI 分析字段
        ai_analysis_report JSON COMMENT 'AI分析报告JSON',
        ai_confidence_score FLOAT COMMENT 'AI责任判定置信度分数 (0-100)',
        ai_analysis_timestamp DATETIME COMMENT 'AI分析完成时间',
        
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        
        INDEX idx_exception_type (exception_type),
        INDEX idx_status (status),
        INDEX idx_ai_confidence_score (ai_confidence_score),
        INDEX idx_ai_analysis_timestamp (ai_analysis_timestamp)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='异常记录表'
    """
    
    cursor.execute(create_table_sql)
    conn.commit()
    print(f"✓ exceptions 表创建成功")
    
    # 3. 验证表结构
    print(f"\n[3/3] 验证表结构...")
    cursor.execute("DESCRIBE exceptions")
    columns = cursor.fetchall()
    
    print(f"\nexceptions 表字段:")
    for col in columns:
        field_name = col[0]
        field_type = col[1]
        marker = "🤖" if field_name.startswith('ai_') else "  "
        print(f"  {marker} {field_name}: {field_type}")
    
    # 检查AI字段
    ai_columns = [col for col in columns if col[0].startswith('ai_')]
    print(f"\n✓ AI分析字段已添加: {len(ai_columns)} 个")
    
    # 插入一条测试数据
    print(f"\n插入测试数据...")
    cursor.execute("""
        INSERT IGNORE INTO exceptions 
        (exception_id, exception_type, description, related_entity_id, entity_type, project_id, supplier_id, material, process_type, severity, quantity_affected)
        VALUES 
        ('TEST001', '尺寸偏差', '轴承座内径尺寸超差0.5mm', 'PART001', 'part', 'PROJ001', 'SUP001', '钢', '数控加工', 'major', 50)
    """)
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM exceptions")
    count = cursor.fetchone()[0]
    print(f"✓ 表中现有 {count} 条记录")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 80)
    print("✓ 数据库设置完成！")
    print("=" * 80)
    print(f"\n数据库信息:")
    print(f"  主机: {DB_HOST}:{DB_PORT}")
    print(f"  数据库: {DB_NAME}")
    print(f"  表: exceptions (包含AI分析字段)")
    print(f"  记录数: {count}")
    
except Exception as e:
    print(f"✗ 失败: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
