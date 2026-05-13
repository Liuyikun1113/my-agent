"""
智能体基类
定义所有智能体的统一接口
"""
import asyncio
import logging
import re
from typing import AsyncGenerator, Dict, List, Optional, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AgentCapabilities:
    """智能体能力描述"""
    can_chat: bool = True
    can_tool_call: bool = True
    can_plan_execute: bool = False
    can_react: bool = False
    can_research: bool = False
    can_code: bool = False
    supported_intents: List[str] = field(default_factory=list)


@dataclass
class AgentStatus:
    """智能体状态"""
    status: str  # idle, busy, error, offline
    current_task: Optional[str] = None
    last_heartbeat: Optional[float] = None
    error_message: Optional[str] = None
    performance_metrics: Dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """
    智能体基类
    所有智能体必须继承此基类
    """

    def __init__(self, agent_id: str, name: str, description: str):
        self.agent_id = agent_id
        self.name = name
        self.description = description
        self.capabilities = AgentCapabilities()
        self.status = AgentStatus(status="idle")
        self._initialized = False

    @abstractmethod
    async def initialize(self):
        """
        初始化智能体
        """
        pass

    @abstractmethod
    async def process_message(
        self,
        session_id: str,
        message_id: str,
        message_content: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        处理消息

        Args:
            session_id: 会话ID
            message_id: 消息ID
            message_content: 消息内容
            context: 上下文信息

        Returns:
            Dict[str, Any]: 处理结果
        """
        pass

    async def stream_response(
        self,
        session_id: str,
        message_id: str,
        message_content: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式响应生成器
        默认实现：调用 process_message() 获取完整结果，按句子拆分逐句 yield。
        子类可以重写以接入真实 LLM streaming。

        Yields:
            {"delta": str, "full_response": str, "metadata": dict, "done": bool}
        """
        result = await self.process_message(
            session_id=session_id,
            message_id=message_id,
            message_content=message_content,
            context=context,
        )
        response_text = result.get("response", "")
        sentences = re.split(r'(?<=[。！？.!?\n])', response_text)
        for sentence in sentences:
            stripped = sentence.strip()
            if stripped:
                yield {
                    "delta": stripped,
                    "full_response": response_text,
                    "metadata": result,
                    "done": False,
                }
                await asyncio.sleep(0.03)  # 模拟 token 生成延迟

        yield {
            "delta": "",
            "full_response": response_text,
            "metadata": result,
            "done": True,
        }

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            Dict[str, Any]: 健康状态信息
        """
        pass

    def update_status(self, status: str, task: Optional[str] = None, error: Optional[str] = None):
        """
        更新智能体状态

        Args:
            status: 新状态
            task: 当前任务
            error: 错误信息
        """
        self.status.status = status
        self.status.current_task = task
        self.status.error_message = error

    async def cleanup(self):
        """
        清理智能体资源
        """
        pass