"""
意图管理API路由
"""
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/categories")
async def list_intent_categories(
    parent_id: Optional[str] = Query(None, description="父类别ID"),
    active_only: bool = Query(True, description="只返回激活的类别"),
) -> List[Dict[str, Any]]:
    """
    获取意图类别列表

    Args:
        parent_id: 父类别ID
        active_only: 是否只返回激活的类别

    Returns:
        意图类别列表
    """
    try:
        from memory.long_term.sql_store import SQLStore
        from models.database import async_session

        # TODO: 从数据库获取意图类别
        # 暂时返回空列表
        return []

    except Exception as e:
        logger.error(f"获取意图类别列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取意图类别列表失败")


@router.post("/classify")
async def classify_intent(
    text: str = Body(..., description="待分类文本"),
    session_id: Optional[str] = Body(None, description="会话ID"),
) -> Dict[str, Any]:
    """
    意图分类

    Args:
        text: 待分类文本
        session_id: 会话ID

    Returns:
        分类结果
    """
    try:
        from intent.classifier import intent_classifier

        # TODO: 调用意图分类器
        # 暂时返回占位响应
        return {
            "status": "success",
            "intent": "general_chat",
            "confidence": 0.95,
            "text": text,
            "session_id": session_id,
        }

    except Exception as e:
        logger.error(f"意图分类失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="意图分类失败")


@router.get("/thresholds")
async def get_intent_thresholds() -> Dict[str, Any]:
    """
    获取意图识别阈值配置

    Returns:
        阈值配置
    """
    try:
        from config.settings import settings

        return {
            "classification_threshold": settings.INTENT_CLASSIFICATION_THRESHOLD,
            "redirect_threshold": settings.INTENT_REDIRECT_THRESHOLD,
        }
    except Exception as e:
        logger.error(f"获取阈值配置失败: {e}")
        raise HTTPException(status_code=500, detail="获取阈值配置失败")