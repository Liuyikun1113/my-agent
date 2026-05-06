"""
Redis 连接诊断工具
运行: python diagnose_redis.py
"""
import socket
import sys
import os

# ========== 1. 检查你的配置 ==========
print("=" * 50)
print("🔍 第一步：检查配置")
print("=" * 50)

# 先加载你的项目配置
sys.path.insert(0, r"D:\project\my-agent")  # 你的项目路径
from backend.src.config.settings import settings

print(f"REDIS_HOST: {settings.REDIS_HOST!r}")
print(f"REDIS_PORT: {settings.REDIS_PORT!r}")
print(f"REDIS_DB: {settings.REDIS_DB!r}")
print(f"REDIS_PASSWORD: {'已设置' if settings.REDIS_PASSWORD else '未设置'}")

# ========== 2. 网络连通性测试 ==========
print("\n" + "=" * 50)
print("🔍 第二步：网络连通性测试")
print("=" * 50)

host = settings.REDIS_HOST
port = settings.REDIS_PORT

try:
    sock = socket.create_connection((host, port), timeout=5)
    print(f"✅ TCP 连接成功: {host}:{port}")
    sock.close()
except socket.timeout:
    print(f"❌ TCP 连接超时: {host}:{port}")
    print("   可能原因：")
    print("   - 服务器未开机")
    print("   - 防火墙阻挡")
    print("   - 安全组未开放端口")
    print("   - 网络不通（VPN？内网？）")
except ConnectionRefusedError:
    print(f"❌ 连接被拒绝: {host}:{port}")
    print("   可能原因：")
    print("   - Redis 服务未启动")
    print("   - 端口错误")
except Exception as e:
    print(f"❌ 网络错误: {e}")

# ========== 3. 用 redis-cli 测试 ==========
print("\n" + "=" * 50)
print("🔍 第三步：redis-cli 测试（如果本地有）")
print("=" * 50)

import subprocess
try:
    result = subprocess.run(
        ["redis-cli", "-h", host, "-p", str(port), "ping"],
        capture_output=True, text=True, timeout=5
    )
    if "PONG" in result.stdout:
        print(f"✅ redis-cli 连接成功")
    else:
        print(f"⚠️  redis-cli 返回: {result.stdout.strip() or result.stderr.strip()}")
except FileNotFoundError:
    print("⚠️  未找到 redis-cli，跳过")
except Exception as e:
    print(f"❌ redis-cli 错误: {e}")

# ========== 4. Python redis 同步客户端测试 ==========
print("\n" + "=" * 50)
print("🔍 第四步：Python 同步客户端测试")
print("=" * 50)

try:
    import redis
    r = redis.Redis(
        host=host,
        port=port,
        db=settings.REDIS_DB,
        password=settings.REDIS_PASSWORD,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    result = r.ping()
    print(f"✅ 同步客户端连接成功: ping={result}")
except ImportError:
    print("⚠️  未安装 redis 包，跳过")
except Exception as e:
    print(f"❌ 同步客户端失败: {e}")

# ========== 5. Python redis 异步客户端测试 ==========
print("\n" + "=" * 50)
print("🔍 第五步：Python 异步客户端测试")
print("=" * 50)

import asyncio

async def test_async():
    try:
        import redis.asyncio as aioredis
        r = aioredis.Redis(
            host=host,
            port=port,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            socket_connect_timeout=5,
        )
        result = await r.ping()
        print(f"✅ 异步客户端连接成功: ping={result}")
        await r.close()
    except Exception as e:
        print(f"❌ 异步客户端失败: {e}")

asyncio.run(test_async())

# ========== 6. 总结 ==========
print("\n" + "=" * 50)
print("📋 诊断总结")
print("=" * 50)
print("""
如果上面所有测试都失败：
  1. 检查服务器 IP 和端口是否正确
  2. 检查防火墙/安全组是否放行 Redis 端口
  3. 检查 Redis 是否允许远程连接（bind 0.0.0.0）
  4. 检查是否需要 VPN/内网穿透

如果只有异步客户端失败：
  - 可能是 asyncio 兼容性问题，用同步客户端替代测试
""")