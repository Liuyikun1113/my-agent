"""
会话存储库
提供会话数据的CRUD操作和查询功能
"""
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
import uuid

from sqlalchemy import select, func, desc, asc, and_, or_, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models.database import get_db_session
from backend.src.models.session import Session
from backend.src.models.message import Message

logger = logging.getLogger(__name__)


class SessionRepository:
    """
    会话存储库
    提供会话数据的CRUD操作
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
            logger.info("会话存储库初始化完成")

        except Exception as e:
            logger.error(f"会话存储库初始化失败: {e}", exc_info=True)
            raise

    async def create_session(
        self,
        user_id: Optional[str] = None,
        title: Optional[str] = None,
        status: str = "active",
        active_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Session:
        """
        创建会话

        Args:
            user_id: 用户ID（可为空）
            title: 会话标题
            status: 会话状态
            active_agent: 当前活跃智能体
            metadata: 会话元数据

        Returns:
            Session: 创建的会话对象
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with get_db_session() as session:
                # 创建会话对象
                session_obj = Session(
                    user_id=user_id,
                    title=title or "新会话",
                    status=status,
                    active_agent=active_agent,
                    metadata=metadata or {},
                )

                session.add(session_obj)
                await session.commit()
                await session.refresh(session_obj)

                logger.debug(f"创建会话: session_id={session_obj.id}, user={user_id}, title={session_obj.title}")

                return session_obj

        except Exception as e:
            logger.error(f"创建会话失败: user={user_id}, error={e}", exc_info=True)
            raise

    async def get_session(self, session_id: str) -> Optional[Session]:
        """
        获取会话

        Args:
            session_id: 会话ID

        Returns:
            Optional[Session]: 会话对象，如果不存在则返回None
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with get_db_session() as db_session:
                stmt = select(Session).where(Session.id == session_id)
                result = await db_session.execute(stmt)
                session_obj = result.scalar_one_or_none()

                return session_obj

        except Exception as e:
            logger.error(f"获取会话失败: session_id={session_id}, error={e}", exc_info=True)
            return None

    async def update_session(
        self,
        session_id: str,
        **kwargs,
    ) -> Optional[Session]:
        """
        更新会话

        Args:
            session_id: 会话ID
            **kwargs: 要更新的字段

        Returns:
            Optional[Session]: 更新后的会话对象，如果不存在则返回None
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with get_db_session() as session:
                # 检查会话是否存在
                stmt = select(Session).where(Session.id == session_id)
                result = await session.execute(stmt)
                session_obj = result.scalar_one_or_none()

                if not session_obj:
                    logger.warning(f"会话不存在，无法更新: session_id={session_id}")
                    return None

                # 更新字段
                for key, value in kwargs.items():
                    if hasattr(session_obj, key):
                        setattr(session_obj, key, value)
                    else:
                        logger.warning(f"会话没有字段 {key}，跳过更新")

                # 自动更新更新时间
                session_obj.updated_at = datetime.utcnow()

                await session.commit()
                await session.refresh(session_obj)

                logger.debug(f"更新会话: session_id={session_id}, fields={list(kwargs.keys())}")

                return session_obj

        except Exception as e:
            logger.error(f"更新会话失败: session_id={session_id}, error={e}", exc_info=True)
            return None

    async def delete_session(self, session_id: str) -> bool:
        """
        删除会话

        Args:
            session_id: 会话ID

        Returns:
            bool: 是否删除成功
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with get_db_session() as session:
                stmt = select(Session).where(Session.id == session_id)
                result = await session.execute(stmt)
                session_obj = result.scalar_one_or_none()

                if not session_obj:
                    logger.warning(f"会话不存在，无法删除: session_id={session_id}")
                    return False

                await session.delete(session_obj)
                await session.commit()

                logger.debug(f"删除会话: session_id={session_id}")

                return True

        except Exception as e:
            logger.error(f"删除会话失败: session_id={session_id}, error={e}", exc_info=True)
            return False

    async def list_sessions(
        self,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        active_agent: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        order_by: str = "updated_at",
        order_desc: bool = True,
        include_message_count: bool = False,
    ) -> Tuple[List[Session], int]:
        """
        列出会话

        Args:
            user_id: 用户ID过滤
            status: 状态过滤
            active_agent: 活跃智能体过滤
            page: 页码
            page_size: 每页数量
            order_by: 排序字段
            order_desc: 是否降序
            include_message_count: 是否包含消息数量

        Returns:
            Tuple[List[Session], int]: 会话列表和总数
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with get_db_session() as session:
                # 构建查询条件
                conditions = []

                if user_id:
                    conditions.append(Session.user_id == user_id)

                if status:
                    conditions.append(Session.status == status)

                if active_agent:
                    conditions.append(Session.active_agent == active_agent)

                # 查询总数
                count_stmt = select(func.count()).select_from(Session)
                if conditions:
                    count_stmt = count_stmt.where(and_(*conditions))

                count_result = await session.execute(count_stmt)
                total = count_result.scalar_one()

                # 查询数据
                stmt = select(Session)
                if conditions:
                    stmt = stmt.where(and_(*conditions))

                # 排序
                order_column = getattr(Session, order_by, Session.updated_at)
                if order_desc:
                    stmt = stmt.order_by(desc(order_column))
                else:
                    stmt = stmt.order_by(asc(order_column))

                # 分页
                offset = (page - 1) * page_size
                stmt = stmt.offset(offset).limit(page_size)

                result = await session.execute(stmt)
                sessions = result.scalars().all()

                # 如果需要消息数量，为每个会话查询消息数量
                if include_message_count:
                    for session_obj in sessions:
                        msg_count_stmt = select(func.count(Message.id)).where(Message.session_id == session_obj.id)
                        msg_count_result = await session.execute(msg_count_stmt)
                        # 将消息数量存储为临时属性
                        session_obj._message_count = msg_count_result.scalar_one()

                return sessions, total

        except Exception as e:
            logger.error(f"列出会话失败: user={user_id}, error={e}", exc_info=True)
            return [], 0

    async def search_sessions(
        self,
        user_id: Optional[str] = None,
        title_query: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Session], int]:
        """
        搜索会话

        Args:
            user_id: 用户ID过滤
            title_query: 标题查询（模糊匹配）
            status: 状态过滤
            start_date: 开始时间
            end_date: 结束时间
            page: 页码
            page_size: 每页数量

        Returns:
            Tuple[List[Session], int]: 会话列表和总数
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with get_db_session() as session:
                # 构建查询条件
                conditions = []

                if user_id:
                    conditions.append(Session.user_id == user_id)

                if title_query:
                    conditions.append(Session.title.contains(title_query))

                if status:
                    conditions.append(Session.status == status)

                if start_date:
                    conditions.append(Session.created_at >= start_date)

                if end_date:
                    conditions.append(Session.created_at <= end_date)

                # 查询总数
                count_stmt = select(func.count()).select_from(Session)
                if conditions:
                    count_stmt = count_stmt.where(and_(*conditions))

                count_result = await session.execute(count_stmt)
                total = count_result.scalar_one()

                # 查询数据
                stmt = select(Session)
                if conditions:
                    stmt = stmt.where(and_(*conditions))

                # 排序和分页
                stmt = stmt.order_by(desc(Session.updated_at))
                offset = (page - 1) * page_size
                stmt = stmt.offset(offset).limit(page_size)

                result = await session.execute(stmt)
                sessions = result.scalars().all()

                return sessions, total

        except Exception as e:
            logger.error(f"搜索会话失败: error={e}", exc_info=True)
            return [], 0

    async def get_user_sessions(
        self,
        user_id: str,
        limit: int = 10,
        include_inactive: bool = False,
    ) -> List[Session]:
        """
        获取用户的会话列表

        Args:
            user_id: 用户ID
            limit: 返回数量
            include_inactive: 是否包含非活跃会话

        Returns:
            List[Session]: 会话列表
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with get_db_session() as session:
                conditions = [Session.user_id == user_id]

                if not include_inactive:
                    conditions.append(Session.status == "active")

                stmt = (
                    select(Session)
                    .where(and_(*conditions))
                    .order_by(desc(Session.updated_at))
                    .limit(limit)
                )

                result = await session.execute(stmt)
                sessions = result.scalars().all()

                return sessions

        except Exception as e:
            logger.error(f"获取用户会话失败: user={user_id}, error={e}", exc_info=True)
            return []

    async def get_session_statistics(
        self,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        获取会话统计信息

        Args:
            user_id: 用户ID过滤
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

                if user_id:
                    conditions.append(Session.user_id == user_id)

                if start_date:
                    conditions.append(Session.created_at >= start_date)

                if end_date:
                    conditions.append(Session.created_at <= end_date)

                base_query = select(Session)
                if conditions:
                    base_query = base_query.where(and_(*conditions))

                # 统计各类会话数量
                status_stats_stmt = (
                    select(Session.status, func.count(Session.id))
                    .group_by(Session.status)
                )
                if conditions:
                    status_stats_stmt = status_stats_stmt.where(and_(*conditions))

                status_result = await session.execute(status_stats_stmt)
                status_stats = dict(status_result.all())

                # 统计活跃智能体分布
                agent_stats_stmt = (
                    select(Session.active_agent, func.count(Session.id))
                    .where(Session.active_agent.is_not(None))
                    .group_by(Session.active_agent)
                )
                if conditions:
                    agent_stats_stmt = agent_stats_stmt.where(and_(*conditions))

                agent_result = await session.execute(agent_stats_stmt)
                agent_stats = dict(agent_result.all())

                # 统计用户分布
                user_stats_stmt = (
                    select(Session.user_id, func.count(Session.id))
                    .where(Session.user_id.is_not(None))
                    .group_by(Session.user_id)
                )
                if conditions:
                    user_stats_stmt = user_stats_stmt.where(and_(*conditions))

                user_result = await session.execute(user_stats_stmt)
                user_stats = dict(user_result.all())

                # 统计消息总数
                total_messages_stmt = select(func.count(Message.id))
                if conditions:
                    # 需要连接会话表进行过滤
                    total_messages_stmt = (
                        total_messages_stmt
                        .join(Session, Session.id == Message.session_id)
                        .where(and_(*conditions))
                    )

                total_messages_result = await session.execute(total_messages_stmt)
                total_messages = total_messages_result.scalar_one()

                # 统计平均消息数
                if status_stats:
                    total_sessions = sum(status_stats.values())
                    avg_messages = total_messages / total_sessions if total_sessions > 0 else 0
                else:
                    avg_messages = 0

                return {
                    "status_stats": status_stats,
                    "agent_stats": agent_stats,
                    "user_stats": user_stats,
                    "total_sessions": sum(status_stats.values()),
                    "total_messages": total_messages,
                    "avg_messages_per_session": avg_messages,
                    "date_range": {
                        "start": start_date.isoformat() if start_date else None,
                        "end": end_date.isoformat() if end_date else None,
                    },
                }

        except Exception as e:
            logger.error(f"获取会话统计失败: error={e}", exc_info=True)
            return {
                "status_stats": {},
                "agent_stats": {},
                "user_stats": {},
                "total_sessions": 0,
                "total_messages": 0,
                "avg_messages_per_session": 0,
                "date_range": {"start": None, "end": None},
            }

    async def cleanup_old_sessions(
        self,
        days_to_keep: int = 90,
        batch_size: int = 100,
    ) -> int:
        """
        清理旧会话

        Args:
            days_to_keep: 保留天数
            batch_size: 批量大小

        Returns:
            int: 删除的会话数量
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
                    # 查找要删除的会话ID
                    find_stmt = (
                        select(Session.id)
                        .where(Session.updated_at < cutoff_date)
                        .limit(batch_size)
                    )

                    result = await session.execute(find_stmt)
                    session_ids = result.scalars().all()

                    if not session_ids:
                        break

                    # 删除会话（级联删除消息）
                    delete_stmt = delete(Session).where(Session.id.in_(session_ids))
                    await session.execute(delete_stmt)
                    await session.commit()

                    deleted_count += len(session_ids)
                    logger.info(f"删除 {len(session_ids)} 个旧会话，累计 {deleted_count} 个")

                return deleted_count

        except Exception as e:
            logger.error(f"清理旧会话失败: error={e}", exc_info=True)
            return 0

    async def update_session_title(
        self,
        session_id: str,
        title: Optional[str] = None,
        auto_generate: bool = True,
        max_messages: int = 5,
    ) -> Optional[Session]:
        """
        更新会话标题

        Args:
            session_id: 会话ID
            title: 新标题（如果提供，则直接使用）
            auto_generate: 是否自动生成标题
            max_messages: 自动生成时使用的最大消息数

        Returns:
            Optional[Session]: 更新后的会话对象
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with get_db_session() as session:
                # 获取会话
                stmt = select(Session).where(Session.id == session_id)
                result = await session.execute(stmt)
                session_obj = result.scalar_one_or_none()

                if not session_obj:
                    logger.warning(f"会话不存在，无法更新标题: session_id={session_id}")
                    return None

                if title:
                    # 使用提供的标题
                    session_obj.title = title
                elif auto_generate:
                    # 自动生成标题
                    # 获取会话的消息
                    messages_stmt = (
                        select(Message)
                        .where(Message.session_id == session_id)
                        .order_by(Message.created_at.asc())
                        .limit(max_messages)
                    )
                    messages_result = await session.execute(messages_stmt)
                    messages = messages_result.scalars().all()

                    # 获取第一条用户消息
                    user_messages = [msg for msg in messages if msg.role == "user"]
                    if user_messages:
                        first_message = user_messages[0]
                        content = first_message.content
                        if content and len(content) > 50:
                            session_obj.title = content[:47] + "..."
                        elif content:
                            session_obj.title = content
                        else:
                            session_obj.title = "新会话"
                    else:
                        session_obj.title = "新会话"

                # 更新时间
                session_obj.updated_at = datetime.utcnow()

                await session.commit()
                await session.refresh(session_obj)

                logger.debug(f"更新会话标题: session_id={session_id}, title={session_obj.title}")

                return session_obj

        except Exception as e:
            logger.error(f"更新会话标题失败: session_id={session_id}, error={e}", exc_info=True)
            return None

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
                count_stmt = select(func.count()).select_from(Session)
                await session.execute(count_stmt)

                # 获取统计信息
                total_sessions_stmt = select(func.count(Session.id))
                total_result = await session.execute(total_sessions_stmt)
                total_sessions = total_result.scalar_one()

                # 获取活跃会话数量
                active_sessions_stmt = select(func.count(Session.id)).where(Session.status == "active")
                active_result = await session.execute(active_sessions_stmt)
                active_sessions = active_result.scalar_one()

                return {
                    "status": "healthy",
                    "message": "会话存储库连接正常",
                    "total_sessions": total_sessions,
                    "active_sessions": active_sessions,
                    "initialized": self._initialized,
                }

        except Exception as e:
            logger.error(f"会话存储库健康检查失败: {e}")
            return {
                "status": "unhealthy",
                "message": f"会话存储库连接失败: {str(e)}",
                "total_sessions": 0,
                "active_sessions": 0,
                "initialized": self._initialized,
            }


# 全局会话存储库实例
session_repository = SessionRepository()