"""
Test script for exception analysis endpoint
"""
import requests
import json

# Test data
test_data = {
    "exception_id": "TEST001",
    "exception_type": "尺寸偏差",
    "description": "轴承座内径尺寸超差0.5mm，超出公差范围±0.2mm，影响装配精度",
    "related_entity_id": "PART001",
    "entity_type": "part",
    "project_id": "PROJ001",
    "supplier_id": "SUP001",
    "material": "钢",
    "process_type": "数控加工",
    "severity": "major",
    "quantity_affected": 50
}

print("=" * 80)
print("测试异常分析端点")
print("=" * 80)
print(f"\n请求数据:")
print(json.dumps(test_data, indent=2, ensure_ascii=False))

try:
    # Send POST request
    print(f"\n发送请求到: http://localhost:8000/api/exception/analyze")
    response = requests.post(
        "http://localhost:8000/api/exception/analyze",
        json=test_data,
        timeout=120  # 2 minutes timeout
    )
    
    print(f"\n响应状态码: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✓ 分析成功!")
        print(f"\n分析结果:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"\n✗ 分析失败!")
        print(f"错误信息: {response.text}")
        
except requests.exceptions.Timeout:
    print(f"\n✗ 请求超时 (120秒)")
except requests.exceptions.ConnectionError:
    print(f"\n✗ 无法连接到服务器，请确保服务器正在运行")
except Exception as e:
    print(f"\n✗ 发生错误: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
