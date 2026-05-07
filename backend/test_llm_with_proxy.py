"""
测试 LLM API - 使用代理
"""
import os
from dotenv import load_dotenv
load_dotenv()

# 明确设置代理
PROXY = "http://127.0.0.1:7890"
os.environ['HTTP_PROXY'] = PROXY
os.environ['HTTPS_PROXY'] = PROXY
os.environ['http_proxy'] = PROXY
os.environ['https_proxy'] = PROXY

print("=" * 80)
print("测试 LLM API 连接（通过代理）")
print("=" * 80)

api_key = os.getenv("OPENAI_API_KEY")
api_base = os.getenv("OPENAI_BASE_URL")
model = os.getenv("EXCEPTION_AGENT_MODEL", os.getenv("OPENAI_MODEL"))

print(f"\n配置:")
print(f"  API Key: {api_key[:20]}...")
print(f"  API Base: {api_base}")
print(f"  Model: {model}")
print(f"  Proxy: {PROXY}")

# 测试1: 使用代理的 HTTP 请求
print("\n" + "=" * 80)
print("测试1: Anthropic格式请求")
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
            {"role": "user", "content": "你好"}
        ]
    }
    
    proxies = {
        'http': PROXY,
        'https': PROXY,
    }
    
    print(f"\nURL: {url}")
    print(f"发送请求...")
    
    response = requests.post(
        url, 
        headers=headers, 
        json=data, 
        timeout=30,
        proxies=proxies,
        verify=True
    )
    
    print(f"\n状态码: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✓ 成功!")
        print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
    else:
        print(f"\n✗ 失败!")
        print(f"响应: {response.text}")
        
except Exception as e:
    print(f"✗ 发生错误: {type(e).__name__}: {e}")

# 测试2: 尝试 OpenAI 格式
print("\n" + "=" * 80)
print("测试2: OpenAI格式请求")
print("=" * 80)

try:
    url2 = f"{api_base}/v1/chat/completions"
    
    headers2 = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data2 = {
        "model": model,
        "max_tokens": 100,
        "messages": [
            {"role": "user", "content": "你好"}
        ]
    }
    
    print(f"\nURL: {url2}")
    
    response2 = requests.post(
        url2,
        headers=headers2,
        json=data2,
        timeout=30,
        proxies=proxies
    )
    
    print(f"状态码: {response2.status_code}")
    
    if response2.status_code == 200:
        print(f"\n✓ 成功!")
        print(f"响应: {json.dumps(response2.json(), indent=2, ensure_ascii=False)}")
    else:
        print(f"响应: {response2.text[:500]}")
        
except Exception as e:
    print(f"✗ 发生错误: {type(e).__name__}: {e}")

# 测试3: 使用 litellm
print("\n" + "=" * 80)
print("测试3: 使用 litellm")
print("=" * 80)

try:
    import litellm
    
    # 尝试 anthropic 格式
    response = litellm.completion(
        model=f"anthropic/{model}",
        messages=[{"role": "user", "content": "你好"}],
        api_key=api_key,
        api_base=api_base,
        max_tokens=100
    )
    
    print(f"\n✓ 成功!")
    print(f"响应: {response.choices[0].message.content}")
    
except Exception as e:
    print(f"✗ 发生错误: {type(e).__name__}: {str(e)[:500]}")

print("\n" + "=" * 80)
