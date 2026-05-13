"""
意图节点实现
处理意图分类和路由逻辑
"""
import logging
from typing import Dict, Any
from datetime import datetime

from config.settings import settings
from intent.classifier import intent_classifier
from agents.registry import agent_registry

logger = logging.getLogger(__name__)


async def intent_classification_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    意图分类节点

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    try:
        # 获取最新用户消息
        messages = state.get("messages", [])
        if not messages:
            logger.warning("没有消息可供意图分类")
            return {"intent": None, "intent_confidence": 0.0}

        # 提取最后一条用户消息
        user_messages = [msg for msg in messages if msg.get("role") == "user"]
        if not user_messages:
            logger.warning("没有用户消息可供意图分类")
            return {"intent": None, "intent_confidence": 0.0}

        latest_user_message = user_messages[-1]
        text = latest_user_message.get("content", "")

        if not text:
            logger.warning("用户消息内容为空")
            return {"intent": None, "intent_confidence": 0.0}

        # 调用意图分类器
        classification_result = await intent_classifier.classify(
            text=text,
            session_id=state.get("session_id")
        )

        logger.info(f"意图分类结果: {classification_result}")

        return {
            "intent": classification_result.get("intent"),
            "intent_confidence": classification_result.get("confidence", 0.0),
            "metadata": {
                **state.get("metadata", {}),
                "intent_classification": classification_result,
                "classification_timestamp": datetime.now().isoformat(),
            }
        }

    except Exception as e:
        logger.error(f"意图分类节点执行失败: {e}")
        return {"intent": None, "intent_confidence": 0.0}


async def agent_routing_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    智能体路由节点

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    try:
        intent = state.get("intent")
        intent_confidence = state.get("intent_confidence", 0.0)

        if not intent or intent_confidence < settings.INTENT_CLASSIFICATION_THRESHOLD:
            # 置信度低于阈值，使用默认智能体
            selected_agent = "general_chat_agent"
            logger.info(f"意图置信度低 ({intent_confidence:.2f} < {settings.INTENT_CLASSIFICATION_THRESHOLD})，使用默认智能体: {selected_agent}")
        else:
            # 根据意图选择智能体
            agent_mapping = {
                "coding": "coding_agent",
                "research": "research_agent",
                "planning": "plan_execute_agent",
                "analysis": "react_agent",
                "general_chat": "general_chat_agent",
            }
            selected_agent = agent_mapping.get(intent, "general_chat_agent")
            logger.info(f"根据意图 '{intent}' 路由到智能体: {selected_agent}")

        # 检查智能体是否存在
        agent = agent_registry.get_agent(selected_agent)
        if not agent:
            logger.warning(f"智能体不存在: {selected_agent}，使用默认智能体")
            selected_agent = "general_chat_agent"
            agent = agent_registry.get_agent(selected_agent)

        if not agent:
            logger.error(f"默认智能体也不存在: {selected_agent}")
            raise ValueError(f"智能体 {selected_agent} 不存在")

        # 记录智能体历史
        agent_history = state.get("agent_history", [])
        agent_history.append({
            "agent_id": selected_agent,
            "intent": intent,
            "confidence": intent_confidence,
            "timestamp": datetime.now().isoformat(),
        })

        return {
            "current_agent": selected_agent,
            "agent_history": agent_history,
            "metadata": {
                **state.get("metadata", {}),
                "agent_routing": {
                    "selected_agent": selected_agent,
                    "intent": intent,
                    "confidence": intent_confidence,
                    "routing_timestamp": datetime.now().isoformat(),
                }
            }
        }

    except Exception as e:
        logger.error(f"智能体路由节点执行失败: {e}")
        # 失败时使用默认智能体
        return {
            "current_agent": "general_chat_agent",
            "agent_history": state.get("agent_history", []),
            "metadata": {
                **state.get("metadata", {}),
                "agent_routing_error": str(e),
            }
        }


async def intent_redirection_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    意图重定向节点
    处理低置信度意图的重定向逻辑

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    try:
        intent_confidence = state.get("intent_confidence", 0.0)

        # 检查是否需要重定向
        if intent_confidence >= settings.INTENT_REDIRECT_THRESHOLD:
            logger.debug(f"意图置信度足够 ({intent_confidence:.2f} >= {settings.INTENT_REDIRECT_THRESHOLD})，不需要重定向")
            return {"requires_redirect": False}

        # 低置信度意图，需要重定向
        logger.info(f"意图置信度过低 ({intent_confidence:.2f} < {settings.INTENT_REDIRECT_THRESHOLD})，触发重定向")

        # 获取候选意图
        intent = state.get("intent")
        metadata = state.get("metadata", {})
        classification_result = metadata.get("intent_classification", {})

        # 尝试获取备选意图
        alternative_intents = classification_result.get("all_predictions", [])
        if alternative_intents and len(alternative_intents) > 1:
            # 选择次优意图
            second_best = alternative_intents[1]  # 假设已按置信度排序
            redirect_intent = second_best.get("intent")
            redirect_confidence = second_best.get("confidence", 0.0)

            logger.info(f"重定向到次优意图: {redirect_intent} (置信度: {redirect_confidence:.2f})")

            return {
                "requires_redirect": True,
                "original_intent": intent,
                "original_confidence": intent_confidence,
                "redirect_intent": redirect_intent,
                "redirect_confidence": redirect_confidence,
                "metadata": {
                    **metadata,
                    "intent_redirection": {
                        "original": {"intent": intent, "confidence": intent_confidence},
                        "redirect": {"intent": redirect_intent, "confidence": redirect_confidence},
                        "redirect_timestamp": datetime.now().isoformat(),
                        "reason": f"低置信度: {intent_confidence:.2f} < {settings.INTENT_REDIRECT_THRESHOLD}",
                    }
                }
            }
        else:
            # 没有备选意图，使用默认
            logger.info("没有备选意图，重定向到默认意图")
            return {
                "requires_redirect": True,
                "original_intent": intent,
                "original_confidence": intent_confidence,
                "redirect_intent": "general_chat",
                "redirect_confidence": 1.0,
                "metadata": {
                    **metadata,
                    "intent_redirection": {
                        "original": {"intent": intent, "confidence": intent_confidence},
                        "redirect": {"intent": "general_chat", "confidence": 1.0},
                        "redirect_timestamp": datetime.now().isoformat(),
                        "reason": f"低置信度且无备选意图: {intent_confidence:.2f} < {settings.INTENT_REDIRECT_THRESHOLD}",
                    }
                }
            }

    except Exception as e:
        logger.error(f"意图重定向节点执行失败: {e}")
        return {
            "requires_redirect": False,
            "metadata": {
                **state.get("metadata", {}),
                "intent_redirection_error": str(e),
            }
        }