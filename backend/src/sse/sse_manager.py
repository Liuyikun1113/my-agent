"""
SSE管理器
处理Server-Sent Events连接、心跳和消息广播
"""
import asyncio
import json
import logging
import time
import uuid
from typing import Dict, Set, Optional, AsyncGenerator, Any
from datetime import datetime, timedelta
from enum import Enum, auto

from config.settings import settings

logger = logging.getLogger(__name__)


class EventType(Enum):
    """事件类型"""
    CHAT_MESSAGE = auto()          # 聊天消息（完整）
    CHAT_DELTA = auto()            # 聊天消息增量（流式逐token）
    TOOL_RESULT = auto()           # 工具结果
    AGENT_STATUS = auto()          # 智能体状态
    SYSTEM_NOTIFICATION = auto()   # 系统通知
    HEARTBEAT = auto()             # 心跳
    ERROR = auto()                 # 错误
    SESSION_UPDATE = auto()        # 会话更新
    INTENT_UPDATE = auto()         # 意图更新


class SSEClient:
    """SSE客户端连接"""

    def __init__(self, client_id: str, user_id: Optional[str] = None, session_id: Optional[str] = None):
        self.client_id = client_id
        self.user_id = user_id
        self.session_id = session_id
        self.connected_at = datetime.now()
        self.last_activity = datetime.now()
        self._message_queue = asyncio.Queue()
        self._is_active = True
        self.subscriptions: Set[EventType] = set()
        self.metadata: Dict[str, Any] = {}

    async def send_event(self, event_type: EventType, data: Any, event_id: Optional[str] = None):
        """发送事件到客户端"""
        if not self._is_active:
            return False

        event = {
            "type": event_type.name,
            "data": data,
            "id": event_id or str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
        }

        try:
            await self._message_queue.put(event)
            self.last_activity = datetime.now()
            return True
        except Exception as e:
            logger.error(f"发送事件到客户端失败 {self.client_id}: {e}")
            return False

    async def event_generator(self) -> AsyncGenerator[str, None]:
        """生成SSE事件流"""
        try:
            # 发送连接确认
            yield self._format_sse_event(
                event_type=EventType.SYSTEM_NOTIFICATION,
                data={"message": "SSE连接已建立", "client_id": self.client_id},
                event_id="connection_established"
            )

            # 发送初始心跳
            yield self._format_sse_event(
                event_type=EventType.HEARTBEAT,
                data={"timestamp": datetime.now().isoformat()},
                event_id="initial_heartbeat"
            )

            # 主事件循环
            while self._is_active:
                try:
                    # 等待消息或超时
                    event = await asyncio.wait_for(
                        self._message_queue.get(),
                        timeout=settings.SSE_HEARTBEAT_INTERVAL
                    )

                    # 发送事件
                    yield self._format_sse_event(
                        event_type=EventType[event["type"]],
                        data=event["data"],
                        event_id=event["id"]
                    )

                    # 标记任务完成
                    self._message_queue.task_done()

                except asyncio.TimeoutError:
                    # 发送心跳
                    yield self._format_sse_event(
                        event_type=EventType.HEARTBEAT,
                        data={"timestamp": datetime.now().isoformat()},
                        event_id=f"heartbeat_{int(time.time())}"
                    )

                except asyncio.CancelledError:
                    break

        except Exception as e:
            logger.error(f"SSE事件生成器异常 {self.client_id}: {e}")
        finally:
            await self.disconnect()

    def _format_sse_event(self, event_type: EventType, data: Any, event_id: str) -> str:
        """格式化SSE事件"""
        event_data = {
            "type": event_type.name,
            "data": data,
            "id": event_id,
            "timestamp": datetime.now().isoformat(),
        }

        lines = []
        lines.append(f"event: {event_type.name.lower()}")
        lines.append(f"id: {event_id}")
        lines.append(f"data: {json.dumps(event_data, ensure_ascii=False)}")
        lines.append("")  # 空行表示事件结束
        return "\n".join(lines)

    async def disconnect(self):
        """断开连接"""
        if not self._is_active:
            return

        self._is_active = False

        # 发送断开连接事件
        try:
            # 清空队列中的剩余消息
            while not self._message_queue.empty():
                try:
                    self._message_queue.get_nowait()
                    self._message_queue.task_done()
                except asyncio.QueueEmpty:
                    break
        except Exception:
            pass

        logger.info(f"SSE客户端断开连接: {self.client_id}")

    def is_active(self) -> bool:
        """检查客户端是否活跃"""
        if not self._is_active:
            return False

        # 检查超时
        timeout = timedelta(seconds=settings.SSE_HEARTBEAT_INTERVAL * 3)
        if datetime.now() - self.last_activity > timeout:
            self._is_active = False
            return False

        return True

    def subscribe(self, event_type: EventType):
        """订阅事件类型"""
        self.subscriptions.add(event_type)

    def unsubscribe(self, event_type: EventType):
        """取消订阅事件类型"""
        self.subscriptions.discard(event_type)

    def has_subscription(self, event_type: EventType) -> bool:
        """检查是否订阅了事件类型"""
        return event_type in self.subscriptions


