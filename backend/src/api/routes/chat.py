"""
聊天相关API路由
"""
import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse

from api.schemas.chat import (
    MessageCreate,
    MessageResponse,
    ChatRequest,
    ChatResponse,
    PaginatedMessages,
    ToolCallRequest,
    ToolCallResponse,
)
from api.middleware.auth import get_current_user_optional
from memory.manager import memory_manager
from agents.registry import agent_registry
from tools.registry import tool_registry
from sse.sse_manager import sse_manager, EventType
from utils.validation import validate_session_id, sanitize_input
from utils.helpers import truncate_text

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

        # 如果是流式响应，通过后台任务处理并返回
        if chat_request.stream:
            background_tasks.add_task(
                process_user_message,
                session_id=session_id,
                message_id=user_message.id,
            )
            return ChatResponse(
                message=user_message,
                is_streaming=True,
                stream_token=f"stream_{session_id}_{user_message.id}",
            )

        # 同步处理：调用智能体协调器处理消息
        from backend.src.agents.orchestrator import agent_orchestrator
        agent, route_info = await agent_orchestrator.route_to_agent(
            session_id=session_id,
            message_content=cleaned_message,
        )
        if agent:
            result = await agent.process_message(
                session_id=session_id,
                message_id=user_message.id,
                message_content=cleaned_message,
            )
            response_content = result.get("response", str(result))
        else:
            response_content = "抱歉，当前没有可用的智能体来处理您的请求。"

        assistant_message = await memory_manager.save_message(
            session_id=session_id,
            role="assistant",
            content=response_content,
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
        from backend.src.intent.classifier import intent_classifier
        try:
            intent_result = await intent_classifier.classify(message.content)
            intent = intent_result.intent
            confidence = intent_result.confidence
        except Exception as e:
            logger.warning(f"意图识别失败: {e}, 使用默认意图")
            intent = "general_chat"
            confidence = 0.5

        # 发送意图识别事件
        await sse_manager.send_to_session(
            session_id=session_id,
            event_type=EventType.INTENT_UPDATE,
            data={
                "session_id": session_id,
                "message_id": message_id,
                "intent": intent,
                "confidence": confidence,
            },
            event_id=f"intent_{message_id}",
        )

        # 2. 路由到对应智能体并流式获取响应
        from backend.src.agents.orchestrator import agent_orchestrator
        agent, route_info = await agent_orchestrator.route_to_agent(
            session_id=session_id,
            message_content=message.content,
            intent=intent,
        )

        if not agent:
            response_content = "抱歉，当前没有可用的智能体来处理您的请求。"
            assistant_message = await memory_manager.save_message(
                session_id=session_id,
                role="assistant",
                content=response_content,
                parent_message_id=message_id,
            )
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
            return

        # 流式消费 Agent 输出
        full_content = ""
        metadata = {}
        async for chunk in agent.stream_response(
            session_id=session_id,
            message_id=message_id,
            message_content=message.content,
        ):
            delta = chunk.get("delta", "")
            full_content += delta

            if chunk.get("done"):
                full_response = chunk.get("full_response", full_content)
                metadata = chunk.get("metadata", {})

                assistant_message = await memory_manager.save_message(
                    session_id=session_id,
                    role="assistant",
                    content=full_response,
                    parent_message_id=message_id,
                )
                await sse_manager.send_to_session(
                    session_id=session_id,
                    event_type=EventType.CHAT_MESSAGE,
                    data={
                        "session_id": session_id,
                        "message": {
                            "id": assistant_message.id,
                            "role": "assistant",
                            "content": full_response,
                            "timestamp": assistant_message.created_at.isoformat() if hasattr(assistant_message, 'created_at') else datetime.now().isoformat(),
                            "parent_message_id": message_id,
                            "metadata": metadata.get("metadata"),
                        }
                    },
                    event_id=f"message_{assistant_message.id}",
                )
            else:
                await sse_manager.send_to_session(
                    session_id=session_id,
                    event_type=EventType.CHAT_DELTA,
                    data={
                        "session_id": session_id,
                        "message_id": message_id,
                        "delta": delta,
                        "is_streaming": True,
                    },
                )

        logger.info(f"用户消息处理完成: session={session_id}, message={message_id}")

    except Exception as e:
        logger.error(f"处理用户消息失败: {e}", exc_info=True)