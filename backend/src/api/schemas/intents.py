"""
意图相关数据模型
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime


class IntentCategoryBase(BaseModel):
    """意图类别基础模型"""
    name: str = Field(..., description="类别名称")
    description: Optional[str] = Field(None, description="类别描述")
    parent_id: Optional[str] = Field(None, description="父类别ID")
    threshold: float = Field(0.7, ge=0.0, le=1.0, description="分类阈值")
    redirect_threshold: float = Field(0.3, ge=0.0, le=1.0, description="重定向阈值")
    is_active: bool = Field(True, description="是否激活")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


class IntentCategoryCreate(IntentCategoryBase):
    """创建意图类别模型"""
    pass


class IntentCategoryUpdate(BaseModel):
    """更新意图类别模型"""
    name: Optional[str] = Field(None, description="类别名称")
    description: Optional[str] = Field(None, description="类别描述")
    parent_id: Optional[str] = Field(None, description="父类别ID")
    threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="分类阈值")
    redirect_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="重定向阈值")
    is_active: Optional[bool] = Field(None, description="是否激活")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class IntentCategoryResponse(IntentCategoryBase):
    """意图类别响应模型"""
    id: str = Field(..., description="类别ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


class IntentClassificationRequest(BaseModel):
    """意图分类请求"""
    text: str = Field(..., description="待分类文本")
    session_id: Optional[str] = Field(None, description="会话ID")
    include_categories: Optional[List[str]] = Field(None, description="包含的类别列表")


class IntentClassificationResponse(BaseModel):
    """意图分类响应"""
    text: str = Field(..., description="原始文本")
    primary_intent: str = Field(..., description="主要意图")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度")
    session_id: Optional[str] = Field(None, description="会话ID")
    all_predictions: List[Dict[str, Any]] = Field(default_factory=list, description="所有预测结果")
    is_redirect: bool = Field(False, description="是否需要重定向")
    redirect_intent: Optional[str] = Field(None, description="重定向意图")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")


class IntentThresholds(BaseModel):
    """意图阈值配置"""
    classification_threshold: float = Field(0.7, ge=0.0, le=1.0, description="分类阈值")
    redirect_threshold: float = Field(0.3, ge=0.0, le=1.0, description="重定向阈值")
    min_confidence: float = Field(0.1, ge=0.0, le=1.0, description="最小置信度")
    max_alternative_predictions: int = Field(3, ge=1, le=10, description="最大备选预测数")