"""
智能体相关数据模型
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime


class AgentBase(BaseModel):
    """智能体基础模型"""
    name: str = Field(..., description="智能体名称")
    description: Optional[str] = Field(None, description="智能体描述")
    category: str = Field(..., description="智能体类别")
    capabilities: List[str] = Field(default_factory=list, description="能力列表")
    config: Dict[str, Any] = Field(default_factory=dict, description="配置参数")
    is_active: bool = Field(True, description="是否激活")


class AgentCreate(AgentBase):
    """创建智能体模型"""
    pass


class AgentUpdate(BaseModel):
    """更新智能体模型"""
    name: Optional[str] = Field(None, description="智能体名称")
    description: Optional[str] = Field(None, description="智能体描述")
    category: Optional[str] = Field(None, description="智能体类别")
    capabilities: Optional[List[str]] = Field(None, description="能力列表")
    config: Optional[Dict[str, Any]] = Field(None, description="配置参数")
    is_active: Optional[bool] = Field(None, description="是否激活")


class AgentResponse(AgentBase):
    """智能体响应模型"""
    id: str = Field(..., description="智能体ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


class AgentExecutionRequest(BaseModel):
    """智能体执行请求"""
    input_data: Dict[str, Any] = Field(..., description="输入数据")
    session_id: Optional[str] = Field(None, description="会话ID")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")


class AgentExecutionResponse(BaseModel):
    """智能体执行响应"""
    status: str = Field(..., description="执行状态")
    result: Optional[Dict[str, Any]] = Field(None, description="执行结果")
    error_message: Optional[str] = Field(None, description="错误信息")
    execution_time: float = Field(..., description="执行时间（秒）")
    session_id: Optional[str] = Field(None, description="会话ID")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")