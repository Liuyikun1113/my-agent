import asyncio
from backend.src.memory.vector.milvus_client import MilvusClient

async def test():
    client = MilvusClient()
    await client.health_check()

if __name__ == '__main__':
    asyncio.run(test())