class SSEManager:
    """SSE管理器"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._clients: Dict[str, SSEClient] = {}
            cls._instance._cleanup_task: Optional[asyncio.Task] = None
            cls._instance._is_running = False
        return cls._instance

    async def start(self):
        """启动SSE管理器"""
        if self._is_running:
            return

        self._is_running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_inactive_clients())
        logger.info("SSE管理器已启动")

    async def stop(self):
        """停止SSE管理器"""
        self._is_running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # 断开所有客户端
        for client in list(self._clients.values()):
            await client.disconnect()

        self._clients.clear()
        logger.info("SSE管理器已停止")

    async def create_client(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SSEClient:
        """创建新的SSE客户端"""
        client_id = str(uuid.uuid4())
        client = SSEClient(client_id, user_id, session_id)

        if metadata:
            client.metadata = metadata

        # 默认订阅聊天消息（完整+增量）、系统通知和心跳
        client.subscribe(EventType.CHAT_MESSAGE)
        client.subscribe(EventType.CHAT_DELTA)
        client.subscribe(EventType.SYSTEM_NOTIFICATION)
        client.subscribe(EventType.HEARTBEAT)

        self._clients[client_id] = client
        logger.info(f"SSE客户端已创建: {client_id}, 用户: {user_id}, 会话: {session_id}")

        return client

    async def disconnect_client(self, client_id: str):
        """断开指定客户端"""
        if client_id in self._clients:
            client = self._clients[client_id]
            await client.disconnect()
            del self._clients[client_id]
            logger.info(f"SSE客户端已断开: {client_id}")

    def get_client(self, client_id: str) -> Optional[SSEClient]:
        """获取客户端"""
        return self._clients.get(client_id)

    async def broadcast_event(
        self,
        event_type: EventType,
        data: Any,
        event_id: Optional[str] = None,
        filter_func: Optional[callable] = None,
    ) -> int:
        """
        广播事件到所有匹配的客户端

        Args:
            event_type: 事件类型
            data: 事件数据
            event_id: 事件ID（可选）
            filter_func: 过滤函数，接收客户端参数，返回bool

        Returns:
            int: 发送成功的客户端数量
        """
        if not self._is_running:
            return 0

        sent_count = 0
        event_id = event_id or str(uuid.uuid4())

        for client in list(self._clients.values()):
            try:
                # 检查客户端是否活跃
                if not client.is_active():
                    continue

                # 检查订阅
                if not client.has_subscription(event_type):
                    continue

                # 应用过滤函数
                if filter_func and not filter_func(client):
                    continue

                # 发送事件
                if await client.send_event(event_type, data, event_id):
                    sent_count += 1

            except Exception as e:
                logger.error(f"广播事件到客户端失败 {client.client_id}: {e}")

        if sent_count > 0:
            logger.debug(f"事件广播成功: {event_type.name}, 客户端数: {sent_count}, 事件ID: {event_id}")

        return sent_count

    async def send_to_client(
        self,
        client_id: str,
        event_type: EventType,
        data: Any,
        event_id: Optional[str] = None,
    ) -> bool:
        """发送事件到指定客户端"""
        client = self.get_client(client_id)
        if not client or not client.is_active():
            return False

        if not client.has_subscription(event_type):
            logger.debug(f"客户端未订阅事件类型: {client_id}, {event_type.name}")
            return False

        return await client.send_event(event_type, data, event_id)

    async def send_to_user(
        self,
        user_id: str,
        event_type: EventType,
        data: Any,
        event_id: Optional[str] = None,
    ) -> int:
        """发送事件到指定用户的所有客户端"""
        sent_count = 0

        for client in list(self._clients.values()):
            if client.user_id == user_id and client.is_active() and client.has_subscription(event_type):
                if await client.send_event(event_type, data, event_id):
                    sent_count += 1

        return sent_count

    async def send_to_session(
        self,
        session_id: str,
        event_type: EventType,
        data: Any,
        event_id: Optional[str] = None,
    ) -> int:
        """发送事件到指定会话的所有客户端"""
        sent_count = 0

        for client in list(self._clients.values()):
            if client.session_id == session_id and client.is_active() and client.has_subscription(event_type):
                if await client.send_event(event_type, data, event_id):
                    sent_count += 1

        return sent_count

    def get_active_clients_count(self) -> int:
        """获取活跃客户端数量"""
        return sum(1 for client in self._clients.values() if client.is_active())

    def get_client_stats(self) -> Dict[str, Any]:
        """获取客户端统计信息"""
        total_clients = len(self._clients)
        active_clients = self.get_active_clients_count()

        # 按用户分组统计
        users: Dict[str, int] = {}
        for client in self._clients.values():
            if client.user_id:
                users[client.user_id] = users.get(client.user_id, 0) + 1

        # 按会话分组统计
        sessions: Dict[str, int] = {}
        for client in self._clients.values():
            if client.session_id:
                sessions[client.session_id] = sessions.get(client.session_id, 0) + 1

        # 订阅统计
        subscriptions: Dict[str, int] = {}
        for client in self._clients.values():
            for event_type in client.subscriptions:
                event_name = event_type.name
                subscriptions[event_name] = subscriptions.get(event_name, 0) + 1

        return {
            "total_clients": total_clients,
            "active_clients": active_clients,
            "inactive_clients": total_clients - active_clients,
            "unique_users": len(users),
            "unique_sessions": len(sessions),
            "subscriptions": subscriptions,
            "timestamp": datetime.now().isoformat(),
        }

    async def _cleanup_inactive_clients(self):
        """清理非活跃客户端"""
        while self._is_running:
            try:
                await asyncio.sleep(60)  # 每分钟清理一次

                clients_to_remove = []
                for client_id, client in list(self._clients.items()):
                    if not client.is_active():
                        clients_to_remove.append(client_id)

                for client_id in clients_to_remove:
                    if client_id in self._clients:
                        client = self._clients[client_id]
                        await client.disconnect()
                        del self._clients[client_id]
                        logger.info(f"清理非活跃SSE客户端: {client_id}")

                if clients_to_remove:
                    logger.debug(f"清理了 {len(clients_to_remove)} 个非活跃SSE客户端")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理非活跃客户端时出错: {e}")

    def __del__(self):
        """析构函数"""
        if self._is_running:
            asyncio.create_task(self.stop())


# 全局SSE管理器实例
sse_manager = SSEManager()