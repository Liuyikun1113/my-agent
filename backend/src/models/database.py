"""
数据库配置和模型基类
"""
import asyncio
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
import logging

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base, DeclarativeBase

from backend.src.config.settings import settings

logger = logging.getLogger(__name__)

# 数据库元数据
metadata = MetaData()

# 声明性基类
class Base(DeclarativeBase):
    """
    SQLAlchemy声明性基类
    """
    metadata = metadata

# 异步引擎
_engine: Optional[AsyncEngine] = None
_async_session_maker: Optional[async_sessionmaker[AsyncSession]] = None


def get_engine() -> AsyncEngine:
    """
    获取数据库引擎（单例）
    """
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
            connect_args={
                "charset": "utf8mb4",
            },
        )
        logger.info("数据库引擎创建完成")
    return _engine


def get_async_session_maker() -> async_sessionmaker[AsyncSession]:
    """
    获取异步会话工厂（单例）
    """
    global _async_session_maker
    if _async_session_maker is None:
        engine = get_engine()
        _async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        logger.info("异步会话工厂创建完成")
    return _async_session_maker


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话的上下文管理器
    """
    session_maker = get_async_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"数据库会话异常: {e}", exc_info=True)
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    初始化数据库连接
    """
    try:
        # 测试连接
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

        logger.info("数据库连接测试成功")

        # 创建表（开发环境）
        if settings.is_development:
            from backend.src.models import session, message, intent_category, todo_list, todo_item
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("数据库表创建完成（开发环境）")

    except Exception as e:
        logger.error(f"数据库初始化失败: {e}", exc_info=True)
        raise


async def close_db() -> None:
    """
    关闭数据库连接
    """
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None
        logger.info("数据库连接已关闭")


async def get_db_health() -> dict:
    """
    获取数据库健康状态
    """
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

        return {
            "status": "healthy",
            "message": "数据库连接正常",
            "database": settings.MYSQL_DATABASE,
            "host": settings.MYSQL_HOST,
            "port": settings.MYSQL_PORT,
        }
    except Exception as e:
        logger.error(f"数据库健康检查失败: {e}")
        return {
            "status": "unhealthy",
            "message": f"数据库连接失败: {str(e)}",
            "database": settings.MYSQL_DATABASE,
            "host": settings.MYSQL_HOST,
            "port": settings.MYSQL_PORT,
        }


# 导入所有模型以确保它们被注册
# 这必须在Base之后导入
__all__ = [
    "Base",
    "get_engine",
    "get_async_session_maker",
    "get_db_session",
    "init_db",
    "close_db",
    "get_db_health",
]