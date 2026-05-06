from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class SessionBase(BaseModel):
    """会话基础模型"""
    title: Optional[str] = Field(None, max_length=255, description="会话标题")
    description: Optional[str] = Field(None, description="会话描述")
    metadata: Optional[Dict[str, Any]] = Field(None, description="会话元数据")


class SessionCreate(SessionBase):
    """创建会话请求模型"""
    user_id: Optional[str] = Field(None, description="用户ID，不传则创建匿名会话")


class SessionUpdate(BaseModel):
    """更新会话请求模型"""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(active|paused|completed|archived)$")
    metadata: Optional[Dict[str, Any]] = None


class SessionResponse(BaseModel):
    """会话响应模型"""
    id: str
    user_id: Optional[str] = None
    title: Optional[str]
    description: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]]
    message_count: int = 0
    last_message_at: Optional[datetime]

    class Config:
        from_attributes = True


class SessionStats(BaseModel):
    """会话统计模型"""
    total_sessions: int
    active_sessions: int
    total_messages: int
    average_messages_per_session: float


class PaginatedSessions(BaseModel):
    """分页会话响应模型"""
    items: List[SessionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int