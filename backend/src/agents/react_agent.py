"""
ReAct智能体
实现 Reason-and-Act 模式：Thought → Action → Observation 循环
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from agents.base_agent import BaseAgent, AgentCapabilities, AgentStatus
from tools.registry import tool_registry

logger = logging.getLogger(__name__)


class ReactAgent(BaseAgent):
    """
    ReAct智能体

    工作流程:
    1. Thought: 分析当前状态，推理下一步行动
    2. Action: 执行具体的工具调用或操作
    3. Observation: 观察行动结果，更新理解
    4. 循环直到得出最终答案

    适用场景：需要多步推理、工具调用和迭代分析的复杂任务
    """

    MAX_REACT_CYCLES = 5

    def __init__(
        self,
        agent_id: str = "react_agent",
        name: str = "ReAct Agent",
        description: str = "推理-行动智能体，通过思考-行动-观察循环解决复杂问题",
    ):
        super().__init__(agent_id=agent_id, name=name, description=description)
        self.capabilities = AgentCapabilities(
            can_chat=True,
            can_tool_call=True,
            can_plan_execute=False,
            can_react=True,
            supported_intents=["analysis", "research", "coding"],
        )

    async def initialize(self):
        """初始化智能体"""
        if self._initialized:
            return
        self._initialized = True
        self.status = AgentStatus(status="idle")
        logger.info(f"ReAct智能体初始化完成: {self.agent_id}")

    async def process_message(
        self,
        session_id: str,
        message_id: str,
        message_content: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        处理消息 - ReAct循环

        Args:
            session_id: 会话ID
            message_id: 消息ID
            message_content: 消息内容
            context: 上下文信息

        Returns:
            处理结果
        """
        try:
            self.update_status("busy", task=message_id)
            context = context or {}

            react_trace = []
            current_thought = message_content

            for cycle in range(1, self.MAX_REACT_CYCLES + 1):
                logger.info(f"ReAct循环 {cycle}/{self.MAX_REACT_CYCLES}")

                # Thought阶段
                thought = self._reason(current_thought, react_trace, cycle)
                react_trace.append({"cycle": cycle, "phase": "thought", "content": thought})

                # Action阶段
                action_result = await self._act(thought, context)
                react_trace.append({"cycle": cycle, "phase": "action", "content": action_result})

                # Observation阶段
                observation = self._observe(thought, action_result)
                react_trace.append({"cycle": cycle, "phase": "observation", "content": observation})

                # 检查是否得出最终答案
                if self._is_final_answer(observation, action_result, cycle):
                    logger.info(f"ReAct循环在第 {cycle} 轮得出最终答案")
                    break

                current_thought = observation

            final_answer = self._synthesize_answer(message_content, react_trace)

            return {
                "response": final_answer,
                "message_id": f"resp_{message_id}",
                "react_trace": react_trace,
                "metadata": {
                    "cycles": len([t for t in react_trace if t["phase"] == "thought"]),
                    "tools_called": len([t for t in react_trace if t["phase"] == "action" and t["content"].get("tool_used")]),
                },
            }

        except Exception as e:
            logger.error(f"ReAct智能体处理消息失败: {e}")
            return {
                "response": f"抱歉，推理过程中出现问题: {str(e)}",
                "message_id": f"error_{message_id}",
                "is_error": True,
            }
        finally:
            self.update_status("idle")

    def _reason(self, current_input: str, trace: List[Dict], cycle: int) -> str:
        """
        Thought阶段：推理下一步该做什么

        Args:
            current_input: 当前输入
            trace: 历史推理轨迹
            cycle: 当前循环次数

        Returns:
            推理结果
        """
        if cycle == 1:
            return f"分析用户请求: {current_input[:200]}"

        # 基于历史轨迹推理
        last_observation = None
        for entry in reversed(trace):
            if entry["phase"] == "observation":
                last_observation = entry["content"]
                break

        if last_observation:
            tool_failures = sum(1 for t in trace if t["phase"] == "action" and not t["content"].get("success", True))
            if tool_failures > 0:
                return f"之前的工具调用有 {tool_failures} 次失败，需要尝试替代方法"
            return f"基于观察结果继续推理: {str(last_observation)[:200]}"

        return "继续分析问题"

    async def _act(self, thought: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Action阶段：执行具体操作

        Args:
            thought: 推理结果
            context: 上下文

        Returns:
            行动结果
        """
        result = {"success": True, "actions_taken": [], "tool_used": None}

        # 根据推理内容选择合适的工具
        thought_lower = thought.lower()

        if any(kw in thought_lower for kw in ["搜索", "查询", "search", "find"]):
            tool_result = await tool_registry.call_tool("web_search", {"query": thought})
            result["tool_used"] = "web_search"
            result["tool_output"] = tool_result.data if tool_result.success else tool_result.error_message
            result["success"] = tool_result.success

        elif any(kw in thought_lower for kw in ["计算", "calculate", "compute"]):
            tool_result = await tool_registry.call_tool("calculator", {"expression": thought})
            result["tool_used"] = "calculator"
            result["tool_output"] = tool_result.data if tool_result.success else tool_result.error_message
            result["success"] = tool_result.success

        elif any(kw in thought_lower for kw in ["文件", "代码", "file", "code"]):
            tool_result = await tool_registry.call_tool("file_operations", {"action": "read", "content": thought})
            result["tool_used"] = "file_operations"
            result["tool_output"] = tool_result.data if tool_result.success else tool_result.error_message
            result["success"] = tool_result.success

        else:
            result["tool_used"] = None
            result["tool_output"] = "无需工具调用，直接推理"
            result["actions_taken"].append("internal_reasoning")

        return result

    def _observe(self, thought: str, action_result: Dict[str, Any]) -> str:
        """
        Observation阶段：观察行动结果

        Args:
            thought: 原始推理
            action_result: 行动结果

        Returns:
            观察结论
        """
        if action_result.get("success"):
            output = action_result.get("tool_output", "操作成功")
            return f"观察: 操作成功完成。输出: {str(output)[:300]}"
        else:
            error = action_result.get("tool_output", "操作失败")
            return f"观察: 操作未能成功。原因: {str(error)[:300]}"

    def _is_final_answer(
        self, observation: str, action_result: Dict[str, Any], cycle: int
    ) -> bool:
        """
        判断是否可以给出最终答案

        Args:
            observation: 观察结果
            action_result: 行动结果
            cycle: 当前循环

        Returns:
            是否可以结束
        """
        if cycle >= self.MAX_REACT_CYCLES:
            return True

        if action_result.get("success") and "最终答案" in observation:
            return True

        return False

    def _synthesize_answer(self, original_request: str, react_trace: List[Dict]) -> str:
        """
        综合React轨迹生成最终答案

        Args:
            original_request: 原始请求
            react_trace: React推理轨迹

        Returns:
            最终答案
        """
        cycles = len([t for t in react_trace if t["phase"] == "thought"])
        tools_used = [t["content"].get("tool_used") for t in react_trace if t["phase"] == "action"]
        tools_used = [t for t in tools_used if t]

        answer_parts = [f"经过 {cycles} 轮推理分析"]

        if tools_used:
            answer_parts.append(f"使用了工具: {', '.join(tools_used)}")

        # 提取最后的观察作为结论
        for entry in reversed(react_trace):
            if entry["phase"] == "observation":
                answer_parts.append(f"\n结论: {entry['content']}")
                break

        return "\n".join(answer_parts)

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "agent_id": self.agent_id,
            "status": "healthy" if self._initialized else "not_initialized",
            "max_cycles": self.MAX_REACT_CYCLES,
        }
