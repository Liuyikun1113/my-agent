"""
聊天相关API路由
"""
import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse

from backend.src.api.schemas.chat import (
    MessageCreate,
    MessageResponse,
    ChatRequest,
    ChatResponse,
    PaginatedMessages,
    ToolCallRequest,
    ToolCallResponse,
)
from backend.src.api.middleware.auth import get_current_user_optional
from backend.src.memory.manager import memory_manager
from backend.src.agents.registry import agent_registry
from backend.src.tools.registry import tool_registry
from backend.src.sse.sse_manager import sse_manager, EventType
from backend.src.utils.validation import validate_session_id, sanitize_input
from backend.src.utils.helpers import truncate_text

logger = logging.getLogger(__name__)
router = APIRouter()


async def verify_session_access(session_id: str, user_id: Optional[str]):
    session = await memory_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.user_id and session.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权访问此会话")
    return session


@router.post("/{session_id}/messages", response_model=MessageResponse)
async def create_message(
    session_id: str,
    message: MessageCreate,
    background_tasks: BackgroundTasks,
    user_id: Optional[str] = Depends(get_current_user_optional),
) -> MessageResponse:
    """
    创建新消息

    Args:
        session_id: 会话ID
        message: 消息数据
        background_tasks: 后台任务管理器

    Returns:
        MessageResponse: 创建的消息
    """
    try:
        if not validate_session_id(session_id):
            raise HTTPException(status_code=400, detail="无效的会话ID格式")
        session = await verify_session_access(session_id, user_id)

        # 验证父消息（如果提供）
        if message.parent_message_id:
            parent_message = await memory_manager.get_message(message.parent_message_id)
            if not parent_message or parent_message.session_id != session_id:
                raise HTTPException(status_code=400, detail="父消息不存在或不属于当前会话")

        # 保存消息到数据库
        saved_message = await memory_manager.save_message(
            session_id=session_id,
            role=message.role,
            content=message.content,
            parent_message_id=message.parent_message_id,
            metadata=message.metadata,
        )

        # 如果是用户消息，触发意图识别和智能体处理
        if message.role == "user":
            background_tasks.add_task(
                process_user_message,
                session_id=session_id,
                message_id=saved_message.id,
            )

        return saved_message

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建消息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="创建消息失败")


