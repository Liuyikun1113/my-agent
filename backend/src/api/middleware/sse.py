"""
Server-Sent Events (SSE) 中间件和路由
提供实时事件流功能，支持连接管理、心跳检测、事件广播
"""
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from config.settings import settings
from sse.sse_manager import sse_manager, EventType, SSEClient

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/connect")
async def sse_connect(
    request: Request,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    subscriptions: Optional[str] = None,
    metadata: Optional[str] = None,
) -> EventSourceResponse:
    """
    建立SSE连接

    Args:
        request: FastAPI请求对象
        user_id: 用户ID（可选）
        session_id: 会话ID（可选）
        subscriptions: 订阅的事件类型，逗号分隔，例如 "CHAT_MESSAGE,TOOL_RESULT,AGENT_STATUS"
        metadata: 客户端元数据，JSON格式字符串

    Returns:
        EventSourceResponse: SSE事件流响应
    """
    try:
        # 解析订阅列表
        subscription_list = set()
        if subscriptions:
            for event_name in subscriptions.split(","):
                event_name = event_name.strip().upper()
                try:
                    event_type = EventType[event_name]
                    subscription_list.add(event_type)
                except KeyError:
                    logger.warning(f"未知的事件类型: {event_name}")

        # 解析元数据
        metadata_dict = {}
        if metadata:
            try:
                metadata_dict = json.loads(metadata)
            except json.JSONDecodeError:
                logger.warning(f"无效的元数据JSON: {metadata}")

        # 创建SSE客户端
        client = await sse_manager.create_client(
            user_id=user_id,
            session_id=session_id,
            metadata=metadata_dict,
        )

        # 设置自定义订阅（如果提供）
        if subscription_list:
            # 先清除默认订阅
            client.subscriptions.clear()
            # 添加自定义订阅
            for event_type in subscription_list:
                client.subscribe(event_type)
            logger.info(f"客户端 {client.client_id} 设置了自定义订阅: {subscription_list}")

        # 定义SSE事件生成器
        async def event_generator():
            try:
                async for event in client.event_generator():
                    yield event
            except Exception as e:
                logger.error(f"SSE事件生成器异常: {e}")
                # 确保客户端被清理
                await sse_manager.disconnect_client(client.client_id)
                raise

        # 返回SSE响应
        return EventSourceResponse(
            event_generator(),
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
                "X-Accel-Buffering": "no",  # 禁用Nginx缓冲
            },
            ping_message={"event": "ping", "data": {"timestamp": datetime.now().isoformat()}},
            ping_interval=settings.SSE_HEARTBEAT_INTERVAL,
        )

    except Exception as e:
        logger.error(f"SSE连接建立失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="SSE连接建立失败")


@router.post("/disconnect")
async def sse_disconnect(client_id: str) -> Dict[str, Any]:
    """
    主动断开SSE连接

    Args:
        client_id: 客户端ID

    Returns:
        断开连接结果
    """
    try:
        await sse_manager.disconnect_client(client_id)
        return {
            "status": "success",
            "message": f"SSE客户端 {client_id} 已断开连接",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"SSE断开连接失败: {e}")
        raise HTTPException(status_code=500, detail=f"断开连接失败: {e}")


@router.get("/stats")
async def sse_stats() -> Dict[str, Any]:
    """
    获取SSE连接统计信息

    Returns:
        SSE连接统计
    """
    try:
        stats = sse_manager.get_client_stats()
        return stats
    except Exception as e:
        logger.error(f"获取SSE统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计失败: {e}")


@router.post("/broadcast")
async def sse_broadcast(
    event_type: str,
    data: Dict[str, Any],
    event_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    广播事件到所有符合条件的客户端

    Args:
        event_type: 事件类型，例如 "CHAT_MESSAGE"
        data: 事件数据
        event_id: 事件ID（可选）

    Returns:
        广播结果
    """
    try:
        # 解析事件类型
        try:
            event_type_enum = EventType[event_type.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"未知的事件类型: {event_type}")

        # 广播事件
        sent_count = await sse_manager.broadcast_event(
            event_type=event_type_enum,
            data=data,
            event_id=event_id,
        )

        return {
            "status": "success",
            "message": f"事件已广播到 {sent_count} 个客户端",
            "event_type": event_type,
            "sent_count": sent_count,
            "timestamp": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"事件广播失败: {e}")
        raise HTTPException(status_code=500, detail=f"事件广播失败: {e}")


@router.post("/send-to-client")
async def sse_send_to_client(
    client_id: str,
    event_type: str,
    data: Dict[str, Any],
    event_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    发送事件到指定客户端

    Args:
        client_id: 客户端ID
        event_type: 事件类型
        data: 事件数据
        event_id: 事件ID（可选）

    Returns:
        发送结果
    """
    try:
        # 解析事件类型
        try:
            event_type_enum = EventType[event_type.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"未知的事件类型: {event_type}")

        # 发送事件
        success = await sse_manager.send_to_client(
            client_id=client_id,
            event_type=event_type_enum,
            data=data,
            event_id=event_id,
        )

        if success:
            return {
                "status": "success",
                "message": f"事件已发送到客户端 {client_id}",
                "event_type": event_type,
                "timestamp": datetime.now().isoformat(),
            }
        else:
            return {
                "status": "error",
                "message": f"发送事件到客户端 {client_id} 失败",
                "event_type": event_type,
                "timestamp": datetime.now().isoformat(),
            }
    except Exception as e:
        logger.error(f"发送事件到客户端失败: {e}")
        raise HTTPException(status_code=500, detail=f"发送事件失败: {e}")


@router.post("/send-to-user")
async def sse_send_to_user(
    user_id: str,
    event_type: str,
    data: Dict[str, Any],
    event_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    发送事件到指定用户的所有客户端

    Args:
        user_id: 用户ID
        event_type: 事件类型
        data: 事件数据
        event_id: 事件ID（可选）

    Returns:
        发送结果
    """
    try:
        # 解析事件类型
        try:
            event_type_enum = EventType[event_type.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"未知的事件类型: {event_type}")

        # 发送事件
        sent_count = await sse_manager.send_to_user(
            user_id=user_id,
            event_type=event_type_enum,
            data=data,
            event_id=event_id,
        )

        return {
            "status": "success",
            "message": f"事件已发送到用户 {user_id} 的 {sent_count} 个客户端",
            "event_type": event_type,
            "sent_count": sent_count,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"发送事件到用户失败: {e}")
        raise HTTPException(status_code=500, detail=f"发送事件失败: {e}")


@router.post("/send-to-session")
async def sse_send_to_session(
    session_id: str,
    event_type: str,
    data: Dict[str, Any],
    event_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    发送事件到指定会话的所有客户端

    Args:
        session_id: 会话ID
        event_type: 事件类型
        data: 事件数据
        event_id: 事件ID（可选）

    Returns:
        发送结果
    """
    try:
        # 解析事件类型
        try:
            event_type_enum = EventType[event_type.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"未知的事件类型: {event_type}")

        # 发送事件
        sent_count = await sse_manager.send_to_session(
            session_id=session_id,
            event_type=event_type_enum,
            data=data,
            event_id=event_id,
        )

        return {
            "status": "success",
            "message": f"事件已发送到会话 {session_id} 的 {sent_count} 个客户端",
            "event_type": event_type,
            "sent_count": sent_count,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"发送事件到会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"发送事件失败: {e}")


# SSE中间件依赖注入
async def get_sse_client(client_id: str) -> Optional[SSEClient]:
    """
    获取SSE客户端依赖

    Args:
        client_id: 客户端ID

    Returns:
        SSEClient对象或None
    """
    return sse_manager.get_client(client_id)


# 注册到主应用的sse_router变量
sse_router = router