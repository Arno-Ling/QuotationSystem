"""
测试 LLM API - 绕过系统代理
"""
import os
import sys

# 在加载任何网络库之前，清除代理设置
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'
# 清除可能存在的代理
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(key, None)

from dotenv import load_dotenv
load_dotenv()

print("=" * 80)
print("测试 LLM API 连接（绕过代理）")
print("=" * 80)

api_key = os.getenv("OPENAI_API_KEY")
api_base = os.getenv("OPENAI_BASE_URL")
model = os.getenv("EXCEPTION_AGENT_MODEL", os.getenv("OPENAI_MODEL"))

print(f"\n配置:")
print(f"  API Key: {api_key[:20]}...")
print(f"  API Base: {api_base}")
print(f"  Model: {model}")
print(f"  代理已禁用: NO_PROXY=*")

# 测试: 使用 requests 直接连接（禁用代理）
print("\n" + "=" * 80)
print("测试: 直接 HTTP 请求（Anthropic格式，禁用代理）")
print("=" * 80)

try:
    import requests
    import json
    
    url = f"{api_base}/v1/messages"
    
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    data = {
        "model": model,
        "max_tokens": 100,
        "messages": [
            {"role": "user", "content": "你好，请用一句话介绍你自己。"}
        ]
    }
    
    print(f"\nURL: {url}")
    print(f"Model: {model}")
    
    # 显式禁用代理
    response = requests.post(
        url, 
        headers=headers, 
        json=data, 
        timeout=30,
        proxies={'http': None, 'https': None}  # 禁用代理
    )
    
    print(f"\n状态码: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✓ 成功!")
        print(f"\n响应内容:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # 提取文本
        if 'content' in result and len(result['content']) > 0:
            text = result['content'][0].get('text', '')
            print(f"\n模型回复: {text}")
    else:
        print(f"\n✗ 失败!")
        print(f"响应: {response.text}")
        
except Exception as e:
    print(f"✗ 发生错误: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
