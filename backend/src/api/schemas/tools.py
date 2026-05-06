"""
工具相关数据模型
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class ToolCategory(str, Enum):
    """工具类别枚举"""
    CALCULATION = "calculation"
    WEB_SEARCH = "web_search"
    FILE_OPERATIONS = "file_operations"
    DATABASE = "database"
    SYSTEM = "system"
    OTHER = "other"


class ToolPermission(str, Enum):
    """工具权限枚举"""
    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    ADMIN = "admin"
    RESTRICTED = "restricted"


class ToolBase(BaseModel):
    """工具基础模型"""
    name: str = Field(..., description="工具名称")
    description: Optional[str] = Field(None, description="工具描述")
    category: ToolCategory = Field(..., description="工具类别")
    permission: ToolPermission = Field(ToolPermission.PUBLIC, description="工具权限")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="参数定义")
    is_active: bool = Field(True, description="是否激活")


class ToolCreate(ToolBase):
    """创建工具模型"""
    pass


class ToolUpdate(BaseModel):
    """更新工具模型"""
    name: Optional[str] = Field(None, description="工具名称")
    description: Optional[str] = Field(None, description="工具描述")
    category: Optional[ToolCategory] = Field(None, description="工具类别")
    permission: Optional[ToolPermission] = Field(None, description="工具权限")
    parameters: Optional[Dict[str, Any]] = Field(None, description="参数定义")
    is_active: Optional[bool] = Field(None, description="是否激活")


class ToolResponse(ToolBase):
    """工具响应模型"""
    id: str = Field(..., description="工具ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


class ToolExecutionRequest(BaseModel):
    """工具执行请求"""
    tool_input: Dict[str, Any] = Field(..., description="工具输入")
    session_id: Optional[str] = Field(None, description="会话ID")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")


class ToolExecutionResponse(BaseModel):
    """工具执行响应"""
    status: str = Field(..., description="执行状态")
    result: Optional[Dict[str, Any]] = Field(None, description="执行结果")
    error_message: Optional[str] = Field(None, description="错误信息")
    execution_time: float = Field(..., description="执行时间（秒）")
    session_id: Optional[str] = Field(None, description="会话ID")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")


class ToolStatistics(BaseModel):
    """工具统计信息"""
    total_executions: int = Field(0, description="总执行次数")
    successful_executions: int = Field(0, description="成功执行次数")
    failed_executions: int = Field(0, description="失败执行次数")
    average_execution_time: float = Field(0.0, description="平均执行时间")
    last_execution_time: Optional[datetime] = Field(None, description="最后执行时间")