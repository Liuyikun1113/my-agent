"""
会话管理API路由
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body

from api.schemas.session import (
    SessionCreate,
    SessionUpdate,
    SessionResponse,
    SessionStats,
    PaginatedSessions,
)
from api.middleware.auth import get_current_user_optional
from memory.manager import memory_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=SessionResponse)
async def create_session(
    session_create: SessionCreate = Body(...),
    user_id: Optional[str] = Depends(get_current_user_optional),
) -> SessionResponse:
    """
    创建新会话

    Args:
        session_create: 会话创建数据
        user_id: 当前用户ID（从JWT解析，可选）

    Returns:
        SessionResponse: 创建的会话
    """
    try:
        # 使用请求中携带的 user_id，或 schema 中显式传入的
        effective_user_id = user_id or session_create.user_id

        # 创建会话
        session = await memory_manager.create_session(
            title=session_create.title,
            description=session_create.description,
            metadata=session_create.metadata,
            user_id=effective_user_id,
        )

        return session

    except Exception as e:
        logger.error(f"创建会话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="创建会话失败")


@router.get("/", response_model=PaginatedSessions)
async def list_sessions(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="按状态过滤"),
    title: Optional[str] = Query(None, description="按标题搜索"),
    user_id: Optional[str] = Depends(get_current_user_optional),
) -> PaginatedSessions:
    """
    获取会话列表（分页）

    Args:
        page: 页码
        page_size: 每页数量
        status: 状态过滤
        title: 标题搜索
        user_id: 当前用户ID（从JWT解析）

    Returns:
        PaginatedSessions: 分页会话列表
    """
    try:
        sessions, total = await memory_manager.get_sessions(
            page=page,
            page_size=page_size,
            status=status,
            title=title,
            user_id=user_id,
        )

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        return PaginatedSessions(
            items=sessions,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except Exception as e:
        logger.error(f"获取会话列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取会话列表失败")


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str) -> SessionResponse:
    """
    获取指定会话

    Args:
        session_id: 会话ID

    Returns:
        SessionResponse: 会话详情
    """
    try:
        session = await memory_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")

        # 获取消息数量
        message_count = await memory_manager.get_session_message_count(session_id)

        # 获取最后消息时间
        last_message = await memory_manager.get_last_session_message(session_id)
        last_message_at = last_message.created_at if last_message else None

        # 更新响应中的统计信息
        session.message_count = message_count
        session.last_message_at = last_message_at

        return session

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取会话失败")


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    session_update: SessionUpdate,
) -> SessionResponse:
    """
    更新会话信息

    Args:
        session_id: 会话ID
        session_update: 会话更新数据

    Returns:
        SessionResponse: 更新后的会话
    """
    try:
        # 验证会话存在
        session = await memory_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")

        # 验证状态值（如果提供）
        if session_update.status and session_update.status not in [
            "active", "paused", "completed", "archived"
        ]:
            raise HTTPException(
                status_code=400,
                detail=f"无效的状态值: {session_update.status}。可选值: active, paused, completed, archived"
            )

        # 更新会话
        updated_session = await memory_manager.update_session(
            session_id=session_id,
            title=session_update.title,
            description=session_update.description,
            status=session_update.status,
            metadata=session_update.metadata,
        )

        return updated_session

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新会话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="更新会话失败")


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """
    删除会话（软删除）

    Args:
        session_id: 会话ID
    """
    try:
        # 验证会话存在
        session = await memory_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")

        # 软删除：将会话状态标记为archived
        await memory_manager.update_session(
            session_id=session_id,
            status="archived",
        )

        return {"message": "会话已归档"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除会话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="删除会话失败")


@router.get("/{session_id}/stats", response_model=SessionStats)
async def get_session_stats(session_id: str) -> SessionStats:
    """
    获取会话统计信息

    Args:
        session_id: 会话ID

    Returns:
        SessionStats: 会话统计
    """
    try:
        # 验证会话存在
        session = await memory_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")

        # 获取会话消息数量
        message_count = await memory_manager.get_session_message_count(session_id)

        # 这里可以添加更多统计信息
        # 暂时返回基本统计

        return SessionStats(
            total_sessions=1,
            active_sessions=1 if session.status == "active" else 0,
            total_messages=message_count,
            average_messages_per_session=message_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取会话统计失败")


@router.get("/stats/overall", response_model=SessionStats)
async def get_overall_stats() -> SessionStats:
    """
    获取整体统计信息

    Returns:
        SessionStats: 整体统计
    """
    try:
        # 获取所有会话
        all_sessions, total_sessions = await memory_manager.get_sessions(
            page=1,
            page_size=1000,  # 获取足够多的会话
        )

        # 计算活跃会话数量
        active_sessions = len([s for s in all_sessions if s.status == "active"])

        # 计算总消息数
        total_messages = 0
        for session in all_sessions:
            message_count = await memory_manager.get_session_message_count(session.id)
            total_messages += message_count

        # 计算平均消息数
        average_messages = total_messages / total_sessions if total_sessions > 0 else 0

        return SessionStats(
            total_sessions=total_sessions,
            active_sessions=active_sessions,
            total_messages=total_messages,
            average_messages_per_session=average_messages,
        )

    except Exception as e:
        logger.error(f"获取整体统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取整体统计失败")