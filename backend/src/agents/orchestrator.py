"""
多智能体协调器
负责智能体的路由、负载均衡和协调
"""
import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple
import time
import random

from .base_agent import BaseAgent, AgentStatus
from .registry import agent_registry
from config.settings import settings

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    多智能体协调器
    管理智能体之间的协作和任务分配
    """

    def __init__(self):
        self.load_balancing_strategy = "round_robin"  # round_robin, least_loaded, random
        self.agent_weights: Dict[str, float] = {}  # 智能体权重（用于加权轮询）
        self.agent_load: Dict[str, int] = {}  # 智能体当前负载（并发任务数）
        self.agent_performance: Dict[str, Dict[str, Any]] = {}  # 智能体性能指标
        self._initialized = False

    async def initialize(self):
        """
        初始化协调器
        """
        if self._initialized:
            return

        try:
            # 初始化智能体注册表
            agent_registry.initialize()

            # 初始化负载统计
            self._initialize_load_tracking()

            # 启动性能监控
            asyncio.create_task(self._monitor_agent_performance())

            self._initialized = True
            logger.info("智能体协调器初始化完成")

        except Exception as e:
            logger.error(f"智能体协调器初始化失败: {e}", exc_info=True)
            raise

    def _initialize_load_tracking(self):
        """
        初始化负载跟踪
        """
        # 为每个已注册的智能体初始化负载统计
        for agent_id, agent in agent_registry.agents.items():
            self.agent_load[agent_id] = 0
            self.agent_weights[agent_id] = 1.0  # 默认权重
            self.agent_performance[agent_id] = {
                "total_tasks": 0,
                "successful_tasks": 0,
                "failed_tasks": 0,
                "avg_response_time": 0.0,
                "last_response_time": 0.0,
            }

    async def _monitor_agent_performance(self):
        """
        监控智能体性能（后台任务）
        """
        while True:
            try:
                await self._update_agent_performance()
                await asyncio.sleep(60)  # 每分钟更新一次
            except Exception as e:
                logger.error(f"智能体性能监控失败: {e}")
                await asyncio.sleep(10)

    async def _update_agent_performance(self):
        """
        更新智能体性能指标
        """
        for agent_id, agent in agent_registry.agents.items():
            try:
                health = await agent.health_check()
                self.agent_performance[agent_id]["status"] = health.get("status", "unknown")
                self.agent_performance[agent_id]["last_check"] = time.time()
            except Exception as e:
                logger.error(f"获取智能体性能指标失败: {agent_id}, error={e}")
                self.agent_performance[agent_id]["status"] = "error"

    async def route_to_agent(
        self,
        session_id: str,
        message_content: str,
        intent: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[BaseAgent], Dict[str, Any]]:
        """
        路由消息到合适的智能体

        Args:
            session_id: 会话ID
            message_content: 消息内容
            intent: 意图标签（可选）
            context: 上下文信息

        Returns:
            Tuple[Optional[BaseAgent], Dict[str, Any]]: (智能体实例, 路由决策信息)
        """
        try:
            if not self._initialized:
                await self.initialize()

            # 1. 基于意图选择智能体
            if intent:
                agent = await self._select_agent_by_intent(intent)
                if agent:
                    logger.info(f"基于意图路由: intent={intent}, agent={agent.agent_id}")
                    return agent, {
                        "strategy": "intent_based",
                        "intent": intent,
                        "agent_id": agent.agent_id,
                    }

            # 2. 基于负载均衡选择智能体
            agent = await self._select_agent_by_load_balancing()
            if agent:
                logger.info(f"基于负载均衡路由: agent={agent.agent_id}")
                return agent, {
                    "strategy": "load_balancing",
                    "agent_id": agent.agent_id,
                }

            # 3. 默认选择第一个可用智能体
            agent = await self._select_default_agent()
            if agent:
                logger.info(f"使用默认智能体: agent={agent.agent_id}")
                return agent, {
                    "strategy": "default",
                    "agent_id": agent.agent_id,
                }

            logger.warning("没有可用的智能体")
            return None, {"error": "No available agents"}

        except Exception as e:
            logger.error(f"智能体路由失败: session={session_id}, error={e}", exc_info=True)
            return None, {"error": str(e)}

    async def _select_agent_by_intent(self, intent: str) -> Optional[BaseAgent]:
        """
        根据意图选择智能体
        """
        # 使用注册表的意图查找功能
        agent = agent_registry.find_agent_for_intent(intent)
        if agent and self._is_agent_available(agent):
            return agent
        return None

    async def _select_agent_by_load_balancing(self) -> Optional[BaseAgent]:
        """
        基于负载均衡选择智能体
        """
        available_agents = []
        for agent in agent_registry.agents.values():
            if self._is_agent_available(agent):
                available_agents.append(agent)

        if not available_agents:
            return None

        # 根据负载均衡策略选择智能体
        if self.load_balancing_strategy == "round_robin":
            return self._round_robin_selection(available_agents)
        elif self.load_balancing_strategy == "least_loaded":
            return self._least_loaded_selection(available_agents)
        elif self.load_balancing_strategy == "random":
            return self._random_selection(available_agents)
        else:
            # 默认使用轮询
            return self._round_robin_selection(available_agents)

    def _round_robin_selection(self, agents: List[BaseAgent]) -> BaseAgent:
        """
        轮询选择
        """
        # 简单的轮询实现（按注册顺序）
        # 在实际应用中应该维护一个轮询指针
        if not hasattr(self, "_round_robin_index"):
            self._round_robin_index = 0

        if self._round_robin_index >= len(agents):
            self._round_robin_index = 0

        selected_agent = agents[self._round_robin_index]
        self._round_robin_index = (self._round_robin_index + 1) % len(agents)
        return selected_agent

    def _least_loaded_selection(self, agents: List[BaseAgent]) -> BaseAgent:
        """
        选择负载最低的智能体
        """
        # 按当前负载排序
        sorted_agents = sorted(
            agents,
            key=lambda agent: self.agent_load.get(agent.agent_id, 0)
        )
        return sorted_agents[0] if sorted_agents else None

    def _random_selection(self, agents: List[BaseAgent]) -> BaseAgent:
        """
        随机选择
        """
        return random.choice(agents) if agents else None

    async def _select_default_agent(self) -> Optional[BaseAgent]:
        """
        选择默认智能体（通用聊天智能体）
        """
        for agent in agent_registry.agents.values():
            if (self._is_agent_available(agent) and
                agent.capabilities.can_chat):
                return agent
        return None

    def _is_agent_available(self, agent: BaseAgent) -> bool:
        """
        检查智能体是否可用
        """
        # 检查状态
        if agent.status.status not in ["idle", "busy"]:
            return False

        # 检查负载（如果负载过高）
        current_load = self.agent_load.get(agent.agent_id, 0)
        max_load = settings.MAX_AGENT_LOAD if hasattr(settings, "MAX_AGENT_LOAD") else 10

        return current_load < max_load

    async def execute_with_agent(
        self,
        agent: BaseAgent,
        session_id: str,
        message_id: str,
        message_content: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        使用指定智能体执行任务

        Args:
            agent: 智能体实例
            session_id: 会话ID
            message_id: 消息ID
            message_content: 消息内容
            context: 上下文信息

        Returns:
            Dict[str, Any]: 执行结果
        """
        try:
            # 增加负载计数
            self._increment_agent_load(agent.agent_id)

            # 更新智能体状态
            agent.update_status("busy", f"处理会话 {session_id} 的消息")
            agent_registry.update_agent_status(agent.agent_id, "busy", f"处理会话 {session_id}")

            # 记录开始时间
            start_time = time.time()

            # 执行智能体处理
            result = await agent.process_message(
                session_id=session_id,
                message_id=message_id,
                message_content=message_content,
                context=context,
            )

            # 记录响应时间
            response_time = time.time() - start_time
            self._update_agent_performance_stats(agent.agent_id, True, response_time)

            return result

        except Exception as e:
            logger.error(f"智能体执行失败: agent={agent.agent_id}, error={e}", exc_info=True)
            self._update_agent_performance_stats(agent.agent_id, False, 0)
            raise

        finally:
            # 减少负载计数
            self._decrement_agent_load(agent.agent_id)

            # 更新智能体状态
            agent.update_status("idle")
            agent_registry.update_agent_status(agent.agent_id, "idle")

    def _increment_agent_load(self, agent_id: str):
        """
        增加智能体负载计数
        """
        if agent_id in self.agent_load:
            self.agent_load[agent_id] += 1

    def _decrement_agent_load(self, agent_id: str):
        """
        减少智能体负载计数
        """
        if agent_id in self.agent_load:
            self.agent_load[agent_id] = max(0, self.agent_load[agent_id] - 1)

    def _update_agent_performance_stats(
        self,
        agent_id: str,
        success: bool,
        response_time: float,
    ):
        """
        更新智能体性能统计
        """
        if agent_id not in self.agent_performance:
            self.agent_performance[agent_id] = {
                "total_tasks": 0,
                "successful_tasks": 0,
                "failed_tasks": 0,
                "avg_response_time": 0.0,
                "last_response_time": 0.0,
            }

        stats = self.agent_performance[agent_id]
        stats["total_tasks"] += 1
        if success:
            stats["successful_tasks"] += 1
        else:
            stats["failed_tasks"] += 1

        # 更新平均响应时间（移动平均）
        old_avg = stats["avg_response_time"]
        old_count = stats["total_tasks"] - 1
        if old_count > 0:
            stats["avg_response_time"] = (old_avg * old_count + response_time) / stats["total_tasks"]
        else:
            stats["avg_response_time"] = response_time

        stats["last_response_time"] = response_time

    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            Dict[str, Any]: 健康状态信息
        """
        try:
            # 检查注册表健康状态
            registry_health = agent_registry.health_check()

            # 计算总体负载
            total_load = sum(self.agent_load.values())
            agent_count = len(self.agent_load)
            avg_load = total_load / agent_count if agent_count > 0 else 0

            # 检查是否有可用的智能体
            available_agents = 0
            for agent in agent_registry.agents.values():
                if self._is_agent_available(agent):
                    available_agents += 1

            return {
                "status": "healthy" if registry_health["status"] == "healthy" and available_agents > 0 else "unhealthy",
                "registry_health": registry_health,
                "agent_count": agent_count,
                "available_agents": available_agents,
                "total_load": total_load,
                "average_load": avg_load,
                "load_balancing_strategy": self.load_balancing_strategy,
                "performance_stats": self.agent_performance,
            }

        except Exception as e:
            logger.error(f"协调器健康检查失败: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    async def cleanup(self):
        """
        清理协调器资源
        """
        try:
            self._initialized = False
            self.agent_load.clear()
            self.agent_weights.clear()
            self.agent_performance.clear()

            logger.info("智能体协调器资源清理完成")

        except Exception as e:
            logger.error(f"清理智能体协调器资源失败: {e}")


# 全局协调器实例
agent_orchestrator = AgentOrchestrator()