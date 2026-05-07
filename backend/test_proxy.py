"""
测试代理本身是否工作
"""
import os
import requests

PROXY = "http://127.0.0.1:7890"
proxies = {'http': PROXY, 'https': PROXY}

print("=" * 80)
print("测试代理连接")
print("=" * 80)

# 测试1: 测试代理是否可达
print("\n测试1: 检查代理端口是否开放")
try:
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    result = sock.connect_ex(('127.0.0.1', 7890))
    sock.close()
    if result == 0:
        print("✓ 代理端口 7890 可达")
    else:
        print(f"✗ 代理端口 7890 不可达 (错误码: {result})")
        print("   → 代理软件可能没运行，请启动Clash/V2Ray等代理软件")
except Exception as e:
    print(f"✗ 检查失败: {e}")

# 测试2: 通过代理访问Google
print("\n测试2: 通过代理访问 Google (验证代理能翻墙)")
try:
    r = requests.get("https://www.google.com", proxies=proxies, timeout=10, verify=False)
    print(f"✓ 状态码: {r.status_code}")
except Exception as e:
    print(f"✗ 失败: {type(e).__name__}: {str(e)[:200]}")

# 测试3: 访问百度（不需要代理的网站）
print("\n测试3: 通过代理访问百度")
try:
    r = requests.get("https://www.baidu.com", proxies=proxies, timeout=10)
    print(f"✓ 状态码: {r.status_code}")
except Exception as e:
    print(f"✗ 失败: {type(e).__name__}: {str(e)[:200]}")

# 测试4: 不通过代理访问百度
print("\n测试4: 不通过代理访问百度（直连）")
try:
    r = requests.get("https://www.baidu.com", timeout=10, proxies={'http': None, 'https': None})
    print(f"✓ 状态码: {r.status_code}")
except Exception as e:
    print(f"✗ 失败: {type(e).__name__}: {str(e)[:200]}")

# 测试5: 尝试访问MiMo API的主页（不用API调用，只测试域名）
print("\n测试5: 通过代理访问 MiMo 域名")
try:
    r = requests.get(
        "https://token-plan-cn.xiaomimomo.com", 
        proxies=proxies, 
        timeout=15,
        allow_redirects=False
    )
    print(f"✓ 状态码: {r.status_code}")
    print(f"   响应头: {dict(r.headers)}")
except Exception as e:
    print(f"✗ 失败: {type(e).__name__}: {str(e)[:300]}")

# 测试6: 使用socks代理（有些代理软件用socks5）
print("\n测试6: 使用 SOCKS5 代理")
try:
    socks_proxies = {
        'http': 'socks5://127.0.0.1:7890',
        'https': 'socks5://127.0.0.1:7890'
    }
    r = requests.get("https://www.google.com", proxies=socks_proxies, timeout=10)
    print(f"✓ 状态码: {r.status_code}")
except Exception as e:
    print(f"✗ 失败: {type(e).__name__}: {str(e)[:200]}")

print("\n" + "=" * 80)
