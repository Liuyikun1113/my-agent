from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class MessageBase(BaseModel):
    """消息基础模型"""
    content: Optional[str] = Field(None, description="消息内容")
    role: str = Field(..., description="消息角色", pattern="^(user|assistant|system|tool)$")
    metadata: Optional[Dict[str, Any]] = Field(None, description="消息元数据")


class MessageCreate(MessageBase):
    """创建消息请求模型"""
    session_id: str = Field(..., description="会话ID")
    parent_message_id: Optional[str] = Field(None, description="父消息ID")


class MessageUpdate(BaseModel):
    """更新消息请求模型"""
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    intent: Optional[str] = None
    intent_confidence: Optional[float] = None
    processing_status: Optional[str] = Field(None, pattern="^(pending|processing|completed|failed)$")
    error_message: Optional[str] = None


class MessageResponse(BaseModel):
    """消息响应模型"""
    id: str
    session_id: str
    role: str
    content: Optional[str]
    tool_calls: Optional[List[Dict[str, Any]]]
    tool_results: Optional[List[Dict[str, Any]]]
    created_at: datetime
    parent_message_id: Optional[str]
    metadata: Optional[Dict[str, Any]]
    intent: Optional[str]
    intent_confidence: Optional[float]
    processing_status: str
    error_message: Optional[str]

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    """聊天请求模型"""
    message: str = Field(..., description="用户消息")
    stream: bool = Field(False, description="是否使用流式响应")


class ChatResponse(BaseModel):
    """聊天响应模型"""
    message: MessageResponse
    is_streaming: bool = False
    stream_token: Optional[str] = None


class PaginatedMessages(BaseModel):
    """分页消息响应模型"""
    items: List[MessageResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ToolCallRequest(BaseModel):
    """工具调用请求模型"""
    tool_name: str = Field(..., description="工具名称")
    tool_input: Dict[str, Any] = Field(..., description="工具输入")


class ToolCallResponse(BaseModel):
    """工具调用响应模型"""
    tool_call_id: str
    tool_name: str
    result: Any
    is_error: bool = False
    error_message: Optional[str] = None