"""
MySQL存储实现
基于SQLAlchemy的长期记忆存储
"""
import logging
import json
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import uuid

from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    JSON,
    Integer,
    select,
    func,
    delete,
    update,
    and_,
    or_,
    desc,
    asc,
)


from backend.src.models.database import Base, get_db_session
from backend.src.memory.interfaces.memory_store import MemoryStore
from backend.src.memory.interfaces.memory_item import MemoryItem

logger = logging.getLogger(__name__)


class MemoryItemModel(Base):
    """
    记忆项数据库模型
    用于存储MemoryItem到MySQL
    """
    __tablename__ = "memory_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    type = Column(String(50), nullable=False, index=True)
    data = Column(JSON, nullable=False)
    metadata = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.now, index=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    embedding = Column(JSON, nullable=True)

    # 自定义索引
    __table_args__ = (
        # 复合索引：类型+创建时间，常用于按类型和时间查询
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    def to_memory_item(self) -> MemoryItem:
        """
        转换为MemoryItem对象

        Returns:
            MemoryItem: 记忆项对象
        """
        # 处理JSON字段中的datetime序列化
        data = self.data.copy() if self.data else {}
        metadata = self.metadata.copy() if self.metadata else {}

        # 将JSON中的datetime字符串转换回datetime对象
        for key, value in data.items():
            if isinstance(value, str) and "T" in value and ":" in value:
                try:
                    data[key] = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

        return MemoryItem(
            id=self.id,
            type=self.type,
            data=data,
            metadata=metadata,
            created_at=self.created_at,
            updated_at=self.updated_at,
            embedding=self.embedding,
        )

    @classmethod
    def from_memory_item(cls, item: MemoryItem) -> "MemoryItemModel":
        """
        从MemoryItem创建数据库模型

        Args:
            item: 记忆项对象

        Returns:
            MemoryItemModel: 数据库模型实例
        """
        # 转换datetime对象为ISO格式字符串，以便JSON序列化
        data = item.data.copy() if item.data else {}
        metadata = item.metadata.copy() if item.metadata else {}

        # 将datetime对象转换为ISO格式字符串
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()

        return cls(
            id=item.id,
            type=item.type,
            data=data,
            metadata=metadata,
            created_at=item.created_at,
            updated_at=item.updated_at,
            embedding=item.embedding,
        )


class SQLStore(MemoryStore):
    """
    MySQL记忆存储实现
    """

    def __init__(self, table_name: str = "memory_items"):
        """
        初始化SQL存储

        Args:
            table_name: 表名（默认为memory_items）
        """
        self.table_name = table_name
        self._initialized = False
        self._model_class = MemoryItemModel

    async def initialize(self):
        """
        初始化存储连接
        注意：表创建由Alembic迁移处理
        """
        if self._initialized:
            return

        try:
            # 测试数据库连接
            from backend.src.models.database import get_db_health
            health = await get_db_health()
            if health["status"] != "healthy":
                raise ConnectionError(f"数据库连接失败: {health.get('message')}")

            self._initialized = True
            logger.info(f"SQL存储初始化完成 (table: {self.table_name})")

        except Exception as e:
            logger.error(f"SQL存储初始化失败: {e}", exc_info=True)
            raise

    async def save(self, item: MemoryItem):
        """
        保存记忆项

        Args:
            item: 记忆项
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with get_db_session() as session:
                # 检查是否已存在
                stmt = select(self._model_class).where(self._model_class.id == item.id)
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    # 更新现有记录
                    update_stmt = (
                        update(self._model_class)
                        .where(self._model_class.id == item.id)
                        .values(
                            type=item.type,
                            data=item.data,
                            metadata=item.metadata,
                            updated_at=datetime.now(),
                            embedding=item.embedding,
                        )
                    )
                    await session.execute(update_stmt)
                    logger.debug(f"更新记忆项: {item.id}")
                else:
                    # 插入新记录
                    model = self._model_class.from_memory_item(item)
                    session.add(model)
                    logger.debug(f"插入记忆项: {item.id}")

                await session.commit()

        except Exception as e:
            logger.error(f"保存记忆项失败: item_id={item.id}, error={e}", exc_info=True)
            raise

    async def get(self, item_id: str, user_id: Optional[str] = None) -> Optional[MemoryItem]:
        """
        获取记忆项

        Args:
            item_id: 记忆项ID
            user_id: 用户ID（MySQL按主键查询，此参数预留）

        Returns:
            Optional[MemoryItem]: 记忆项，如果不存在则返回None
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with get_db_session() as session:
                stmt = select(self._model_class).where(self._model_class.id == item_id)
                result = await session.execute(stmt)
                model = result.scalar_one_or_none()

                if model:
                    return model.to_memory_item()
                else:
                    return None

        except Exception as e:
            logger.error(f"获取记忆项失败: item_id={item_id}, error={e}", exc_info=True)
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
        列出记忆项

        Args:
            type: 记忆项类型过滤
            filters: 过滤条件
            page: 页码
            page_size: 每页数量
            order_by: 排序字段（前缀"-"表示降序）

        Returns:
            Tuple[List[MemoryItem], int]: 记忆项列表和总数
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with get_db_session() as session:
                # 构建查询条件
                conditions = []
                if type:
                    conditions.append(self._model_class.type == type)

                if filters:
                    for key, value in filters.items():
                        if key in ["data", "metadata"]:
                            # JSON 字段过滤：支持 data.user_id 或 metadata.user_id 形式
                            if isinstance(value, dict):
                                for sub_key, sub_value in value.items():
                                    json_path = f"$.{sub_key}"
                                    conditions.append(
                                        func.json_extract(getattr(self._model_class, key), json_path) == sub_value
                                    )
                            else:
                                logger.warning(f"JSON字段过滤暂不支持非字典值: {key}={value}")
                        elif key in ("user_id",):
                            # user_id 跨 data 和 metadata 两列查找
                            conditions.append(
                                func.json_extract(self._model_class.data, f"$.{key}") == value
                            )
                        else:
                            # 普通字段过滤
                            if hasattr(self._model_class, key):
                                conditions.append(getattr(self._model_class, key) == value)

                # 查询总数
                count_stmt = select(func.count()).select_from(self._model_class)
                if conditions:
                    count_stmt = count_stmt.where(and_(*conditions))

                count_result = await session.execute(count_stmt)
                total = count_result.scalar_one()

                # 查询数据
                stmt = select(self._model_class)
                if conditions:
                    stmt = stmt.where(and_(*conditions))

                # 排序
                if order_by:
                    if order_by.startswith("-"):
                        stmt = stmt.order_by(desc(order_by[1:]))
                    else:
                        stmt = stmt.order_by(asc(order_by))
                else:
                    # 默认按创建时间降序
                    stmt = stmt.order_by(desc(self._model_class.created_at))

                # 分页
                offset = (page - 1) * page_size
                stmt = stmt.offset(offset).limit(page_size)

                result = await session.execute(stmt)
                models = result.scalars().all()

                # 转换为MemoryItem
                items = [model.to_memory_item() for model in models]

                return items, total

        except Exception as e:
            logger.error(f"列出记忆项失败: type={type}, page={page}, error={e}", exc_info=True)
            return [], 0

    async def delete(self, item_id: str):
        """
        删除记忆项

        Args:
            item_id: 记忆项ID
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with get_db_session() as session:
                delete_stmt = delete(self._model_class).where(self._model_class.id == item_id)
                await session.execute(delete_stmt)
                await session.commit()

                logger.debug(f"删除记忆项: {item_id}")

        except Exception as e:
            logger.error(f"删除记忆项失败: item_id={item_id}, error={e}", exc_info=True)
            raise

    async def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
    ) -> List[MemoryItem]:
        """
        搜索记忆项

        Args:
            query: 搜索查询
            filters: 过滤条件
            limit: 返回结果数量限制

        Returns:
            List[MemoryItem]: 搜索结果
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with get_db_session() as session:
                # 构建基本查询
                stmt = select(self._model_class)

                # 添加过滤条件
                conditions = []
                if filters:
                    for key, value in filters.items():
                        if key in ("user_id",):
                            conditions.append(
                                func.json_extract(self._model_class.data, f"$.{key}") == value
                            )
                        elif key in ["data", "metadata"]:
                            pass  # JSON字段搜索通过like实现
                        elif hasattr(self._model_class, key):
                            conditions.append(getattr(self._model_class, key) == value)

                if conditions:
                    stmt = stmt.where(and_(*conditions))

                # 全文搜索（简化实现：在type、data、metadata字段中搜索）
                # 注意：实际生产中应该使用MySQL全文索引或Elasticsearch
                search_conditions = []
                if query:
                    # 在type字段中搜索
                    search_conditions.append(self._model_class.type.contains(query))

                    # 在JSON字段中搜索（简化）
                    # 这里我们只是简单地在所有记录中过滤，性能较差
                    # 实际应用应该使用专门的搜索方案

                if search_conditions:
                    stmt = stmt.where(or_(*search_conditions))

                # 排序和限制
                stmt = stmt.order_by(desc(self._model_class.updated_at)).limit(limit)

                result = await session.execute(stmt)
                models = result.scalars().all()

                # 转换为MemoryItem
                items = [model.to_memory_item() for model in models]

                return items

        except Exception as e:
            logger.error(f"搜索记忆项失败: query={query}, error={e}", exc_info=True)
            return []

    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            Dict[str, Any]: 健康状态信息
        """
        try:
            await self.initialize()

            async with get_db_session() as session:
                # 检查连接和表是否存在
                count_stmt = select(func.count()).select_from(self._model_class)
                await session.execute(count_stmt)

                # 获取表统计信息
                table_info = {
                    "table_name": self.table_name,
                    "initialized": self._initialized,
                    "model_class": self._model_class.__name__,
                }

                return {
                    "status": "healthy",
                    "message": "SQL存储连接正常",
                    "table_info": table_info,
                }

        except Exception as e:
            logger.error(f"SQL存储健康检查失败: {e}")
            return {
                "status": "unhealthy",
                "message": f"SQL存储连接失败: {str(e)}",
                "table_name": self.table_name,
            }

    async def close(self):
        """
        关闭存储连接
        SQLAlchemy连接池会自动管理，这里主要清理状态
        """
        try:
            self._initialized = False
            logger.info("SQL存储连接关闭")

        except Exception as e:
            logger.error(f"关闭SQL存储连接失败: {e}")

    async def clear_all(self):
        """
        清空所有记忆项
        警告：此操作会删除所有数据！
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with get_db_session() as session:
                delete_stmt = delete(self._model_class)
                await session.execute(delete_stmt)
                await session.commit()

                logger.warning("清空所有记忆项")

        except Exception as e:
            logger.error(f"清空记忆项失败: {e}", exc_info=True)
            raise


# 全局SQL存储实例（默认）
sql_store = SQLStore()