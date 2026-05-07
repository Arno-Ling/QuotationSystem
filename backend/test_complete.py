"""
完整端到端测试 - LLM + Agent + Database
"""
import requests
import json

print("=" * 80)
print("完整端到端测试：异常分析系统")
print("=" * 80)

test_data = {
    "exception_id": "TEST002",
    "exception_type": "尺寸偏差",
    "description": "轴承座内径尺寸超差0.5mm，超出公差范围0.2mm，影响装配精度",
    "related_entity_id": "PART002",
    "entity_type": "part",
    "project_id": "PROJ001",
    "supplier_id": "SUP001",
    "material": "钢",
    "process_type": "数控加工",
    "severity": "major",
    "quantity_affected": 50
}

print("\n发送请求...")
print(f"URL: http://localhost:8000/api/exception/analyze")
print(f"数据: {json.dumps(test_data, indent=2, ensure_ascii=False)}")

try:
    response = requests.post(
        "http://localhost:8000/api/exception/analyze",
        json=test_data,
        timeout=180
    )
    
    print(f"\n[状态码] {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        
        print("\n" + "=" * 80)
        print("[成功] 分析完成!")
        print("=" * 80)
        
        print(f"\n[Agent执行步数] {result.get('agent_steps', 'N/A')}")
        print(f"[时间戳] {result.get('timestamp', 'N/A')}")
        
        # 打印分析报告
        report = result.get('analysis_report', '')
        if report:
            print("\n" + "=" * 80)
            print("[分析报告]")
            print("=" * 80)
            print(report)
        
        # 检查数据库更新
        db_warning = result.get('database_update_warning')
        if db_warning:
            print(f"\n[数据库警告] {db_warning}")
        else:
            print("\n[数据库] 成功写入")
        
        # 保存到文件
        with open('test_result.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print("\n[已保存] 完整结果保存到 test_result.json")
        
    else:
        print(f"\n[失败]")
        print(f"响应: {response.text}")
        
except requests.exceptions.Timeout:
    print("\n[超时] 请求超时（180秒）")
except Exception as e:
    print(f"\n[错误] {type(e).__name__}: {e}")

print("\n" + "=" * 80)
