from backend.src.memory.short_term.redis_client import RedisClient
import asyncio


async def main():
    """异步主函数"""
    client = RedisClient()

    # 初始化连接
    await client.initialize()

    # 设置键值
    await client.set("x", "1")

    # 读取并打印
    result = await client.get("x")
    print(f"读取结果: {result}")

    # 关闭连接（好习惯）
    await client.close()


if __name__ == '__main__':
    # 用 asyncio.run() 启动异步主函数
    asyncio.run(main())