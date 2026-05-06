import asyncio
import sys
sys.path.insert(0, 'src')
from backend.src.config.settings import settings
print(f'目标: {settings.MYSQL_HOST}:{settings.MYSQL_PORT}')

async def check():
    from backend.src.models.database import get_db_health
    r = await get_db_health()
    print(r)
asyncio.run(check())