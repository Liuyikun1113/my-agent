"""
记忆管理器 - 协调短期、长期、向量记忆存储
"""
import asyncio
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import uuid

from backend.src.memory.interfaces.memory_store import MemoryStore
from backend.src.memory.interfaces.memory_item import MemoryItem
from backend.src.api.schemas.session import SessionResponse
from backend.src.api.schemas.chat import MessageResponse
from backend.src.utils.async_utils import retry_async, timeout_async
from backend.src.utils.helpers import truncate_text, safe_get

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    记忆管理器，协调三层记忆存储：
    1. 短期记忆 (Redis) - 快速访问，TTL有限
    2. 长期记忆 (MySQL) - 持久化存储
    3. 向量记忆 (Milvus) - 语义搜索
    """

    def __init__(self):
        self.short_term_store: Optional[MemoryStore] = None
        self.long_term_store: Optional[MemoryStore] = None
        self.vector_store: Optional[MemoryStore] = None
        self._initialized = False

    async def initialize(self):
        """
        初始化所有记忆存储
        """
        if self._initialized:
            return

        try:
            # 初始化短期记忆存储 (Redis)
            from memory.short_term.redis_store import RedisMemoryStore
            self.short_term_store = RedisMemoryStore()
            await self.short_term_store.initialize()
            logger.info("短期记忆存储初始化完成")

            # 初始化长期记忆存储 (MySQL)
            from memory.long_term.sql_store import SQLStore
            self.long_term_store = SQLStore()
            await self.long_term_store.initialize()
            logger.info("长期记忆存储初始化完成")

            # 初始化向量记忆存储 (Milvus)
            from memory.vector.milvus_store import MilvusMemoryStore
            self.vector_store = MilvusMemoryStore()
            await self.vector_store.initialize()
            logger.info("向量记忆存储初始化完成")

            self._initialized = True
            logger.info("记忆管理器初始化完成")

        except Exception as e:
            logger.error(f"记忆管理器初始化失败: {e}", exc_info=True)
            raise

    # ===== 会话管理方法 =====

    async def create_session(
        self,
        title: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> SessionResponse:
        """
        创建新会话

        Args:
            title: 会话标题
            description: 会话描述
            metadata: 会话元数据
            user_id: 用户ID

        Returns:
            SessionResponse: 创建的会话
        """
        try:
            if not self._initialized:
                await self.initialize()

            # 生成会话ID
            session_id = str(uuid.uuid4())

            # 创建会话对象
            session_data = {
                "id": session_id,
                "user_id": user_id,
                "title": title,
                "description": description,
                "status": "active",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "metadata": metadata or {},
            }

            # metadata 中单独存一份 user_id，方便存储层索引
            item_metadata = metadata or {}
            if user_id:
                item_metadata["user_id"] = user_id

            # 保存到长期记忆
            session_item = MemoryItem(
                id=session_id,
                type="session",
                data=session_data,
                metadata=item_metadata,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            await self.long_term_store.save(session_item)

            # 同时保存到短期记忆（用于快速访问）
            await self.short_term_store.save(session_item)

            # 转换为响应模型
            return SessionResponse(**session_data)

        except Exception as e:
            logger.error(f"创建会话失败: {e}", exc_info=True)
            raise

    async def get_session(self, session_id: str) -> Optional[SessionResponse]:
        """
        获取会话

        Args:
            session_id: 会话ID

        Returns:
            Optional[SessionResponse]: 会话信息，如果不存在则返回None
        """
        try:
            if not self._initialized:
                await self.initialize()

            # 首先尝试从短期记忆获取
            session_item = await self.short_term_store.get(session_id)
            if session_item:
                return SessionResponse(**session_item.data)

            # 如果短期记忆中没有，从长期记忆获取
            session_item = await self.long_term_store.get(session_id)
            if session_item:
                # 同时保存到短期记忆（缓存）
                await self.short_term_store.save(session_item)
                return SessionResponse(**session_item.data)

            return None

        except Exception as e:
            logger.error(f"获取会话失败: {e}", exc_info=True)
            return None

    async def get_sessions(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        title: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Tuple[List[SessionResponse], int]:
        """
        获取会话列表

        Args:
            page: 页码
            page_size: 每页数量
            status: 状态过滤
            title: 标题搜索
            user_id: 用户ID过滤

        Returns:
            Tuple[List[SessionResponse], int]: 会话列表和总数
        """
        try:
            if not self._initialized:
                await self.initialize()

            # 从长期记忆获取
            filters = {}
            if status:
                filters["status"] = status
            if title:
                filters["title"] = title
            if user_id:
                filters["user_id"] = user_id

            sessions, total = await self.long_term_store.list(
                type="session",
                filters=filters,
                page=page,
                page_size=page_size,
                order_by="-created_at",
            )

            session_responses = []
            for session_item in sessions:
                session_responses.append(SessionResponse(**session_item.data))

            return session_responses, total

        except Exception as e:
            logger.error(f"获取会话列表失败: {e}", exc_info=True)
            return [], 0

    async def update_session(
        self,
        session_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SessionResponse:
        """
        更新会话

        Args:
            session_id: 会话ID
            title: 新标题
            description: 新描述
            status: 新状态
            metadata: 新元数据

        Returns:
            SessionResponse: 更新后的会话
        """
        try:
            if not self._initialized:
                await self.initialize()

            # 获取现有会话
            existing_item = await self.long_term_store.get(session_id)
            if not existing_item:
                raise ValueError(f"会话不存在: {session_id}")

            # 更新数据
            updated_data = existing_item.data.copy()
            if title is not None:
                updated_data["title"] = title
            if description is not None:
                updated_data["description"] = description
            if status is not None:
                updated_data["status"] = status
            if metadata is not None:
                updated_data["metadata"] = metadata
            updated_data["updated_at"] = datetime.now()

            # 更新元数据
            updated_metadata = existing_item.metadata.copy()
            if metadata:
                updated_metadata.update(metadata)

            # 创建更新后的记忆项
            updated_item = MemoryItem(
                id=session_id,
                type="session",
                data=updated_data,
                metadata=updated_metadata,
                created_at=existing_item.created_at,
                updated_at=datetime.now(),
            )

            # 更新到长期记忆
            await self.long_term_store.save(updated_item)

            # 更新到短期记忆
            await self.short_term_store.save(updated_item)

            return SessionResponse(**updated_data)

        except Exception as e:
            logger.error(f"更新会话失败: {e}", exc_info=True)
            raise

    # ===== 消息管理方法 =====

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: Optional[str] = None,
        parent_message_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None,
        intent: Optional[str] = None,
        intent_confidence: Optional[float] = None,
    ) -> MessageResponse:
        """
        保存消息

        Args:
            session_id: 会话ID
            role: 消息角色 (user, assistant, system, tool)
            content: 消息内容
            parent_message_id: 父消息ID
            metadata: 消息元数据
            tool_calls: 工具调用信息
            tool_results: 工具调用结果
            intent: 意图标签
            intent_confidence: 意图置信度

        Returns:
            MessageResponse: 保存的消息
        """
        try:
            if not self._initialized:
                await self.initialize()

            # 生成消息ID
            message_id = str(uuid.uuid4())

            # 从会话中获取 user_id
            user_id = None
            session = await self.get_session(session_id)
            if session:
                user_id = session.user_id

            # 创建消息数据
            message_data = {
                "id": message_id,
                "session_id": session_id,
                "role": role,
                "content": content,
                "tool_calls": tool_calls or [],
                "tool_results": tool_results or [],
                "created_at": datetime.now(),
                "parent_message_id": parent_message_id,
                "metadata": metadata or {},
                "intent": intent,
                "intent_confidence": intent_confidence,
                "processing_status": "pending",
                "error_message": None,
            }

            # metadata 中存入 user_id，方便存储层索引
            item_metadata = metadata or {}
            if user_id:
                item_metadata["user_id"] = user_id

            # 创建记忆项
            message_item = MemoryItem(
                id=message_id,
                type="message",
                data=message_data,
                metadata=item_metadata,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            # 保存到长期记忆 (MySQL, 同步写入 — source of truth)
            await self.long_term_store.save(message_item)

            # 保存到短期记忆 (Redis 列表, 最近10条, 容错+轻量重试)
            try:
                await retry_async(
                    self.short_term_store.push_to_session_list,
                    max_attempts=2,
                    backoff_factor=1.0,
                    exceptions=(Exception,),
                    session_id=session_id,
                    message_data=message_data,
                    max_len=10,
                )
            except Exception as e:
                logger.warning(f"Redis写入失败 (消息仍已持久化到MySQL): {e}")

            # 触发压缩检查（后台异步）
            asyncio.create_task(
                self._maybe_compress(session_id)
            )

            return MessageResponse(**message_data)

        except Exception as e:
            logger.error(f"保存消息失败: {e}", exc_info=True)
            raise

    async def get_message(self, message_id: str) -> Optional[MessageResponse]:
        """
        获取消息

        Args:
            message_id: 消息ID

        Returns:
            Optional[MessageResponse]: 消息信息，如果不存在则返回None
        """
        try:
            if not self._initialized:
                await self.initialize()

            # 首先尝试从短期记忆获取
            message_item = await self.short_term_store.get(message_id)
            if message_item:
                return MessageResponse(**message_item.data)

            # 如果短期记忆中没有，从长期记忆获取
            message_item = await self.long_term_store.get(message_id)
            if message_item:
                # 同时保存到短期记忆（缓存）
                await self.short_term_store.save(message_item)
                return MessageResponse(**message_item.data)

            return None

        except Exception as e:
            logger.error(f"获取消息失败: {e}", exc_info=True)
            return None

    async def get_messages(
        self,
        session_id: str,
        page: int = 1,
        page_size: int = 20,
        role: Optional[str] = None,
        parent_message_id: Optional[str] = None,
    ) -> Tuple[List[MessageResponse], int]:
        """
        获取会话消息列表

        Args:
            session_id: 会话ID
            page: 页码
            page_size: 每页数量
            role: 角色过滤
            parent_message_id: 父消息ID过滤

        Returns:
            Tuple[List[MessageResponse], int]: 消息列表和总数
        """
        try:
            if not self._initialized:
                await self.initialize()

            # 构建过滤条件
            filters = {"session_id": session_id}
            if role:
                filters["role"] = role
            if parent_message_id:
                filters["parent_message_id"] = parent_message_id

            # 从长期记忆获取
            messages, total = await self.long_term_store.list(
                type="message",
                filters=filters,
                page=page,
                page_size=page_size,
                order_by="created_at",
            )

            message_responses = []
            for message_item in messages:
                message_responses.append(MessageResponse(**message_item.data))

            return message_responses, total

        except Exception as e:
            logger.error(f"获取消息列表失败: {e}", exc_info=True)
            return [], 0

    async def update_message(
        self,
        message_id: str,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        intent: Optional[str] = None,
        intent_confidence: Optional[float] = None,
        processing_status: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> MessageResponse:
        """
        更新消息

        Args:
            message_id: 消息ID
            content: 新内容
            metadata: 新元数据
            intent: 意图标签
            intent_confidence: 意图置信度
            processing_status: 处理状态
            error_message: 错误信息

        Returns:
            MessageResponse: 更新后的消息
        """
        try:
            if not self._initialized:
                await self.initialize()

            # 获取现有消息
            existing_item = await self.long_term_store.get(message_id)
            if not existing_item:
                raise ValueError(f"消息不存在: {message_id}")

            # 更新数据
            updated_data = existing_item.data.copy()
            if content is not None:
                updated_data["content"] = content
            if intent is not None:
                updated_data["intent"] = intent
            if intent_confidence is not None:
                updated_data["intent_confidence"] = intent_confidence
            if processing_status is not None:
                updated_data["processing_status"] = processing_status
            if error_message is not None:
                updated_data["error_message"] = error_message
            updated_data["updated_at"] = datetime.now()

            # 更新元数据
            updated_metadata = existing_item.metadata.copy()
            if metadata:
                updated_metadata.update(metadata)

            # 创建更新后的记忆项
            updated_item = MemoryItem(
                id=message_id,
                type="message",
                data=updated_data,
                metadata=updated_metadata,
                created_at=existing_item.created_at,
                updated_at=datetime.now(),
            )

            # 更新到长期记忆 (MySQL, 同步)
            await self.long_term_store.save(updated_item)

            # 更新到短期记忆 (Redis, 容错)
            session_id = updated_data.get("session_id")
            if session_id:
                try:
                    await self.short_term_store.push_to_session_list(
                        session_id, updated_data, max_len=10
                    )
                except Exception as e:
                    logger.warning(f"Redis更新失败 (消息仍已持久化到MySQL): {e}")

            return MessageResponse(**updated_data)

        except Exception as e:
            logger.error(f"更新消息失败: {e}", exc_info=True)
            raise

    # ===== 统计方法 =====

    async def get_session_message_count(self, session_id: str) -> int:
        """
        获取会话消息数量

        Args:
            session_id: 会话ID

        Returns:
            int: 消息数量
        """
        try:
            if not self._initialized:
                await self.initialize()

            # 从长期记忆获取统计
            filters = {"session_id": session_id}
            messages, total = await self.long_term_store.list(
                type="message",
                filters=filters,
                page=1,
                page_size=1,  # 只获取总数
            )

            return total

        except Exception as e:
            logger.error(f"获取会话消息数量失败: {e}", exc_info=True)
            return 0

    async def get_last_session_message(self, session_id: str) -> Optional[MessageResponse]:
        """
        获取会话最后一条消息

        Args:
            session_id: 会话ID

        Returns:
            Optional[MessageResponse]: 最后一条消息，如果没有则返回None
        """
        try:
            if not self._initialized:
                await self.initialize()

            # 从长期记忆获取最新消息
            filters = {"session_id": session_id}
            messages, total = await self.long_term_store.list(
                type="message",
                filters=filters,
                page=1,
                page_size=1,
                order_by="-created_at",
            )

            if messages:
                return MessageResponse(**messages[0].data)

            return None

        except Exception as e:
            logger.error(f"获取最后消息失败: {e}", exc_info=True)
            return None

    # ===== 搜索方法 =====

    async def search_messages(
        self,
        session_id: str,
        query: str,
        limit: int = 10,
    ) -> List[MessageResponse]:
        """
        语义搜索消息

        Args:
            session_id: 会话ID
            query: 搜索查询
            limit: 返回结果数量

        Returns:
            List[MessageResponse]: 搜索结果
        """
        try:
            if not self._initialized:
                await self.initialize()

            # 从向量记忆搜索（带超时保护）
            results = await timeout_async(
                self.vector_store.search(
                    query=query,
                    filters={"session_id": session_id},
                    limit=limit,
                ),
                timeout=5.0,
                default=[],
            )

            # 转换为消息响应
            message_responses = []
            for result in results:
                message_responses.append(MessageResponse(**result.data))

            return message_responses

        except Exception as e:
            logger.error(f"搜索消息失败: {e}", exc_info=True)
            return []

    # ===== 上下文组装 =====

    async def get_context(
        self,
        session_id: str,
        current_query: str,
        recent_count: int = 10,
        summary_limit: int = 5,
    ) -> Dict[str, Any]:
        """
        组装模型上下文：Redis 最近消息 + Milvus 语义检索相似摘要

        Args:
            session_id: 会话ID
            current_query: 当前用户输入
            recent_count: 从 Redis 获取的最近消息数
            summary_limit: 从 Milvus 检索的摘要数

        Returns:
            {"recent_messages": [...], "relevant_summaries": [...]}
        """
        try:
            if not self._initialized:
                await self.initialize()

            recent_messages = []
            try:
                recent_messages = await self.short_term_store.get_session_messages(
                    session_id, count=recent_count
                )
            except Exception as e:
                logger.warning(f"获取 Redis 最近消息失败: {e}")

            relevant_summaries = []
            if current_query:
                try:
                    results = await timeout_async(
                        self.vector_store.search(
                            query=current_query,
                            filters={"session_id": session_id, "type": "summary"},
                            limit=summary_limit,
                        ),
                        timeout=3.0,
                        default=[],
                    )
                    for r in results:
                        summary_data = (
                            r.data if isinstance(r, MemoryItem)
                            else safe_get(r, "data", default={})
                        )
                        relevant_summaries.append(summary_data)
                except Exception as e:
                    logger.warning(f"Milvus 摘要检索失败: {e}")

            return {
                "recent_messages": recent_messages,
                "relevant_summaries": relevant_summaries,
            }
        except Exception as e:
            logger.error(f"获取上下文失败: {e}")
            return {"recent_messages": [], "relevant_summaries": []}

    # ===== 清理方法 =====

    async def cleanup_old_sessions(self, days: int = 30):
        """
        清理旧的会话（归档超过指定天数的会话）

        Args:
            days: 天数阈值
        """
        # TODO: 实现会话清理逻辑
        pass

    async def cleanup_old_messages(self, days: int = 90):
        """
        清理旧的消息

        Args:
            days: 天数阈值
        """
        # TODO: 实现消息清理逻辑
        pass

    # ===== 内部辅助方法 =====

    async def _maybe_compress(self, session_id: str):
        """
        后台检查是否需要压缩会话消息。
        使用 Summarizer 生成摘要，摘要只存入 Milvus（不存 MySQL）。
        """
        try:
            count = await self.get_session_message_count(session_id)
            if count < 20:
                return

            messages, _ = await self.long_term_store.list(
                type="message",
                filters={"session_id": session_id},
                page=1,
                page_size=50,
                order_by="created_at",
            )

            if len(messages) < 20:
                return

            from memory.compression.summarizer import summarizer

            compressed = await summarizer.summarize_memory_items(
                messages, compression_ratio=0.3
            )

            for item in compressed:
                if item.type == "summary":
                    asyncio.create_task(
                        self._async_save_summary_to_vector(item)
                    )

            summary_count = sum(1 for i in compressed if i.type == "summary")
            sample_text = truncate_text(
                messages[-1].get_data_field("content") if messages else "", 100
            )
            logger.info(
                f"会话 {session_id} 压缩完成: "
                f"原始 {len(messages)} 条 → {summary_count} 条摘要写入 Milvus, "
                f"最近消息: {sample_text}"
            )
        except Exception as e:
            logger.warning(f"后台压缩检查失败 (会话 {session_id}): {e}")

    async def _async_save_summary_to_vector(self, summary_item: MemoryItem):
        """
        异步将摘要写入 Milvus（后台任务，轻量重试）
        """
        try:
            await retry_async(
                self.vector_store.save,
                max_attempts=2,
                backoff_factor=1.0,
                exceptions=(Exception,),
                summary_item,
            )
        except Exception as e:
            logger.error(f"摘要写入 Milvus 失败: {e}")


# 全局记忆管理器实例
memory_manager = MemoryManager()