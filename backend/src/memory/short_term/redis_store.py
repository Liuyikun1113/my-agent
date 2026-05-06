"""
Redis记忆存储实现 - 短期记忆
"""
import logging
import json
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from backend.src.memory.interfaces.memory_store import MemoryStore
from backend.src.memory.interfaces.memory_item import MemoryItem
from .redis_client import redis_client
from backend.src.config.settings import settings

logger = logging.getLogger(__name__)


class RedisMemoryStore(MemoryStore):
    """
    Redis记忆存储实现
    用于短期记忆存储，支持TTL
    """

    def __init__(self):
        self._initialized = False
        self.default_ttl = settings.SHORT_TERM_MEMORY_TTL

    async def initialize(self):
        """
        初始化Redis连接
        """
        if self._initialized:
            return

        try:
            await redis_client.initialize()
            self._initialized = True
            logger.info("RedisMemoryStore初始化完成")

        except Exception as e:
            logger.error(f"RedisMemoryStore初始化失败: {e}", exc_info=True)
            raise

    async def save(self, item: MemoryItem):
        """
        保存记忆项到Redis

        Args:
            item: 记忆项
        """
        try:
            if not self._initialized:
                await self.initialize()

            # 转换为字典
            item_dict = item.to_dict()
            user_id = self._get_user_id(item)

            # 构建键名
            key = self._build_key(item.id, item.type, user_id)

            # 保存到Redis，设置TTL
            await redis_client.set(key, item_dict, ttl=self.default_ttl)

            # 同时添加到类型索引
            await self._add_to_index(item, user_id)

            logger.debug(f"记忆项保存到Redis: {key}")

        except Exception as e:
            logger.error(f"保存记忆项到Redis失败: item_id={item.id}, error={e}", exc_info=True)
            raise

    async def get(self, item_id: str, user_id: Optional[str] = None) -> Optional[MemoryItem]:
        """
        从Redis获取记忆项

        Args:
            item_id: 记忆项ID
            user_id: 用户ID（可选，用于精确匹配key）

        Returns:
            Optional[MemoryItem]: 记忆项，如果不存在则返回None
        """
        try:
            if not self._initialized:
                await self.initialize()

            item_types = ["session", "message", "intent", "todo"]

            if user_id:
                # 有 user_id，精确查找
                for item_type in item_types:
                    key = self._build_key(item_id, item_type, user_id)
                    item_dict = await redis_client.get(key)
                    if item_dict:
                        try:
                            return MemoryItem.from_dict(item_dict)
                        except Exception as e:
                            logger.error(f"解析Redis记忆项失败: key={key}, error={e}")
                            continue
            else:
                # 无 user_id，扫描所有用户前缀
                for item_type in item_types:
                    pattern = f"memory:user:*:{item_type}:{item_id}"
                    keys = await redis_client.keys(pattern)
                    for key in keys:
                        item_dict = await redis_client.get(key)
                        if item_dict:
                            try:
                                return MemoryItem.from_dict(item_dict)
                            except Exception as e:
                                logger.error(f"解析Redis记忆项失败: key={key}, error={e}")
                                continue

            logger.debug(f"记忆项在Redis中不存在: {item_id}")
            return None

        except Exception as e:
            logger.error(f"从Redis获取记忆项失败: item_id={item_id}, error={e}")
            return None

    async def list(
        self,
        type: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20,
        order_by: Optional[str] = None,
    ) -> Tuple[List[MemoryItem], int]:
        """
        从Redis列出记忆项（支持有限过滤）

        Args:
            type: 记忆项类型过滤
            filters: 过滤条件（Redis实现有限支持）
            page: 页码
            page_size: 每页数量
            order_by: 排序字段（Redis实现有限支持）

        Returns:
            Tuple[List[MemoryItem], int]: 记忆项列表和总数
        """
        try:
            if not self._initialized:
                await self.initialize()

            # 获取类型的所有键（按用户前缀）
            if type:
                pattern = f"memory:user:*:{type}:*"
            else:
                pattern = "memory:user:*:*:*"

            # 获取匹配的键
            keys = await redis_client.keys(pattern)

            # 获取所有记忆项
            items = []
            for key in keys:
                item_dict = await redis_client.get(key)
                if item_dict:
                    try:
                        memory_item = MemoryItem.from_dict(item_dict)
                        items.append(memory_item)
                    except Exception as e:
                        logger.error(f"解析Redis记忆项失败: key={key}, error={e}")
                        continue

            # 应用过滤（内存中过滤）
            if filters:
                filtered_items = []
                for item in items:
                    if self._matches_filters(item, filters):
                        filtered_items.append(item)
                items = filtered_items

            # 应用排序（内存中排序）
            if order_by:
                reverse = order_by.startswith("-")
                sort_field = order_by[1:] if reverse else order_by
                items.sort(key=lambda x: x.get_data_field(sort_field, ""), reverse=reverse)

            # 分页
            total = len(items)
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_items = items[start_idx:end_idx]

            logger.debug(f"从Redis列出记忆项: type={type}, count={len(paginated_items)}/{total}")

            return paginated_items, total

        except Exception as e:
            logger.error(f"从Redis列出记忆项失败: error={e}", exc_info=True)
            return [], 0

    async def delete(self, item_id: str):
        """
        从Redis删除记忆项

        Args:
            item_id: 记忆项ID
        """
        try:
            if not self._initialized:
                await self.initialize()

            # 扫描所有用户前缀，找到并删除
            deleted = False
            for item_type in ["session", "message", "intent", "todo"]:
                pattern = f"memory:user:*:{item_type}:{item_id}"
                keys = await redis_client.keys(pattern)
                for key in keys:
                    await redis_client.delete(key)
                    # 从key中提取user_id: memory:user:{user_id}:{type}:{id}
                    parts = key.split(":")
                    if len(parts) >= 5:
                        await self._remove_from_index(item_id, item_type, parts[2])
                    deleted = True
                    logger.debug(f"从Redis删除记忆项: {key}")

            if not deleted:
                logger.warning(f"要删除的记忆项不存在: {item_id}")

        except Exception as e:
            logger.error(f"从Redis删除记忆项失败: item_id={item_id}, error={e}", exc_info=True)
            raise

    async def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
    ) -> List[MemoryItem]:
        """
        从Redis搜索记忆项（支持简单文本搜索）

        Args:
            query: 搜索查询
            filters: 过滤条件
            limit: 返回结果数量限制

        Returns:
            List[MemoryItem]: 搜索结果
        """
        try:
            if not self._initialized:
                await self.initialize()

            # Redis不支持复杂的文本搜索，这里实现简单的关键字搜索
            pattern = "memory:user:*:*:*"
            keys = await redis_client.keys(pattern)

            results = []
            for key in keys:
                item_dict = await redis_client.get(key)
                if item_dict:
                    try:
                        memory_item = MemoryItem.from_dict(item_dict)

                        # 检查是否匹配查询
                        if self._matches_search(memory_item, query):
                            # 检查是否匹配过滤条件
                            if not filters or self._matches_filters(memory_item, filters):
                                results.append(memory_item)

                                if len(results) >= limit:
                                    break

                    except Exception as e:
                        logger.error(f"解析Redis记忆项失败: key={key}, error={e}")
                        continue

            logger.debug(f"从Redis搜索记忆项: query={query}, results={len(results)}")

            return results

        except Exception as e:
            logger.error(f"从Redis搜索记忆项失败: query={query}, error={e}", exc_info=True)
            return []

    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            Dict[str, Any]: 健康状态信息
        """
        try:
            if not self._initialized:
                return {"status": "unhealthy", "error": "未初始化"}

            # 使用Redis客户端的健康检查
            redis_health = await redis_client.health_check()

            # 获取统计信息
            pattern = "memory:user:*:*:*"
            keys = await redis_client.keys(pattern)
            item_count = len(keys)

            return {
                "status": redis_health.get("status", "unknown"),
                "redis_info": redis_health,
                "item_count": item_count,
                "default_ttl": self.default_ttl,
            }

        except Exception as e:
            logger.error(f"RedisMemoryStore健康检查失败: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    async def close(self):
        """
        关闭存储连接
        """
        try:
            await redis_client.close()
            self._initialized = False
            logger.info("RedisMemoryStore已关闭")

        except Exception as e:
            logger.error(f"关闭RedisMemoryStore失败: {e}")
            raise

    # ===== 会话消息列表（短期记忆） =====

    async def push_to_session_list(
        self,
        session_id: str,
        message_data: Dict[str, Any],
        max_len: int = 10,
    ):
        """
        将消息推入会话的最近消息列表（LTRIM 保留最近 max_len 条）

        Args:
            session_id: 会话ID
            message_data: 消息数据字典
            max_len: 最大保留数量
        """
        try:
            key = f"session:{session_id}:recent"
            payload = json.dumps(message_data, ensure_ascii=False)
            await redis_client.lpush(key, payload)
            await redis_client.ltrim(key, 0, max_len - 1)
            await redis_client.expire(key, self.default_ttl)
        except Exception as e:
            logger.warning(f"写入会话消息列表失败: session={session_id}, error={e}")

    async def get_session_messages(
        self,
        session_id: str,
        count: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        获取会话最近的消息列表

        Args:
            session_id: 会话ID
            count: 获取数量

        Returns:
            List[Dict]: 消息数据列表（按时间正序）
        """
        try:
            key = f"session:{session_id}:recent"
            items = await redis_client.lrange(key, 0, count - 1)
            messages = [json.loads(item) for item in items]
            messages.reverse()  # LPUSH 是倒序的，翻转为时间正序
            return messages
        except Exception as e:
            logger.warning(f"读取会话消息列表失败: session={session_id}, error={e}")
            return []

    # ===== 私有方法 =====

    @staticmethod
    def _get_user_id(item: MemoryItem) -> str:
        """从MemoryItem的metadata中提取user_id，无则返回'anon'"""
        uid = item.metadata.get("user_id") if item.metadata else None
        return uid if uid else "anon"

    def _build_key(self, item_id: str, item_type: str, user_id: Optional[str] = None) -> str:
        """
        构建Redis键名

        Args:
            item_id: 记忆项ID
            item_type: 记忆项类型
            user_id: 用户ID

        Returns:
            str: Redis键名
        """
        uid = user_id or "anon"
        return f"memory:user:{uid}:{item_type}:{item_id}"

    async def _add_to_index(self, item: MemoryItem, user_id: Optional[str] = None):
        """
        添加记忆项到用户维度的索引

        Args:
            item: 记忆项
            user_id: 用户ID
        """
        try:
            uid = user_id or self._get_user_id(item)

            # 用户维度：类型集合
            type_key = f"memory:user:{uid}:index:type:{item.type}"
            await redis_client.sadd(type_key, item.id)
            await redis_client.expire(type_key, self.default_ttl)

            # 用户的会话列表索引（仅session类型）
            if item.type == "session":
                sessions_key = f"memory:user:{uid}:index:sessions"
                await redis_client.sadd(sessions_key, item.id)
                await redis_client.expire(sessions_key, self.default_ttl)

            # 按小时的时间索引
            hour_key = f"memory:user:{uid}:index:created:{datetime.now().strftime('%Y%m%d%H')}"
            await redis_client.sadd(hour_key, f"{item.type}:{item.id}")
            await redis_client.expire(hour_key, self.default_ttl)

        except Exception as e:
            logger.error(f"添加到索引失败: item_id={item.id}, error={e}")

    async def _remove_from_index(self, item_id: str, item_type: str, user_id: Optional[str] = None):
        """
        从用户维度的索引中移除记忆项

        Args:
            item_id: 记忆项ID
            item_type: 记忆项类型
            user_id: 用户ID
        """
        try:
            uid = user_id or "anon"
            type_key = f"memory:user:{uid}:index:type:{item_type}"
            await redis_client.srem(type_key, item_id)

            if item_type == "session":
                sessions_key = f"memory:user:{uid}:index:sessions"
                await redis_client.srem(sessions_key, item_id)

        except Exception as e:
            logger.error(f"从索引移除失败: item_id={item_id}, error={e}")

    def _matches_filters(self, item: MemoryItem, filters: Dict[str, Any]) -> bool:
        """
        检查记忆项是否匹配过滤条件

        Args:
            item: 记忆项
            filters: 过滤条件

        Returns:
            bool: 是否匹配
        """
        for field, expected_value in filters.items():
            # 从data或metadata中获取值
            actual_value = item.get_data_field(field)
            if actual_value is None:
                actual_value = item.get_metadata_field(field)

            if actual_value != expected_value:
                return False

        return True

    def _matches_search(self, item: MemoryItem, query: str) -> bool:
        """
        检查记忆项是否匹配搜索查询

        Args:
            item: 记忆项
            query: 搜索查询

        Returns:
            bool: 是否匹配
        """
        if not query:
            return True

        query_lower = query.lower()

        # 检查内容字段
        content = item.get_data_field("content")
        if content and query_lower in content.lower():
            return True

        # 检查标题字段
        title = item.get_data_field("title")
        if title and query_lower in title.lower():
            return True

        # 检查描述字段
        description = item.get_data_field("description")
        if description and query_lower in description.lower():
            return True

        # 检查元数据
        for value in item.metadata.values():
            if isinstance(value, str) and query_lower in value.lower():
                return True

        return False