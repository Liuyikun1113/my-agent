"""
Milvus向量记忆存储适配器
实现MemoryStore接口，封装EmbeddingStore
"""
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from backend.src.memory.interfaces.memory_store import MemoryStore
from backend.src.memory.interfaces.memory_item import MemoryItem
from .embedding_store import embedding_store

logger = logging.getLogger(__name__)


class MilvusMemoryStore(MemoryStore):
    """
    Milvus向量记忆存储
    适配EmbeddingStore以符合MemoryStore接口
    """

    def __init__(self):
        self._store = embedding_store
        self._initialized = False

    async def initialize(self):
        if self._initialized:
            return
        try:
            await self._store.initialize()
            self._initialized = True
            logger.info("MilvusMemoryStore初始化完成")
        except Exception as e:
            logger.error(f"MilvusMemoryStore初始化失败: {e}", exc_info=True)
            raise

    async def save(self, item: MemoryItem):
        if not self._initialized:
            await self.initialize()
        try:
            await self._store.store_memory_item(item, generate_embedding=True)
        except Exception as e:
            logger.error(f"保存向量记忆失败: item_id={item.id}, error={e}", exc_info=True)
            raise

    async def get(self, item_id: str, user_id: Optional[str] = None) -> Optional[MemoryItem]:
        if not self._initialized:
            await self.initialize()
        try:
            return await self._store.get_memory_item(item_id, include_embedding=False)
        except Exception as e:
            logger.error(f"获取向量记忆失败: item_id={item_id}, error={e}")
            return None

    async def list(
        self,
        type: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20,
        order_by: Optional[str] = None,
    ) -> Tuple[List[MemoryItem], int]:
        # Milvus不适合分页列表查询，返回空列表
        logger.debug("Milvus不支持list操作，返回空列表")
        return [], 0

    async def delete(self, item_id: str):
        if not self._initialized:
            await self.initialize()
        try:
            await self._store.delete_memory_item(item_id)
        except Exception as e:
            logger.error(f"删除向量记忆失败: item_id={item_id}, error={e}", exc_info=True)
            raise

    async def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
    ) -> List[MemoryItem]:
        if not self._initialized:
            await self.initialize()
        try:
            filter_type = None
            user_id = None
            if filters:
                filter_type = filters.get("type")
                user_id = filters.get("user_id")

            # 构建 Milvus scalar filter 表达式
            filter_parts = []
            if filter_type:
                filter_parts.append(f'type == "{filter_type}"')
            if user_id:
                filter_parts.append(f'data["user_id"] == "{user_id}"')

            filter_expr = " && ".join(filter_parts) if filter_parts else None

            results = await self._store.search_similar(
                query=query,
                filter_type=filter_type,
                limit=limit,
            )

            # 如果有 user_id 过滤，在结果中再次过滤（Milvus JSON field 过滤可能因版本而异）
            items = []
            for r in results:
                item = r.get("item")
                if item and user_id:
                    item_uid = item.metadata.get("user_id") or ""
                    if item_uid != user_id:
                        continue
                if item:
                    items.append(item)
                if len(items) >= limit:
                    break
            return items
        except Exception as e:
            logger.error(f"向量搜索失败: query={query}, error={e}", exc_info=True)
            return []

    async def health_check(self) -> Dict[str, Any]:
        try:
            return await self._store.health_check()
        except Exception as e:
            return {"status": "unhealthy", "message": str(e)}

    async def close(self):
        try:
            await self._store.close()
            self._initialized = False
            logger.info("MilvusMemoryStore已关闭")
        except Exception as e:
            logger.error(f"关闭MilvusMemoryStore失败: {e}")
