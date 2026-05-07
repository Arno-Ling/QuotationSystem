"""
测试正确的 MiMo API 域名
"""
import os
from dotenv import load_dotenv
load_dotenv()

import requests
import json

# 正确的 URL
CORRECT_URL = "https://token-plan-cn.xiaomimimo.com/anthropic"
API_KEY = "tp-cn0tro64vccki1wqosmy4d79v12alzqfnuv60ag1q5jvvwez"
MODEL = "MiMo-V2.5-Pro"

# 使用代理（因为需要翻墙）
PROXY = "http://127.0.0.1:7890"
proxies = {'http': PROXY, 'https': PROXY}

print("=" * 80)
print("测试正确的 MiMo API")
print("=" * 80)
print(f"\nURL: {CORRECT_URL}")
print(f"Model: {MODEL}")
print(f"Proxy: {PROXY}")

# 测试1: 不走代理，直连
print("\n" + "=" * 80)
print("测试1: 直连（不用代理）")
print("=" * 80)

try:
    url = f"{CORRECT_URL}/v1/messages"
    headers = {
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    data = {
        "model": MODEL,
        "max_tokens": 100,
        "messages": [{"role": "user", "content": "你好"}]
    }
    
    response = requests.post(
        url, 
        headers=headers, 
        json=data, 
        timeout=30,
        proxies={'http': None, 'https': None}
    )
    
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"✓ 成功!")
        print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
    else:
        print(f"响应: {response.text[:500]}")
        
except Exception as e:
    print(f"✗ 错误: {type(e).__name__}: {str(e)[:300]}")

# 测试2: 通过代理
print("\n" + "=" * 80)
print("测试2: 通过代理")
print("=" * 80)

try:
    url = f"{CORRECT_URL}/v1/messages"
    headers = {
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    data = {
        "model": MODEL,
        "max_tokens": 100,
        "messages": [{"role": "user", "content": "你好"}]
    }
    
    response = requests.post(
        url, 
        headers=headers, 
        json=data, 
        timeout=30,
        proxies=proxies
    )
    
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"✓ 成功!")
        print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
    else:
        print(f"响应: {response.text[:500]}")
        
except Exception as e:
    print(f"✗ 错误: {type(e).__name__}: {str(e)[:300]}")

print("\n" + "=" * 80)
