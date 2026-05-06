"""
WebSocket中间件
提供双向实时通信支持（可选，SSE的增强替代）
"""
import logging
import json
import asyncio
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from enum import Enum

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws/v1", tags=["websocket"])


class WSMessageType(Enum):
    """WebSocket消息类型"""
    CHAT_MESSAGE = "chat_message"
    CHAT_RESPONSE = "chat_response"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    AGENT_STATUS = "agent_status"
    INTENT_UPDATE = "intent_update"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"
    SYSTEM = "system"


class WSClient:
    """WebSocket客户端连接"""

    def __init__(self, websocket: WebSocket, client_id: str, user_id: Optional[str] = None):
        self.websocket = websocket
        self.client_id = client_id
        self.user_id = user_id
        self.connected_at = datetime.now()
        self.last_heartbeat = datetime.now()
        self.subscriptions: Set[str] = set()
        self.is_connected = False

    async def send_message(self, msg_type: WSMessageType, data: Dict[str, Any]):
        """发送消息"""
        if not self.is_connected:
            return

        try:
            message = {
                "type": msg_type.value,
                "data": data,
                "timestamp": datetime.now().isoformat(),
                "client_id": self.client_id,
            }
            await self.websocket.send_json(message)
        except Exception as e:
            logger.error(f"WebSocket发送消息失败: {self.client_id}, error={e}")
            self.is_connected = False

    async def send_error(self, error_message: str, error_code: str = "UNKNOWN"):
        """发送错误消息"""
        await self.send_message(WSMessageType.ERROR, {
            "message": error_message,
            "code": error_code,
        })

    async def ping(self):
        """发送心跳"""
        await self.send_message(WSMessageType.PING, {
            "timestamp": datetime.now().isoformat(),
        })


class WSConnectionManager:
    """WebSocket连接管理器"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._clients: Dict[str, WSClient] = {}
            cls._instance._session_clients: Dict[str, Set[str]] = {}
        return cls._instance

    async def connect(self, websocket: WebSocket, client_id: str, user_id: Optional[str] = None) -> WSClient:
        """建立连接"""
        await websocket.accept()
        client = WSClient(websocket, client_id, user_id)
        client.is_connected = True
        self._clients[client_id] = client
        logger.info(f"WebSocket客户端已连接: {client_id}")
        return client

    def disconnect(self, client_id: str):
        """断开连接"""
        if client_id in self._clients:
            client = self._clients.pop(client_id)
            client.is_connected = False
            logger.info(f"WebSocket客户端已断开: {client_id}")
            for session_set in self._session_clients.values():
                session_set.discard(client_id)

    def get_client(self, client_id: str) -> Optional[WSClient]:
        """获取客户端"""
        return self._clients.get(client_id)

    async def broadcast(self, msg_type: WSMessageType, data: Dict[str, Any]):
        """广播消息"""
        disconnected = []
        for client_id, client in self._clients.items():
            try:
                await client.send_message(msg_type, data)
            except Exception:
                disconnected.append(client_id)

        for client_id in disconnected:
            self.disconnect(client_id)

    async def send_to_session(self, session_id: str, msg_type: WSMessageType, data: Dict[str, Any]):
        """向会话内的客户端发送消息"""
        client_ids = self._session_clients.get(session_id, set())
        for client_id in client_ids:
            client = self.get_client(client_id)
            if client and client.is_connected:
                await client.send_message(msg_type, data)

    async def send_to_user(self, user_id: str, msg_type: WSMessageType, data: Dict[str, Any]):
        """向特定用户发送消息"""
        for client in self._clients.values():
            if client.user_id == user_id and client.is_connected:
                await client.send_message(msg_type, data)

    def register_session(self, client_id: str, session_id: str):
        """注册客户端到会话"""
        if session_id not in self._session_clients:
            self._session_clients[session_id] = set()
        self._session_clients[session_id].add(client_id)

    @property
    def active_connections(self) -> int:
        return len([c for c in self._clients.values() if c.is_connected])


ws_manager = WSConnectionManager()


@router.websocket("/chat/{session_id}")
async def websocket_chat(
    websocket: WebSocket,
    session_id: str,
    user_id: Optional[str] = Query(None),
    client_id: Optional[str] = Query(None),
):
    """
    WebSocket聊天端点
    支持双向实时通信
    """
    if not client_id:
        import uuid
        client_id = f"ws_{uuid.uuid4().hex[:12]}"

    client = await ws_manager.connect(websocket, client_id, user_id)
    ws_manager.register_session(client_id, session_id)

    # 发送连接确认
    await client.send_message(WSMessageType.SYSTEM, {
        "message": "WebSocket连接已建立",
        "session_id": session_id,
        "client_id": client_id,
    })

    try:
        while True:
            try:
                raw_data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=settings.SSE_HEARTBEAT_INTERVAL,
                )

                data = json.loads(raw_data)
                msg_type = data.get("type", "")

                if msg_type == "ping":
                    await client.send_message(WSMessageType.PONG, {
                        "timestamp": datetime.now().isoformat(),
                    })
                    client.last_heartbeat = datetime.now()

                elif msg_type == "chat_message":
                    content = data.get("content", "")
                    logger.info(f"收到聊天消息: session={session_id}, client={client_id}")
                    await client.send_message(WSMessageType.CHAT_RESPONSE, {
                        "message": f"已收到消息: {content[:100]}",
                        "session_id": session_id,
                    })

                else:
                    logger.debug(f"未知消息类型: {msg_type}")

            except asyncio.TimeoutError:
                await client.ping()
            except json.JSONDecodeError:
                await client.send_error("无效的JSON格式", "INVALID_JSON")

    except WebSocketDisconnect:
        logger.info(f"WebSocket客户端断开: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket处理异常: {e}")
    finally:
        ws_manager.disconnect(client_id)


@router.websocket("/agent/{agent_id}")
async def websocket_agent(
    websocket: WebSocket,
    agent_id: str,
    user_id: Optional[str] = Query(None),
):
    """
    WebSocket智能体端点
    用于实时监控智能体状态
    """
    import uuid
    client_id = f"ws_agent_{uuid.uuid4().hex[:12]}"

    client = await ws_manager.connect(websocket, client_id, user_id)

    await client.send_message(WSMessageType.AGENT_STATUS, {
        "agent_id": agent_id,
        "status": "connected",
        "message": f"正在监控智能体: {agent_id}",
    })

    try:
        while True:
            try:
                raw_data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=settings.SSE_HEARTBEAT_INTERVAL,
                )
                data = json.loads(raw_data)

                if data.get("type") == "ping":
                    await client.send_message(WSMessageType.PONG, {
                        "timestamp": datetime.now().isoformat(),
                    })

            except asyncio.TimeoutError:
                await client.ping()

    except WebSocketDisconnect:
        logger.info(f"WebSocket智能体监控断开: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket智能体端点异常: {e}")
    finally:
        ws_manager.disconnect(client_id)
