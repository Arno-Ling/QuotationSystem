"""
测试 litellm 调用 MiMo API
"""
import os
from dotenv import load_dotenv
load_dotenv()

import litellm

API_KEY = os.getenv("OPENAI_API_KEY")
API_BASE = os.getenv("OPENAI_BASE_URL")
MODEL = os.getenv("EXCEPTION_AGENT_MODEL")

print("=" * 80)
print("测试 litellm 调用 MiMo")
print("=" * 80)
print(f"API Base: {API_BASE}")
print(f"Model: {MODEL}")

# 必须加 anthropic/ 前缀让litellm知道用anthropic provider
model_with_prefix = f"anthropic/{MODEL}"

print(f"\n使用模型: {model_with_prefix}")
print("发送测试请求...")

try:
    response = litellm.completion(
        model=model_with_prefix,
        messages=[
            {"role": "user", "content": "你好，请用一句话介绍你自己。"}
        ],
        api_key=API_KEY,
        api_base=API_BASE,
        max_tokens=200,
        temperature=0.3
    )
    
    print(f"\n✓ 成功!")
    print(f"响应: {response.choices[0].message.content}")
    print(f"\n使用情况:")
    if hasattr(response, 'usage'):
        print(f"  输入 tokens: {response.usage.prompt_tokens}")
        print(f"  输出 tokens: {response.usage.completion_tokens}")
        print(f"  总 tokens: {response.usage.total_tokens}")
    
except Exception as e:
    print(f"\n✗ 失败: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
