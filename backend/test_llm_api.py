"""
测试 LLM API (MiMo) 连接
"""
import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

print("=" * 80)
print("测试 LLM API 连接")
print("=" * 80)

# 读取配置
api_key = os.getenv("OPENAI_API_KEY")
api_base = os.getenv("OPENAI_BASE_URL")
model = os.getenv("EXCEPTION_AGENT_MODEL", os.getenv("OPENAI_MODEL"))

print(f"\n当前配置:")
print(f"  API Key: {api_key[:20]}..." if api_key else "  API Key: 未设置")
print(f"  API Base URL: {api_base}")
print(f"  Model: {model}")

# 测试1: 使用 litellm 直接调用
print("\n" + "=" * 80)
print("测试1: 使用 litellm 调用 MiMo API")
print("=" * 80)

try:
    import litellm
    
    # 开启详细日志
    litellm.set_verbose = True
    
    messages = [
        {"role": "user", "content": "你好，请用一句话介绍你自己。"}
    ]
    
    print(f"\n发送测试请求...")
    print(f"消息: {messages[0]['content']}")
    
    # 尝试多种模型名称格式
    model_variations = [
        model,  # 原始模型名
        f"anthropic/{model}",  # anthropic前缀
        f"openai/{model}",  # openai前缀
    ]
    
    success = False
    for try_model in model_variations:
        print(f"\n尝试模型名称: {try_model}")
        try:
            response = litellm.completion(
                model=try_model,
                messages=messages,
                api_key=api_key,
                api_base=api_base,
                max_tokens=100,
                temperature=0.3
            )
            
            print(f"✓ 成功!")
            print(f"响应: {response.choices[0].message.content}")
            print(f"使用的模型: {try_model}")
            success = True
            break
            
        except Exception as e:
            print(f"✗ 失败: {str(e)[:200]}")
    
    if not success:
        print("\n" + "=" * 80)
        print("所有模型名称格式都失败了")
        print("=" * 80)
        
except ImportError as e:
    print(f"✗ litellm 未安装: {e}")
except Exception as e:
    print(f"✗ 发生错误: {e}")
    import traceback
    traceback.print_exc()

# 测试2: 直接使用 HTTP 请求（Anthropic 格式）
print("\n" + "=" * 80)
print("测试2: 直接使用 HTTP 请求 (Anthropic Messages API)")
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
    print(f"请求头: {json.dumps(headers, indent=2, ensure_ascii=False)}")
    print(f"请求体: {json.dumps(data, indent=2, ensure_ascii=False)}")
    
    response = requests.post(url, headers=headers, json=data, timeout=30)
    
    print(f"\n状态码: {response.status_code}")
    print(f"响应头: {dict(response.headers)}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✓ 成功!")
        print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
    else:
        print(f"\n✗ 失败!")
        print(f"响应: {response.text}")
        
except Exception as e:
    print(f"✗ 发生错误: {e}")
    import traceback
    traceback.print_exc()

# 测试3: 使用 OpenAI 格式 (可能 MiMo 支持两种格式)
print("\n" + "=" * 80)
print("测试3: 使用 OpenAI 格式 (Chat Completions)")
print("=" * 80)

try:
    import requests
    import json
    
    # 尝试不同的URL后缀
    url_variations = [
        f"{api_base}/v1/chat/completions",
        f"{api_base}/chat/completions",
        f"{api_base}/v1/messages",
    ]
    
    for url in url_variations:
        print(f"\n尝试URL: {url}")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "max_tokens": 100,
            "messages": [
                {"role": "user", "content": "Hello"}
            ]
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✓ 成功!")
                print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)[:500]}")
                break
            else:
                print(f"响应: {response.text[:300]}")
                
        except Exception as e:
            print(f"错误: {str(e)[:200]}")
            
except Exception as e:
    print(f"✗ 发生错误: {e}")

print("\n" + "=" * 80)
print("测试完成")
print("=" * 80)
