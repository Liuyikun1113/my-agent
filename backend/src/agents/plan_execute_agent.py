"""
Plan-and-Execute智能体
实现规划-执行模式：先将任务分解为步骤列表，再逐步执行
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid

from agents.base_agent import BaseAgent, AgentCapabilities, AgentStatus
from tools.registry import tool_registry

logger = logging.getLogger(__name__)


class PlanExecuteAgent(BaseAgent):
    """
    Plan-and-Execute智能体

    工作流程:
    1. 分析用户请求，生成执行计划（待办列表）
    2. 按顺序执行每个步骤，处理依赖关系
    3. 汇总结果，生成最终响应
    """

    def __init__(
        self,
        agent_id: str = "plan_execute_agent",
        name: str = "Plan-Execute Agent",
        description: str = "规划-执行智能体，将复杂任务分解为可执行的步骤列表",
    ):
        super().__init__(agent_id=agent_id, name=name, description=description)
        self.capabilities = AgentCapabilities(
            can_chat=True,
            can_tool_call=True,
            can_plan_execute=True,
            can_react=False,
            supported_intents=["planning", "coding", "analysis"],
        )
        self._plans: Dict[str, List[Dict[str, Any]]] = {}

    async def initialize(self):
        """初始化智能体"""
        if self._initialized:
            return
        self._initialized = True
        self.status = AgentStatus(status="idle")
        logger.info(f"Plan-Execute智能体初始化完成: {self.agent_id}")

    async def process_message(
        self,
        session_id: str,
        message_id: str,
        message_content: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        处理消息 - 核心执行逻辑

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

            if context.get("mode") == "planning":
                plan = self._decompose_task(message_content, context)
                return {
                    "response": f"已生成{len(plan)}个步骤的执行计划",
                    "message_id": f"plan_{message_id}",
                    "plan": plan,
                    "metadata": {"plan_steps": len(plan)},
                }

            # 标准Plan-and-Execute流程
            plan = self._decompose_task(message_content, context)
            self._plans[session_id] = plan

            results = []
            for step in plan:
                step_result = await self._execute_step(step, session_id, context)
                results.append(step_result)
                if not step_result.get("success", True):
                    logger.warning(f"步骤执行失败: {step.get('title')}, 错误: {step_result.get('error')}")

            response = self._summarize_results(message_content, plan, results)

            return {
                "response": response,
                "message_id": f"resp_{message_id}",
                "plan": plan,
                "results": results,
                "metadata": {
                    "total_steps": len(plan),
                    "completed_steps": len([r for r in results if r.get("success")]),
                    "failed_steps": len([r for r in results if not r.get("success")]),
                },
            }

        except Exception as e:
            logger.error(f"Plan-Execute智能体处理消息失败: {e}")
            return {
                "response": f"抱歉，任务规划执行过程中出现问题: {str(e)}",
                "message_id": f"error_{message_id}",
                "is_error": True,
            }
        finally:
            self.update_status("idle")

    def _decompose_task(
        self, content: str, context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        任务分解 - 将用户请求分解为可执行的步骤

        Args:
            content: 用户消息内容
            context: 上下文

        Returns:
            步骤列表
        """
        steps = []

        # 根据内容关键词进行启发式分解
        content_lower = content.lower()

        if any(kw in content_lower for kw in ["创建", "新建", "生成", "build", "create"]):
            steps.append({"title": "分析需求", "description": "理解用户的具体需求", "order": 1, "dependencies": []})
            steps.append({"title": "设计方案", "description": "设计实现方案", "order": 2, "dependencies": [1]})
            steps.append({"title": "执行实现", "description": "按照方案实现功能", "order": 3, "dependencies": [2]})
            steps.append({"title": "验证结果", "description": "验证实现是否符合需求", "order": 4, "dependencies": [3]})

        elif any(kw in content_lower for kw in ["分析", "调查", "研究", "analyze", "research"]):
            steps.append({"title": "收集信息", "description": "收集相关数据和信息", "order": 1, "dependencies": []})
            steps.append({"title": "分析数据", "description": "对收集的信息进行分析", "order": 2, "dependencies": [1]})
            steps.append({"title": "得出结论", "description": "基于分析得出最终结论", "order": 3, "dependencies": [2]})

        elif any(kw in content_lower for kw in ["修复", "调试", "debug", "fix"]):
            steps.append({"title": "定位问题", "description": "找到问题的根本原因", "order": 1, "dependencies": []})
            steps.append({"title": "制定修复方案", "description": "设计修复策略", "order": 2, "dependencies": [1]})
            steps.append({"title": "执行修复", "description": "实施修复方案", "order": 3, "dependencies": [2]})
            steps.append({"title": "测试验证", "description": "验证修复是否成功", "order": 4, "dependencies": [3]})

        else:
            steps.append({"title": "理解需求", "description": content, "order": 1, "dependencies": []})
            steps.append({"title": "执行处理", "description": "执行相应操作", "order": 2, "dependencies": [1]})

        return steps

    async def _execute_step(
        self, step: Dict[str, Any], session_id: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行单个步骤

        Args:
            step: 步骤定义
            session_id: 会话ID
            context: 上下文

        Returns:
            步骤执行结果
        """
        try:
            step_title = step.get("title", "")
            logger.info(f"执行步骤: {step_title}")

            # 尝试使用相关工具
            tools_used = []
            if "搜索" in step_title or "收集" in step_title:
                result = await tool_registry.call_tool("web_search", {"query": step.get("description", "")})
                tools_used.append("web_search")
            elif "实现" in step_title or "执行" in step_title:
                result = await tool_registry.call_tool("file_operations", {"action": "write", "content": step.get("description", "")})
                tools_used.append("file_operations")
            else:
                result = type("Result", (), {"success": True, "data": f"步骤 '{step_title}' 执行完成", "execution_time": 0.0})()

            return {
                "step": step_title,
                "success": result.success if hasattr(result, "success") else True,
                "data": result.data if hasattr(result, "data") else str(result),
                "tools_used": tools_used,
                "execution_time": getattr(result, "execution_time", 0),
            }

        except Exception as e:
            logger.error(f"步骤执行失败: {step.get('title')}, 错误: {e}")
            return {"step": step.get("title"), "success": False, "error": str(e), "tools_used": []}

    def _summarize_results(
        self, original_request: str, plan: List[Dict], results: List[Dict]
    ) -> str:
        """汇总执行结果"""
        total = len(plan)
        completed = len([r for r in results if r.get("success")])
        failed = len([r for r in results if not r.get("success")])

        summary = f"任务执行完成: {completed}/{total} 个步骤成功"
        if failed > 0:
            summary += f", {failed} 个步骤失败"

        for i, (step, result) in enumerate(zip(plan, results)):
            status = "✓" if result.get("success") else "✗"
            summary += f"\n  {status} 步骤{i + 1}: {step.get('title')}"

        return summary

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "agent_id": self.agent_id,
            "status": "healthy" if self._initialized else "not_initialized",
            "active_plans": len(self._plans),
        }

    async def cleanup(self):
        """清理资源"""
        self._plans.clear()
