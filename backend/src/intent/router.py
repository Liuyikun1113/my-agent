"""
意图路由器
根据意图分类结果和置信度将请求路由到合适的智能体
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from .classifier import IntentResult, IntentCategory
from backend.src.config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class RouteDecision:
    """路由决策"""
    intent: str
    confidence: float
    selected_agent: str
    requires_redirect: bool
    redirect_intent: Optional[str] = None
    redirect_confidence: Optional[float] = None
    alternative_agents: List[str] = field(default_factory=list)
    reason: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class IntentRouter:
    """
    意图路由器
    负责将意图分类结果映射到具体的智能体，处理重定向逻辑
    """

    # 意图到智能体的映射表
    DEFAULT_AGENT_MAPPING = {
        "general_chat": "general_chat_agent",
        "coding": "coding_agent",
        "research": "research_agent",
        "planning": "plan_execute_agent",
        "analysis": "react_agent",
        "tool_usage": "general_chat_agent",
    }

    # 智能体负载均衡计数器
    _load_counter: Dict[str, int] = {}

    def __init__(self):
        self._initialized = False
        self._routing_history: List[RouteDecision] = []
        self._max_history = 1000

    async def initialize(self):
        """初始化路由器"""
        if self._initialized:
            return
        self._initialized = True
        logger.info("意图路由器初始化完成")

    def route(
        self,
        intent_result: IntentResult,
        context: Optional[Dict[str, Any]] = None,
    ) -> RouteDecision:
        """
        根据意图结果做出路由决策

        Args:
            intent_result: 意图分类结果
            context: 上下文信息

        Returns:
            RouteDecision: 路由决策
        """
        intent = intent_result.intent
        confidence = intent_result.confidence
        context = context or {}

        # 检查是否需要重定向
        requires_redirect = self._should_redirect(intent_result)
        redirect_intent = None
        redirect_confidence = None

        if requires_redirect:
            redirect_intent, redirect_confidence = self._determine_redirect(intent_result)

        # 选择目标智能体
        target_intent = redirect_intent if requires_redirect else intent
        selected_agent = self._select_agent(target_intent, confidence, context)

        # 查找备选智能体
        alternative_agents = self._find_alternatives(target_intent, selected_agent)

        decision = RouteDecision(
            intent=intent,
            confidence=confidence,
            selected_agent=selected_agent,
            requires_redirect=requires_redirect,
            redirect_intent=redirect_intent,
            redirect_confidence=redirect_confidence,
            alternative_agents=alternative_agents,
            reason=self._build_reason(intent, confidence, requires_redirect, selected_agent),
        )

        self._record_decision(decision)
        self._update_load(selected_agent)

        logger.info(
            f"路由决策: intent={intent}, confidence={confidence:.2f}, "
            f"redirect={requires_redirect}, agent={selected_agent}"
        )

        return decision

    def _should_redirect(self, intent_result: IntentResult) -> bool:
        """
        判断是否需要重定向

        Args:
            intent_result: 意图分类结果

        Returns:
            是否需要重定向
        """
        intent = intent_result.intent

        if intent == "unknown":
            return True

        if intent_result.confidence < settings.INTENT_REDIRECT_THRESHOLD:
            return True

        redirect_marker = intent_result.metadata.get("should_redirect", False)
        if redirect_marker:
            return True

        return False

    def _determine_redirect(self, intent_result: IntentResult) -> Tuple[str, float]:
        """
        确定重定向目标意图

        Args:
            intent_result: 意图分类结果

        Returns:
            (redirect_intent, redirect_confidence)
        """
        # 首先检查是否有备选预测
        all_predictions = intent_result.metadata.get("all_predictions", [])
        if all_predictions and len(all_predictions) > 1:
            second_best = all_predictions[1]
            if isinstance(second_best, dict):
                return second_best.get("intent", "general_chat"), second_best.get("confidence", 0.5)

        # 次优意图推断
        intent = intent_result.intent
        redirect_map = {
            "coding": ("general_chat", 0.6),
            "research": ("general_chat", 0.6),
            "planning": ("general_chat", 0.5),
            "analysis": ("research", 0.5),
            "tool_usage": ("general_chat", 0.7),
        }

        return redirect_map.get(intent, ("general_chat", 0.5))

    def _select_agent(
        self, intent: str, confidence: float, context: Dict[str, Any]
    ) -> str:
        """
        选择合适的智能体

        Args:
            intent: 意图
            confidence: 置信度
            context: 上下文

        Returns:
            选中的智能体ID
        """
        # 上下文指定的智能体优先
        context_agent = context.get("preferred_agent")
        if context_agent:
            return context_agent

        # 使用映射表
        agent_id = self.DEFAULT_AGENT_MAPPING.get(intent, "general_chat_agent")

        # 负载均衡：如果主智能体负载高，尝试使用备选
        if self._get_load(agent_id) > 10:
            alternatives = self._find_alternatives(intent, agent_id)
            if alternatives:
                least_loaded = min(alternatives, key=lambda a: self._get_load(a))
                if self._get_load(least_loaded) < self._get_load(agent_id):
                    logger.info(f"负载均衡: {agent_id} → {least_loaded}")
                    return least_loaded

        return agent_id

    def _find_alternatives(self, intent: str, current_agent: str) -> List[str]:
        """
        查找备选智能体

        Args:
            intent: 意图
            current_agent: 当前选中的智能体

        Returns:
            备选智能体列表
        """
        all_agents = set(self.DEFAULT_AGENT_MAPPING.values())
        all_agents.discard(current_agent)

        # 按相关性排序
        intent_agents = {
            "coding": ["react_agent", "plan_execute_agent", "general_chat_agent"],
            "research": ["react_agent", "general_chat_agent"],
            "planning": ["coding_agent", "react_agent", "general_chat_agent"],
            "analysis": ["research_agent", "plan_execute_agent", "general_chat_agent"],
        }

        return intent_agents.get(intent, ["general_chat_agent"])

    def _build_reason(
        self, intent: str, confidence: float, requires_redirect: bool, selected_agent: str
    ) -> str:
        """构建路由决策原因"""
        if requires_redirect:
            return f"意图 '{intent}' 置信度 ({confidence:.2f}) 不足，重定向后路由到 {selected_agent}"
        return f"意图 '{intent}' 置信度 ({confidence:.2f}) 足够，路由到 {selected_agent}"

    def _record_decision(self, decision: RouteDecision):
        """记录路由决策历史"""
        self._routing_history.append(decision)
        if len(self._routing_history) > self._max_history:
            self._routing_history = self._routing_history[-self._max_history // 2:]

    def _update_load(self, agent_id: str):
        """更新智能体负载计数"""
        self._load_counter[agent_id] = self._load_counter.get(agent_id, 0) + 1

    def _get_load(self, agent_id: str) -> int:
        """获取智能体负载"""
        return self._load_counter.get(agent_id, 0)

    def get_routing_stats(self) -> Dict[str, Any]:
        """获取路由统计信息"""
        if not self._routing_history:
            return {"total_decisions": 0}

        agent_counts = {}
        redirect_count = 0
        for decision in self._routing_history:
            agent = decision.selected_agent
            agent_counts[agent] = agent_counts.get(agent, 0) + 1
            if decision.requires_redirect:
                redirect_count += 1

        total = len(self._routing_history)
        return {
            "total_decisions": total,
            "redirect_rate": redirect_count / total if total > 0 else 0,
            "agent_distribution": agent_counts,
            "load_balance": dict(self._load_counter),
        }

    def reset_load_counters(self):
        """重置负载计数器"""
        self._load_counter.clear()
        logger.info("负载计数器已重置")

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "status": "healthy" if self._initialized else "unhealthy",
            "history_size": len(self._routing_history),
            "active_agents": len(self._load_counter),
        }


# 全局意图路由器实例
intent_router = IntentRouter()
