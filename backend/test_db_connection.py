"""
Test database connection
"""
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 80)
print("测试数据库连接")
print("=" * 80)

# 读取配置
db_config = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'mold_procurement')
}

print(f"\n数据库配置:")
print(f"  Host: {db_config['host']}")
print(f"  Port: {db_config['port']}")
print(f"  User: {db_config['user']}")
print(f"  Password: {'*' * len(db_config['password'])}")
print(f"  Database: {db_config['database']}")

# 测试1: 不指定数据库，只连接MySQL
print(f"\n测试1: 连接到MySQL服务器（不指定数据库）...")
try:
    conn = pymysql.connect(
        host=db_config['host'],
        port=db_config['port'],
        user=db_config['user'],
        password=db_config['password']
    )
    print("✓ 成功连接到MySQL服务器!")
    
    cursor = conn.cursor()
    cursor.execute("SHOW DATABASES;")
    databases = cursor.fetchall()
    print(f"\n可用的数据库:")
    for db in databases:
        print(f"  - {db[0]}")
    
    # 检查目标数据库是否存在
    db_exists = any(db[0] == db_config['database'] for db in databases)
    if db_exists:
        print(f"\n✓ 数据库 '{db_config['database']}' 存在")
    else:
        print(f"\n⚠ 数据库 '{db_config['database']}' 不存在")
        print(f"  需要创建数据库: CREATE DATABASE {db_config['database']};")
    
    conn.close()
    
except pymysql.err.OperationalError as e:
    print(f"✗ 连接失败: {e}")
    print(f"\n可能的原因:")
    print(f"  1. MySQL服务未启动")
    print(f"  2. 用户名或密码不正确")
    print(f"  3. 主机地址不正确")
    exit(1)

# 测试2: 连接到指定数据库
print(f"\n测试2: 连接到数据库 '{db_config['database']}'...")
try:
    conn = pymysql.connect(**db_config)
    print(f"✓ 成功连接到数据库 '{db_config['database']}'!")
    
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES;")
    tables = cursor.fetchall()
    
    if tables:
        print(f"\n数据库中的表:")
        for table in tables:
            print(f"  - {table[0]}")
        
        # 检查 exceptions 表是否存在
        table_names = [table[0] for table in tables]
        if 'exceptions' in table_names:
            print(f"\n✓ 'exceptions' 表存在")
            
            # 检查 AI 分析字段
            cursor.execute("DESCRIBE exceptions;")
            columns = cursor.fetchall()
            ai_columns = [col for col in columns if col[0].startswith('ai_')]
            
            if ai_columns:
                print(f"\n✓ AI分析字段已添加:")
                for col in ai_columns:
                    print(f"  - {col[0]} ({col[1]})")
            else:
                print(f"\n⚠ AI分析字段未添加")
                print(f"  需要运行迁移脚本: python run_migration.py")
        else:
            print(f"\n⚠ 'exceptions' 表不存在")
    else:
        print(f"\n⚠ 数据库中没有表")
    
    conn.close()
    
except pymysql.err.OperationalError as e:
    if '1049' in str(e):  # Unknown database
        print(f"✗ 数据库 '{db_config['database']}' 不存在")
        print(f"\n需要创建数据库:")
        print(f"  mysql -u {db_config['user']} -p")
        print(f"  CREATE DATABASE {db_config['database']};")
    else:
        print(f"✗ 连接失败: {e}")
    exit(1)

print("\n" + "=" * 80)
print("✓ 所有测试通过!")
print("=" * 80)
