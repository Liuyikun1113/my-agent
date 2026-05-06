"""
消息存储库
提供消息数据的CRUD操作和查询功能
"""
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
import uuid

from sqlalchemy import select, func, desc, asc, and_, or_, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models.database import get_db_session
from backend.src.models.message import Message
from backend.src.models.session import Session as SessionModel

logger = logging.getLogger(__name__)


class MessageRepository:
    """
    消息存储库
    提供消息数据的CRUD操作
    """

    def __init__(self):
        self._initialized = False

    async def initialize(self):
        """
        初始化存储库
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
            logger.info("消息存储库初始化完成")

        except Exception as e:
            logger.error(f"消息存储库初始化失败: {e}", exc_info=True)
            raise

    async def create_message(
        self,
        session_id: str,
        role: str,
        content: Optional[str] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None,
        parent_message_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        intent: Optional[str] = None,
        intent_confidence: Optional[float] = None,
        processing_status: str = "pending",
    ) -> Message:
        """
        创建消息

        Args:
            session_id: 会话ID
            role: 消息角色 (user, assistant, system, tool)
            content: 消息内容
            tool_calls: 工具调用列表
            tool_results: 工具调用结果列表
            parent_message_id: 父消息ID
            metadata: 消息元数据
            intent: 意图分类
            intent_confidence: 意图置信度
            processing_status: 处理状态

        Returns:
            Message: 创建的消息对象
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with get_db_session() as session:
                # 检查会话是否存在
                session_stmt = select(SessionModel).where(SessionModel.id == session_id)
                session_result = await session.execute(session_stmt)
                if not session_result.scalar_one_or_none():
                    raise ValueError(f"会话不存在: {session_id}")

                # 如果指定了父消息，检查父消息是否存在
                if parent_message_id:
                    parent_stmt = select(Message).where(Message.id == parent_message_id)
                    parent_result = await session.execute(parent_stmt)
                    if not parent_result.scalar_one_or_none():
                        raise ValueError(f"父消息不存在: {parent_message_id}")

                # 创建消息对象
                message = Message(
                    session_id=session_id,
                    role=role,
                    content=content,
                    tool_calls=tool_calls,
                    tool_results=tool_results,
                    parent_message_id=parent_message_id,
                    metadata=metadata,
                    intent=intent,
                    intent_confidence=intent_confidence,
                    processing_status=processing_status,
                )

                session.add(message)
                await session.commit()
                await session.refresh(message)

                logger.debug(f"创建消息: message_id={message.id}, session={session_id}, role={role}")

                return message

        except Exception as e:
            logger.error(f"创建消息失败: session={session_id}, role={role}, error={e}", exc_info=True)
            raise

    async def get_message(self, message_id: str) -> Optional[Message]:
        """
        获取消息

        Args:
            message_id: 消息ID

        Returns:
            Optional[Message]: 消息对象，如果不存在则返回None
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with get_db_session() as session:
                stmt = select(Message).where(Message.id == message_id)
                result = await session.execute(stmt)
                message = result.scalar_one_or_none()

                return message

        except Exception as e:
            logger.error(f"获取消息失败: message_id={message_id}, error={e}", exc_info=True)
            return None

    async def update_message(
        self,
        message_id: str,
        **kwargs,
    ) -> Optional[Message]:
        """
        更新消息

        Args:
            message_id: 消息ID
            **kwargs: 要更新的字段

        Returns:
            Optional[Message]: 更新后的消息对象，如果不存在则返回None
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with get_db_session() as session:
                # 检查消息是否存在
                stmt = select(Message).where(Message.id == message_id)
                result = await session.execute(stmt)
                message = result.scalar_one_or_none()

                if not message:
                    logger.warning(f"消息不存在，无法更新: message_id={message_id}")
                    return None

                # 更新字段
                for key, value in kwargs.items():
                    if hasattr(message, key):
                        setattr(message, key, value)
                    else:
                        logger.warning(f"消息没有字段 {key}，跳过更新")

                await session.commit()
                await session.refresh(message)

                logger.debug(f"更新消息: message_id={message_id}, fields={list(kwargs.keys())}")

                return message

        except Exception as e:
            logger.error(f"更新消息失败: message_id={message_id}, error={e}", exc_info=True)
            return None

    async def delete_message(self, message_id: str) -> bool:
        """
        删除消息

        Args:
            message_id: 消息ID

        Returns:
            bool: 是否删除成功
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with get_db_session() as session:
                stmt = select(Message).where(Message.id == message_id)
                result = await session.execute(stmt)
                message = result.scalar_one_or_none()

                if not message:
                    logger.warning(f"消息不存在，无法删除: message_id={message_id}")
                    return False

                await session.delete(message)
                await session.commit()

                logger.debug(f"删除消息: message_id={message_id}")

                return True

        except Exception as e:
            logger.error(f"删除消息失败: message_id={message_id}, error={e}", exc_info=True)
            return False

    async def get_session_messages(
        self,
        session_id: str,
        page: int = 1,
        page_size: int = 50,
        role: Optional[str] = None,
        processing_status: Optional[str] = None,
        order_by: str = "created_at",
        order_desc: bool = True,
    ) -> Tuple[List[Message], int]:
        """
        获取会话消息列表

        Args:
            session_id: 会话ID
            page: 页码
            page_size: 每页数量
            role: 消息角色过滤
            processing_status: 处理状态过滤
            order_by: 排序字段
            order_desc: 是否降序

        Returns:
            Tuple[List[Message], int]: 消息列表和总数
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with get_db_session() as session:
                # 构建查询条件
                conditions = [Message.session_id == session_id]

                if role:
                    conditions.append(Message.role == role)

                if processing_status:
                    conditions.append(Message.processing_status == processing_status)

                # 查询总数
                count_stmt = select(func.count()).select_from(Message).where(and_(*conditions))
                count_result = await session.execute(count_stmt)
                total = count_result.scalar_one()

                # 查询数据
                stmt = select(Message).where(and_(*conditions))

                # 排序
                order_column = getattr(Message, order_by, Message.created_at)
                if order_desc:
                    stmt = stmt.order_by(desc(order_column))
                else:
                    stmt = stmt.order_by(asc(order_column))

                # 分页
                offset = (page - 1) * page_size
                stmt = stmt.offset(offset).limit(page_size)

                result = await session.execute(stmt)
                messages = result.scalars().all()

                return messages, total

        except Exception as e:
            logger.error(f"获取会话消息失败: session={session_id}, error={e}", exc_info=True)
            return [], 0

    async def get_recent_messages(
        self,
        session_id: str,
        limit: int = 10,
        include_system: bool = False,
    ) -> List[Message]:
        """
        获取最近的消息

        Args:
            session_id: 会话ID
            limit: 返回数量
            include_system: 是否包含系统消息

        Returns:
            List[Message]: 消息列表
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with get_db_session() as session:
                # 构建查询条件
                conditions = [Message.session_id == session_id]

                if not include_system:
                    conditions.append(Message.role != "system")

                stmt = (
                    select(Message)
                    .where(and_(*conditions))
                    .order_by(desc(Message.created_at))
                    .limit(limit)
                )

                result = await session.execute(stmt)
                messages = result.scalars().all()

                # 返回按时间升序排列
                return sorted(messages, key=lambda m: m.created_at)

        except Exception as e:
            logger.error(f"获取最近消息失败: session={session_id}, error={e}", exc_info=True)
            return []

    async def get_message_thread(
        self,
        message_id: str,
        include_parents: bool = True,
        include_children: bool = True,
        max_depth: int = 10,
    ) -> List[Message]:
        """
        获取消息线程（父子关系）

        Args:
            message_id: 消息ID
            include_parents: 是否包含父消息
            include_children: 是否包含子消息
            max_depth: 最大深度

        Returns:
            List[Message]: 消息线程列表
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with get_db_session() as session:
                messages = []
                visited = set()

                # 获取起始消息
                start_stmt = select(Message).where(Message.id == message_id)
                start_result = await session.execute(start_stmt)
                start_message = start_result.scalar_one_or_none()

                if not start_message:
                    return []

                messages.append(start_message)
                visited.add(start_message.id)

                # 递归获取父消息
                if include_parents:
                    await self._collect_parent_messages(
                        session, start_message, messages, visited, max_depth
                    )

                # 递归获取子消息
                if include_children:
                    await self._collect_child_messages(
                        session, start_message, messages, visited, max_depth
                    )

                # 按时间排序
                return sorted(messages, key=lambda m: m.created_at)

        except Exception as e:
            logger.error(f"获取消息线程失败: message_id={message_id}, error={e}", exc_info=True)
            return []

    async def _collect_parent_messages(
        self,
        session: AsyncSession,
        message: Message,
        messages: List[Message],
        visited: set,
        max_depth: int,
        current_depth: int = 0,
    ):
        """
        递归收集父消息
        """
        if current_depth >= max_depth or not message.parent_message_id:
            return

        parent_id = message.parent_message_id
        if parent_id in visited:
            return

        stmt = select(Message).where(Message.id == parent_id)
        result = await session.execute(stmt)
        parent = result.scalar_one_or_none()

        if parent:
            messages.append(parent)
            visited.add(parent_id)

            # 继续向上查找
            await self._collect_parent_messages(
                session, parent, messages, visited, max_depth, current_depth + 1
            )

    async def _collect_child_messages(
        self,
        session: AsyncSession,
        message: Message,
        messages: List[Message],
        visited: set,
        max_depth: int,
        current_depth: int = 0,
    ):
        """
        递归收集子消息
        """
        if current_depth >= max_depth:
            return

        # 查找所有子消息
        stmt = select(Message).where(Message.parent_message_id == message.id)
        result = await session.execute(stmt)
        children = result.scalars().all()

        for child in children:
            if child.id not in visited:
                messages.append(child)
                visited.add(child.id)

                # 继续向下查找
                await self._collect_child_messages(
                    session, child, messages, visited, max_depth, current_depth + 1
                )

    async def search_messages(
        self,
        session_id: Optional[str] = None,
        role: Optional[str] = None,
        intent: Optional[str] = None,
        content_query: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Message], int]:
        """
        搜索消息

        Args:
            session_id: 会话ID过滤
            role: 消息角色过滤
            intent: 意图过滤
            content_query: 内容查询（模糊匹配）
            start_date: 开始时间
            end_date: 结束时间
            page: 页码
            page_size: 每页数量

        Returns:
            Tuple[List[Message], int]: 消息列表和总数
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with get_db_session() as session:
                # 构建查询条件
                conditions = []

                if session_id:
                    conditions.append(Message.session_id == session_id)

                if role:
                    conditions.append(Message.role == role)

                if intent:
                    conditions.append(Message.intent == intent)

                if content_query:
                    conditions.append(Message.content.contains(content_query))

                if start_date:
                    conditions.append(Message.created_at >= start_date)

                if end_date:
                    conditions.append(Message.created_at <= end_date)

                # 查询总数
                count_stmt = select(func.count()).select_from(Message)
                if conditions:
                    count_stmt = count_stmt.where(and_(*conditions))

                count_result = await session.execute(count_stmt)
                total = count_result.scalar_one()

                # 查询数据
                stmt = select(Message)
                if conditions:
                    stmt = stmt.where(and_(*conditions))

                # 排序和分页
                stmt = stmt.order_by(desc(Message.created_at))
                offset = (page - 1) * page_size
                stmt = stmt.offset(offset).limit(page_size)

                result = await session.execute(stmt)
                messages = result.scalars().all()

                return messages, total

        except Exception as e:
            logger.error(f"搜索消息失败: error={e}", exc_info=True)
            return [], 0

    async def get_message_statistics(
        self,
        session_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        获取消息统计信息

        Args:
            session_id: 会话ID过滤
            start_date: 开始时间
            end_date: 结束时间

        Returns:
            Dict[str, Any]: 统计信息
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with get_db_session() as session:
                # 构建查询条件
                conditions = []

                if session_id:
                    conditions.append(Message.session_id == session_id)

                if start_date:
                    conditions.append(Message.created_at >= start_date)

                if end_date:
                    conditions.append(Message.created_at <= end_date)

                base_query = select(Message)
                if conditions:
                    base_query = base_query.where(and_(*conditions))

                # 统计各类消息数量
                role_stats_stmt = (
                    select(Message.role, func.count(Message.id))
                    .group_by(Message.role)
                )
                if conditions:
                    role_stats_stmt = role_stats_stmt.where(and_(*conditions))

                role_result = await session.execute(role_stats_stmt)
                role_stats = dict(role_result.all())

                # 统计意图分布
                intent_stats_stmt = (
                    select(Message.intent, func.count(Message.id))
                    .where(Message.intent.is_not(None))
                    .group_by(Message.intent)
                )
                if conditions:
                    intent_stats_stmt = intent_stats_stmt.where(and_(*conditions))

                intent_result = await session.execute(intent_stats_stmt)
                intent_stats = dict(intent_result.all())

                # 统计处理状态
                status_stats_stmt = (
                    select(Message.processing_status, func.count(Message.id))
                    .group_by(Message.processing_status)
                )
                if conditions:
                    status_stats_stmt = status_stats_stmt.where(and_(*conditions))

                status_result = await session.execute(status_stats_stmt)
                status_stats = dict(status_result.all())

                # 统计时间分布（按天）
                if start_date and end_date:
                    # 生成时间序列
                    pass

                return {
                    "role_stats": role_stats,
                    "intent_stats": intent_stats,
                    "status_stats": status_stats,
                    "total_messages": sum(role_stats.values()),
                    "date_range": {
                        "start": start_date.isoformat() if start_date else None,
                        "end": end_date.isoformat() if end_date else None,
                    },
                }

        except Exception as e:
            logger.error(f"获取消息统计失败: error={e}", exc_info=True)
            return {
                "role_stats": {},
                "intent_stats": {},
                "status_stats": {},
                "total_messages": 0,
                "date_range": {"start": None, "end": None},
            }

    async def cleanup_old_messages(
        self,
        days_to_keep: int = 30,
        batch_size: int = 1000,
    ) -> int:
        """
        清理旧消息

        Args:
            days_to_keep: 保留天数
            batch_size: 批量大小

        Returns:
            int: 删除的消息数量
        """
        if not self._initialized:
            await self.initialize()

        if days_to_keep <= 0:
            logger.warning(f"无效的保留天数: {days_to_keep}")
            return 0

        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            deleted_count = 0

            async with get_db_session() as session:
                # 分批删除
                while True:
                    # 查找要删除的消息ID
                    find_stmt = (
                        select(Message.id)
                        .where(Message.created_at < cutoff_date)
                        .limit(batch_size)
                    )

                    result = await session.execute(find_stmt)
                    message_ids = result.scalars().all()

                    if not message_ids:
                        break

                    # 删除消息
                    delete_stmt = delete(Message).where(Message.id.in_(message_ids))
                    await session.execute(delete_stmt)
                    await session.commit()

                    deleted_count += len(message_ids)
                    logger.info(f"删除 {len(message_ids)} 条旧消息，累计 {deleted_count} 条")

                return deleted_count

        except Exception as e:
            logger.error(f"清理旧消息失败: error={e}", exc_info=True)
            return 0

    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            Dict[str, Any]: 健康状态信息
        """
        try:
            await self.initialize()

            async with get_db_session() as session:
                # 检查表是否存在
                count_stmt = select(func.count()).select_from(Message)
                await session.execute(count_stmt)

                # 获取统计信息
                total_messages_stmt = select(func.count(Message.id))
                total_result = await session.execute(total_messages_stmt)
                total_messages = total_result.scalar_one()

                return {
                    "status": "healthy",
                    "message": "消息存储库连接正常",
                    "total_messages": total_messages,
                    "initialized": self._initialized,
                }

        except Exception as e:
            logger.error(f"消息存储库健康检查失败: {e}")
            return {
                "status": "unhealthy",
                "message": f"消息存储库连接失败: {str(e)}",
                "total_messages": 0,
                "initialized": self._initialized,
            }


# 全局消息存储库实例
message_repository = MessageRepository()