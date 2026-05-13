"""
智能体注册表
"""
import logging
from typing import Dict, List, Optional, Any, Type
from dataclasses import dataclass, field
import uuid

from .base_agent import BaseAgent, AgentCapabilities, AgentStatus

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    智能体注册表
    管理所有可用智能体的注册和发现
    """

    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.agent_status: Dict[str, AgentStatus] = {}
        self._initialized = False

    def initialize(self):
        """
        初始化智能体注册表
        """
        if self._initialized:
            return

        try:
            # 注册默认智能体
            self._register_default_agents()

            self._initialized = True
            logger.info("智能体注册表初始化完成")
            logger.info(f"已注册智能体: {list(self.agents.keys())}")

        except Exception as e:
            logger.error(f"智能体注册表初始化失败: {e}", exc_info=True)
            raise

    def _register_default_agents(self):
        """
        注册默认智能体
        """
        # 这里暂时不创建具体智能体实例
        # 等智能体实现完成后在这里注册
        pass

    def register_agent(self, agent: BaseAgent):
        """
        注册智能体

        Args:
            agent: 智能体实例
        """
        if agent.agent_id in self.agents:
            logger.warning(f"智能体已存在，将覆盖: {agent.agent_id}")

        self.agents[agent.agent_id] = agent
        self.agent_status[agent.agent_id] = agent.status

        logger.info(f"智能体注册成功: {agent.agent_id} ({agent.name})")

    def unregister_agent(self, agent_id: str):
        """
        注销智能体

        Args:
            agent_id: 智能体ID
        """
        if agent_id in self.agents:
            agent = self.agents.pop(agent_id)
            self.agent_status.pop(agent_id, None)

            logger.info(f"智能体注销成功: {agent_id}")

            # 清理智能体资源
            try:
                agent.cleanup()
            except Exception as e:
                logger.error(f"清理智能体资源失败: {agent_id}, error={e}")

    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """
        获取智能体

        Args:
            agent_id: 智能体ID

        Returns:
            Optional[BaseAgent]: 智能体实例，如果不存在则返回None
        """
        return self.agents.get(agent_id)

    def get_agent_by_name(self, name: str) -> Optional[BaseAgent]:
        """
        通过名称获取智能体

        Args:
            name: 智能体名称

        Returns:
            Optional[BaseAgent]: 智能体实例，如果不存在则返回None
        """
        for agent in self.agents.values():
            if agent.name == name:
                return agent
        return None

    def list_agents(
        self,
        capability: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[BaseAgent]:
        """
        列出智能体

        Args:
            capability: 能力过滤
            status: 状态过滤

        Returns:
            List[BaseAgent]: 智能体列表
        """
        filtered_agents = []

        for agent in self.agents.values():
            # 能力过滤
            if capability:
                if capability == "chat" and not agent.capabilities.can_chat:
                    continue
                if capability == "tool_call" and not agent.capabilities.can_tool_call:
                    continue
                if capability == "plan_execute" and not agent.capabilities.can_plan_execute:
                    continue
                if capability == "react" and not agent.capabilities.can_react:
                    continue
                if capability == "research" and not agent.capabilities.can_research:
                    continue
                if capability == "code" and not agent.capabilities.can_code:
                    continue

            # 状态过滤
            if status and agent.status.status != status:
                continue

            filtered_agents.append(agent)

        return filtered_agents

    def find_agent_for_intent(self, intent: str) -> Optional[BaseAgent]:
        """
        根据意图查找合适的智能体

        Args:
            intent: 意图标签

        Returns:
            Optional[BaseAgent]: 合适的智能体，如果找不到则返回None
        """
        # 首先查找支持该意图的专用智能体
        for agent in self.agents.values():
            if intent in agent.capabilities.supported_intents:
                return agent

        # 如果没有专用智能体，返回通用聊天智能体
        for agent in self.agents.values():
            if agent.capabilities.can_chat:
                return agent

        return None

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            Dict[str, Any]: 健康状态信息
        """
        try:
            total_agents = len(self.agents)
            healthy_agents = 0
            agent_health = {}

            for agent_id, agent in self.agents.items():
                try:
                    agent_health[agent_id] = agent.health_check()
                    if agent_health[agent_id].get("status") == "healthy":
                        healthy_agents += 1
                except Exception as e:
                    logger.error(f"智能体健康检查失败: {agent_id}, error={e}")
                    agent_health[agent_id] = {"status": "error", "error": str(e)}

            return {
                "status": "healthy" if healthy_agents == total_agents > 0 else "unhealthy",
                "total_agents": total_agents,
                "healthy_agents": healthy_agents,
                "agents": agent_health,
            }

        except Exception as e:
            logger.error(f"智能体注册表健康检查失败: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    def update_agent_status(self, agent_id: str, status: str, task: Optional[str] = None):
        """
        更新智能体状态

        Args:
            agent_id: 智能体ID
            status: 新状态
            task: 当前任务
        """
        if agent_id in self.agents:
            self.agents[agent_id].update_status(status, task)
            self.agent_status[agent_id] = self.agents[agent_id].status

    def get_agent_status(self, agent_id: str) -> Optional[AgentStatus]:
        """
        获取智能体状态

        Args:
            agent_id: 智能体ID

        Returns:
            Optional[AgentStatus]: 智能体状态
        """
        return self.agent_status.get(agent_id)

    def list_agent_status(self) -> Dict[str, AgentStatus]:
        """
        列出所有智能体状态

        Returns:
            Dict[str, AgentStatus]: 智能体状态字典
        """
        return self.agent_status.copy()


# 全局智能体注册表实例
agent_registry = AgentRegistry()