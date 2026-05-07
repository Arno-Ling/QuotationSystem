"""
测试 MiMo API 支持的模型名称
"""
import os
from dotenv import load_dotenv
load_dotenv()

import requests
import json

URL = "https://token-plan-cn.xiaomimimo.com/anthropic"
API_KEY = "tp-cn0tro64vccki1wqosmy4d79v12alzqfnuv60ag1q5jvvwez"

# 尝试多种可能的模型名称
model_variations = [
    "mimo-v2.5-pro",
    "MiMo-V2.5-Pro",
    "mimo-v2-5-pro",
    "MiMo-v2.5",
    "mimo-pro",
    "mimo",
    "MiMo",
    "MiMo-V2.5",
    "mimo-2.5-pro",
    "claude-3-sonnet-20240229",  # 可能支持claude模型
    "claude-3-5-sonnet-20241022",
    "claude-sonnet-4",
    "claude-haiku-3-5",
    "anthropic.claude-3-sonnet",
    "xiaomi-mimo-pro",
    "xiaomi/mimo-pro",
]

print("=" * 80)
print("查找支持的 MiMo 模型")
print("=" * 80)

# 先试试 /v1/models 端点
print("\n测试: GET /v1/models 列出可用模型")
try:
    response = requests.get(
        f"{URL}/v1/models",
        headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01"},
        timeout=15,
        proxies={'http': None, 'https': None}
    )
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.text[:1000]}")
except Exception as e:
    print(f"错误: {e}")

# 逐个测试模型名称
print("\n" + "=" * 80)
print("逐个测试模型名称")
print("=" * 80)

working_models = []

for model in model_variations:
    try:
        response = requests.post(
            f"{URL}/v1/messages",
            headers={
                "x-api-key": API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": model,
                "max_tokens": 20,
                "messages": [{"role": "user", "content": "hi"}]
            },
            timeout=15,
            proxies={'http': None, 'https': None}
        )
        
        status = response.status_code
        if status == 200:
            print(f"✓ {model} - 成功!")
            working_models.append(model)
            result = response.json()
            if 'content' in result and result['content']:
                print(f"   响应: {result['content'][0].get('text', '')[:100]}")
        elif status == 400:
            error = response.json().get('error', {}).get('message', '')
            if 'Not supported model' in error or 'model' in error.lower():
                print(f"✗ {model} - 不支持")
            else:
                print(f"? {model} - 400: {error[:100]}")
        elif status == 401:
            print(f"⚠ {model} - 401 认证失败，可能是API key问题")
        else:
            print(f"? {model} - {status}: {response.text[:100]}")
            
    except Exception as e:
        print(f"✗ {model} - 错误: {str(e)[:80]}")

print("\n" + "=" * 80)
print("总结")
print("=" * 80)
if working_models:
    print(f"\n✓ 可用的模型:")
    for m in working_models:
        print(f"   - {m}")
else:
    print("\n✗ 没有找到可用的模型，请联系API提供商确认正确的模型名称")