@router.get("/{session_id}/messages", response_model=PaginatedMessages)
async def get_messages(
    session_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    role: Optional[str] = Query(None, description="按角色过滤"),
    parent_message_id: Optional[str] = Query(None, description="父消息ID"),
    user_id: Optional[str] = Depends(get_current_user_optional),
) -> PaginatedMessages:
    """
    获取会话消息列表（分页）

    Args:
        session_id: 会话ID
        page: 页码
        page_size: 每页数量
        role: 角色过滤
        parent_message_id: 父消息ID过滤

    Returns:
        PaginatedMessages: 分页消息列表
    """
    try:
        if not validate_session_id(session_id):
            raise HTTPException(status_code=400, detail="无效的会话ID格式")
        session = await verify_session_access(session_id, user_id)

        # 获取消息
        messages, total = await memory_manager.get_messages(
            session_id=session_id,
            page=page,
            page_size=page_size,
            role=role,
            parent_message_id=parent_message_id,
        )

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        return PaginatedMessages(
            items=messages,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取消息列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取消息列表失败")


@router.get("/messages/{message_id}", response_model=MessageResponse)
async def get_message(message_id: str) -> MessageResponse:
    """
    获取指定消息

    Args:
        message_id: 消息ID

    Returns:
        MessageResponse: 消息详情
    """
    try:
        message = await memory_manager.get_message(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="消息不存在")

        return message

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取消息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取消息失败")


@router.post("/{session_id}", response_model=ChatResponse)
async def chat(
    session_id: str,
    chat_request: ChatRequest,
    background_tasks: BackgroundTasks,
    user_id: Optional[str] = Depends(get_current_user_optional),
) -> ChatResponse:
    """
    聊天接口（同步响应）

    Args:
        session_id: 会话ID
        chat_request: 聊天请求
        background_tasks: 后台任务管理器

    Returns:
        ChatResponse: 聊天响应
    """
    try:
        if not validate_session_id(session_id):
            raise HTTPException(status_code=400, detail="无效的会话ID格式")
        session = await verify_session_access(session_id, user_id)

        # 清洗用户输入
        cleaned_message, warnings = sanitize_input(chat_request.message)
        if warnings:
            logger.warning(f"消息清洗警告: {warnings} | 原文: {truncate_text(chat_request.message, 100)}")

        # 创建用户消息
        user_message = await memory_manager.save_message(
            session_id=session_id,
            role="user",
            content=cleaned_message,
        )

        # 如果是流式响应，返回流式响应
        if chat_request.stream:
            return ChatResponse(
                message=user_message,
                is_streaming=True,
                stream_token=f"stream_{session_id}_{user_message.id}",
            )

        # 同步处理：获取智能体响应
        # 这里应该调用智能体协调器处理消息
        # 暂时返回一个占位响应
        assistant_message = await memory_manager.save_message(
            session_id=session_id,
            role="assistant",
            content="这是一个占位响应，智能体功能待实现",
            parent_message_id=user_message.id,
        )

        return ChatResponse(message=assistant_message)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"聊天处理失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="聊天处理失败")


@router.post("/tool-call", response_model=ToolCallResponse)
async def call_tool(
    tool_request: ToolCallRequest,
) -> ToolCallResponse:
    """
    直接调用工具

    Args:
        tool_request: 工具调用请求

    Returns:
        ToolCallResponse: 工具调用结果
    """
    try:
        # 获取工具
        tool = tool_registry.get_tool(tool_request.tool_name)
        if not tool:
            raise HTTPException(status_code=404, detail="工具不存在")

        # 调用工具
        result = await tool.execute(tool_request.tool_input)

        return ToolCallResponse(
            tool_call_id=f"call_{tool_request.tool_name}",
            tool_name=tool_request.tool_name,
            result=result,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"工具调用失败: {e}", exc_info=True)
        return ToolCallResponse(
            tool_call_id=f"call_{tool_request.tool_name}",
            tool_name=tool_request.tool_name,
            result=None,
            is_error=True,
            error_message=str(e),
        )


# 后台任务函数
async def process_user_message(session_id: str, message_id: str):
    """
    处理用户消息的后台任务

    Args:
        session_id: 会话ID
        message_id: 消息ID
    """
    try:
        logger.info(f"开始处理用户消息: session={session_id}, message={message_id}")

        # 获取消息
        message = await memory_manager.get_message(message_id)
        if not message or message.session_id != session_id:
            logger.error(f"消息不存在或不属于当前会话: {message_id}")
            return

        # 1. 意图识别
        # TODO: 调用意图分类器
        # 暂时使用简单逻辑
        intent = "general_chat"

        # 发送意图识别事件
        await sse_manager.send_to_session(
            session_id=session_id,
            event_type=EventType.INTENT_UPDATE,
            data={
                "session_id": session_id,
                "message_id": message_id,
                "intent": intent,
                "confidence": 1.0,
            },
            event_id=f"intent_{message_id}",
        )

        # 2. 路由到对应智能体
        # TODO: 根据意图路由到相应智能体
        # 暂时使用通用智能体

        # 3. 获取智能体响应
        # TODO: 调用智能体处理消息
        # 暂时生成模拟响应
        response_content = f"这是对您消息的模拟响应: '{message.content[:50]}...'"

        # 4. 保存智能体响应
        assistant_message = await memory_manager.save_message(
            session_id=session_id,
            role="assistant",
            content=response_content,
            parent_message_id=message_id,
        )

        # 5. 通过SSE推送响应到会话
        await sse_manager.send_to_session(
            session_id=session_id,
            event_type=EventType.CHAT_MESSAGE,
            data={
                "session_id": session_id,
                "message": {
                    "id": assistant_message.id,
                    "role": "assistant",
                    "content": response_content,
                    "timestamp": assistant_message.created_at.isoformat() if hasattr(assistant_message, 'created_at') else datetime.now().isoformat(),
                    "parent_message_id": message_id,
                }
            },
            event_id=f"message_{assistant_message.id}",
        )

        logger.info(f"用户消息处理完成: session={session_id}, message={message_id}")

    except Exception as e:
        logger.error(f"处理用户消息失败: {e}", exc_info=True)