"""
Redis客户端封装 - 短期记忆存储
"""
import logging
import json
from typing import Optional, Dict, Any
import redis.asyncio as redis
from redis.asyncio import Redis

from backend.src.config.settings import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Redis客户端封装
    提供异步Redis操作接口
    """

    def __init__(self):
        self.client: Optional[Redis] = None
        self._initialized = False

    async def initialize(self):
        """
        初始化Redis连接
        """
        if self._initialized:
            return

        try:
            # 构建连接参数
            connection_kwargs = {
                "host": settings.REDIS_HOST,
                "port": settings.REDIS_PORT,
                "db": settings.REDIS_DB,
                "decode_responses": True,  # 自动解码字符串
                "socket_connect_timeout": 5,
                "socket_keepalive": True,
            }

            # 如果有密码，添加密码参数
            if settings.REDIS_PASSWORD:
                connection_kwargs["password"] = settings.REDIS_PASSWORD

            # 创建Redis客户端
            self.client = redis.Redis(**connection_kwargs)

            # 测试连接
            await self.client.ping()
            logger.info(f"Redis连接成功: {settings.REDIS_HOST}:{settings.REDIS_PORT}")

            self._initialized = True

        except Exception as e:
            logger.error(f"Redis连接失败: {e}", exc_info=True)
            raise

    async def close(self):
        """
        关闭Redis连接
        """
        if self.client:
            await self.client.close()
            self.client = None
            self._initialized = False
            logger.info("Redis连接已关闭")

    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            Dict[str, Any]: 健康状态信息
        """
        try:
            if not self._initialized:
                return {"status": "unhealthy", "error": "未初始化"}

            # 测试连接
            await self.client.ping()

            # 获取Redis信息
            info = await self.client.info()
            memory_info = info.get("memory", {})
            stats_info = info.get("stats", {})

            return {
                "status": "healthy",
                "version": info.get("redis_version"),
                "mode": info.get("redis_mode"),
                "uptime": info.get("uptime_in_seconds"),
                "memory_used": memory_info.get("used_memory_human"),
                "memory_max": memory_info.get("maxmemory_human"),
                "connected_clients": info.get("connected_clients"),
                "total_commands_processed": stats_info.get("total_commands_processed"),
                "instantaneous_ops_per_sec": stats_info.get("instantaneous_ops_per_sec"),
            }

        except Exception as e:
            logger.error(f"Redis健康检查失败: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    # ===== 基础键值操作 =====

    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        设置键值

        Args:
            key: 键名
            value: 值（会自动序列化为JSON）
            ttl: 过期时间（秒）
        """
        try:
            if not self._initialized:
                await self.initialize()

            # 序列化值为JSON字符串
            json_value = json.dumps(value, ensure_ascii=False)

            if ttl:
                await self.client.setex(key, ttl, json_value)
            else:
                await self.client.set(key, json_value)

        except Exception as e:
            logger.error(f"设置Redis键值失败: key={key}, error={e}")
            raise

    async def get(self, key: str) -> Optional[Any]:
        """
        获取键值

        Args:
            key: 键名

        Returns:
            Optional[Any]: 值（会自动反序列化），如果键不存在则返回None
        """
        try:
            if not self._initialized:
                await self.initialize()

            json_value = await self.client.get(key)
            if json_value is None:
                return None

            return json.loads(json_value)

        except json.JSONDecodeError as e:
            logger.error(f"解析Redis值JSON失败: key={key}, value={json_value}, error={e}")
            return None
        except Exception as e:
            logger.error(f"获取Redis键值失败: key={key}, error={e}")
            return None

    async def delete(self, key: str) -> bool:
        """
        删除键

        Args:
            key: 键名

        Returns:
            bool: 是否删除成功
        """
        try:
            if not self._initialized:
                await self.initialize()

            result = await self.client.delete(key)
            return result > 0

        except Exception as e:
            logger.error(f"删除Redis键失败: key={key}, error={e}")
            return False

    async def exists(self, key: str) -> bool:
        """
        检查键是否存在

        Args:
            key: 键名

        Returns:
            bool: 是否存在
        """
        try:
            if not self._initialized:
                await self.initialize()

            result = await self.client.exists(key)
            return result > 0

        except Exception as e:
            logger.error(f"检查Redis键存在失败: key={key}, error={e}")
            return False

    async def expire(self, key: str, ttl: int):
        """
        设置键过期时间

        Args:
            key: 键名
            ttl: 过期时间（秒）
        """
        try:
            if not self._initialized:
                await self.initialize()

            await self.client.expire(key, ttl)

        except Exception as e:
            logger.error(f"设置Redis键过期时间失败: key={key}, ttl={ttl}, error={e}")
            raise

    # ===== 哈希操作 =====

    async def hset(self, hash_key: str, field: str, value: Any):
        """
        设置哈希字段

        Args:
            hash_key: 哈希键名
            field: 字段名
            value: 字段值（会自动序列化为JSON）
        """
        try:
            if not self._initialized:
                await self.initialize()

            json_value = json.dumps(value, ensure_ascii=False)
            await self.client.hset(hash_key, field, json_value)

        except Exception as e:
            logger.error(f"设置Redis哈希字段失败: hash={hash_key}, field={field}, error={e}")
            raise

    async def hget(self, hash_key: str, field: str) -> Optional[Any]:
        """
        获取哈希字段值

        Args:
            hash_key: 哈希键名
            field: 字段名

        Returns:
            Optional[Any]: 字段值（会自动反序列化），如果字段不存在则返回None
        """
        try:
            if not self._initialized:
                await self.initialize()

            json_value = await self.client.hget(hash_key, field)
            if json_value is None:
                return None

            return json.loads(json_value)

        except json.JSONDecodeError as e:
            logger.error(f"解析Redis哈希值JSON失败: hash={hash_key}, field={field}, error={e}")
            return None
        except Exception as e:
            logger.error(f"获取Redis哈希字段失败: hash={hash_key}, field={field}, error={e}")
            return None

    async def hgetall(self, hash_key: str) -> Dict[str, Any]:
        """
        获取哈希所有字段

        Args:
            hash_key: 哈希键名

        Returns:
            Dict[str, Any]: 所有字段和值
        """
        try:
            if not self._initialized:
                await self.initialize()

            result = await self.client.hgetall(hash_key)
            decoded = {}
            for field, json_value in result.items():
                try:
                    decoded[field] = json.loads(json_value)
                except json.JSONDecodeError:
                    decoded[field] = json_value

            return decoded

        except Exception as e:
            logger.error(f"获取Redis哈希所有字段失败: hash={hash_key}, error={e}")
            return {}

    async def hdel(self, hash_key: str, field: str) -> bool:
        """
        删除哈希字段

        Args:
            hash_key: 哈希键名
            field: 字段名

        Returns:
            bool: 是否删除成功
        """
        try:
            if not self._initialized:
                await self.initialize()

            result = await self.client.hdel(hash_key, field)
            return result > 0

        except Exception as e:
            logger.error(f"删除Redis哈希字段失败: hash={hash_key}, field={field}, error={e}")
            return False

    # ===== 列表操作 =====

    async def lpush(self, list_key: str, *values: Any):
        """
        从列表左侧插入元素

        Args:
            list_key: 列表键名
            *values: 要插入的值（会自动序列化为JSON）
        """
        try:
            if not self._initialized:
                await self.initialize()

            json_values = [json.dumps(v, ensure_ascii=False) for v in values]
            await self.client.lpush(list_key, *json_values)

        except Exception as e:
            logger.error(f"Redis列表左侧插入失败: key={list_key}, error={e}")
            raise

    async def rpush(self, list_key: str, *values: Any):
        """
        从列表右侧插入元素

        Args:
            list_key: 列表键名
            *values: 要插入的值（会自动序列化为JSON）
        """
        try:
            if not self._initialized:
                await self.initialize()

            json_values = [json.dumps(v, ensure_ascii=False) for v in values]
            await self.client.rpush(list_key, *json_values)

        except Exception as e:
            logger.error(f"Redis列表右侧插入失败: key={list_key}, error={e}")
            raise

    async def lrange(self, list_key: str, start: int = 0, end: int = -1) -> list:
        """
        获取列表范围元素

        Args:
            list_key: 列表键名
            start: 起始索引
            end: 结束索引

        Returns:
            list: 元素列表（会自动反序列化）
        """
        try:
            if not self._initialized:
                await self.initialize()

            json_values = await self.client.lrange(list_key, start, end)
            result = []
            for json_value in json_values:
                try:
                    result.append(json.loads(json_value))
                except json.JSONDecodeError:
                    result.append(json_value)

            return result

        except Exception as e:
            logger.error(f"获取Redis列表范围失败: key={list_key}, start={start}, end={end}, error={e}")
            return []

    async def llen(self, list_key: str) -> int:
        """
        获取列表长度

        Args:
            list_key: 列表键名

        Returns:
            int: 列表长度
        """
        try:
            if not self._initialized:
                await self.initialize()

            return await self.client.llen(list_key)

        except Exception as e:
            logger.error(f"获取Redis列表长度失败: key={list_key}, error={e}")
            return 0

    # ===== 集合操作 =====

    async def sadd(self, set_key: str, *members: Any):
        """
        向集合添加成员

        Args:
            set_key: 集合键名
            *members: 成员（字符串或可序列化为字符串的值）
        """
        try:
            if not self._initialized:
                await self.initialize()

            str_members = [str(m) for m in members]
            await self.client.sadd(set_key, *str_members)

        except Exception as e:
            logger.error(f"Redis集合添加成员失败: key={set_key}, error={e}")
            raise

    async def smembers(self, set_key: str) -> set:
        """
        获取集合所有成员

        Args:
            set_key: 集合键名

        Returns:
            set: 成员集合
        """
        try:
            if not self._initialized:
                await self.initialize()

            return await self.client.smembers(set_key)

        except Exception as e:
            logger.error(f"获取Redis集合成员失败: key={set_key}, error={e}")
            return set()

    async def sismember(self, set_key: str, member: Any) -> bool:
        """
        检查成员是否在集合中

        Args:
            set_key: 集合键名
            member: 成员

        Returns:
            bool: 是否在集合中
        """
        try:
            if not self._initialized:
                await self.initialize()

            return await self.client.sismember(set_key, str(member))

        except Exception as e:
            logger.error(f"检查Redis集合成员失败: key={set_key}, member={member}, error={e}")
            return False

    # ===== 统计和工具方法 =====

    async def keys(self, pattern: str = "*") -> list:
        """
        获取匹配模式的键

        Args:
            pattern: 键模式

        Returns:
            list: 键列表
        """
        try:
            if not self._initialized:
                await self.initialize()

            return await self.client.keys(pattern)

        except Exception as e:
            logger.error(f"获取Redis键失败: pattern={pattern}, error={e}")
            return []

    async def flushdb(self):
        """
        清空当前数据库
        """
        try:
            if not self._initialized:
                await self.initialize()

            await self.client.flushdb()
            logger.warning("Redis数据库已清空")

        except Exception as e:
            logger.error(f"清空Redis数据库失败: {e}")
            raise

    async def get_info(self) -> Dict[str, Any]:
        """
        获取Redis服务器信息

        Returns:
            Dict[str, Any]: Redis信息
        """
        try:
            if not self._initialized:
                await self.initialize()

            info = await self.client.info()
            return info

        except Exception as e:
            logger.error(f"获取Redis信息失败: {e}")
            return {}


# 全局Redis客户端实例
redis_client = RedisClient()