"""
智能体执行图节点
处理不同范式智能体的执行逻辑（Plan-and-Execute, ReAct, 通用对话）
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from config.settings import settings
from agents.registry import agent_registry

logger = logging.getLogger(__name__)


async def agent_execution_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    智能体执行节点
    根据当前选定的智能体执行对应的处理逻辑

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    try:
        current_agent_id = state.get("current_agent", "general_chat_agent")
        agent = agent_registry.get_agent(current_agent_id)

        if not agent:
            logger.warning(f"智能体不存在: {current_agent_id}，回退到通用聊天智能体")
            current_agent_id = "general_chat_agent"
            agent = agent_registry.get_agent(current_agent_id)

        if not agent:
            raise ValueError(f"无法找到可用智能体: {current_agent_id}")

        messages = state.get("messages", [])
        session_id = state.get("session_id", "unknown")

        user_messages = [m for m in messages if m.get("role") == "user"]
        if not user_messages:
            return {"current_agent": current_agent_id}

        latest_message = user_messages[-1]
        message_content = latest_message.get("content", "")
        message_id = latest_message.get("id", f"msg_{datetime.now().timestamp()}")

        logger.info(f"智能体 [{current_agent_id}] 开始处理消息: {message_id}")

        agent_registry.update_agent_status(current_agent_id, "busy", task=message_id)

        try:
            result = await agent.process_message(
                session_id=session_id,
                message_id=message_id,
                message_content=message_content,
                context={
                    "intent": state.get("intent"),
                    "intent_confidence": state.get("intent_confidence"),
                    "tool_results": state.get("tool_results", []),
                    "metadata": state.get("metadata", {}),
                },
            )

            agent_registry.update_agent_status(current_agent_id, "idle")

            return {
                "current_agent": current_agent_id,
                "messages": [{
                    "role": "assistant",
                    "content": result.get("response", ""),
                    "id": result.get("message_id", f"resp_{message_id}"),
                    "agent_id": current_agent_id,
                    "metadata": result.get("metadata", {}),
                }],
                "metadata": {
                    **state.get("metadata", {}),
                    "agent_execution": {
                        "agent_id": current_agent_id,
                        "message_id": message_id,
                        "execution_timestamp": datetime.now().isoformat(),
                        "result": result,
                    }
                }
            }

        except Exception as e:
            agent_registry.update_agent_status(current_agent_id, "error", error=str(e))
            raise

    except Exception as e:
        logger.error(f"智能体执行节点失败: {e}")
        error_message = f"抱歉，智能体处理您的请求时遇到了问题: {str(e)}"
        return {
            "messages": [{
                "role": "assistant",
                "content": error_message,
                "id": f"error_{datetime.now().timestamp()}",
                "is_error": True,
            }],
            "metadata": {
                **state.get("metadata", {}),
                "agent_execution_error": str(e),
            }
        }


async def plan_generation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    计划生成节点（Plan-and-Execute范式）
    将用户请求分解为可执行的待办列表

    Args:
        state: 当前状态

    Returns:
        更新后的状态（包含todo_list）
    """
    try:
        messages = state.get("messages", [])
        user_messages = [m for m in messages if m.get("role") == "user"]
        if not user_messages:
            return {"todo_list": []}

        latest_message = user_messages[-1]
        content = latest_message.get("content", "")

        current_agent_id = state.get("current_agent", "")
        agent = agent_registry.get_agent(current_agent_id)

        if not agent or not getattr(agent.capabilities, "can_plan_execute", False):
            logger.debug(f"智能体 {current_agent_id} 不支持Plan-and-Execute，跳过计划生成")
            return {"todo_list": []}

        # 使用智能体生成计划
        plan = await _generate_plan(agent, content, state)

        todo_list = []
        for i, step in enumerate(plan):
            todo_list.append({
                "id": f"todo_{i}_{datetime.now().timestamp()}",
                "title": step.get("title", f"步骤 {i + 1}"),
                "description": step.get("description", ""),
                "status": "pending",
                "order": i + 1,
                "dependencies": step.get("dependencies", []),
                "created_at": datetime.now().isoformat(),
            })

        logger.info(f"生成待办列表: {len(todo_list)} 项")

        return {
            "todo_list": todo_list,
            "current_task": todo_list[0] if todo_list else None,
            "metadata": {
                **state.get("metadata", {}),
                "plan_generation": {
                    "total_steps": len(todo_list),
                    "steps": [t["title"] for t in todo_list],
                    "generation_timestamp": datetime.now().isoformat(),
                }
            }
        }

    except Exception as e:
        logger.error(f"计划生成节点执行失败: {e}")
        return {"todo_list": []}


async def plan_execution_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    计划执行节点（Plan-and-Execute范式）
    逐个执行待办列表中的任务

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    try:
        todo_list = state.get("todo_list", [])
        if not todo_list:
            return {}

        # 找到第一个待处理的任务
        current_task = None
        for task in todo_list:
            if task.get("status") == "pending":
                # 检查依赖是否已完成
                deps = task.get("dependencies", [])
                deps_met = all(
                    any(t.get("id") == d and t.get("status") == "completed" for t in todo_list)
                    for d in deps
                )
                if deps_met:
                    current_task = task
                    break

        if not current_task:
            logger.debug("所有任务已完成")
            return {"current_task": None, "todo_list": todo_list}

        # 标记为进行中
        current_task["status"] = "in_progress"
        current_task["started_at"] = datetime.now().isoformat()

        logger.info(f"执行任务: {current_task['title']}")

        # 更新todo_list中的任务状态
        updated_todo_list = []
        for task in todo_list:
            if task["id"] == current_task["id"]:
                updated_todo_list.append(current_task)
            else:
                updated_todo_list.append(task)

        return {
            "current_task": current_task,
            "todo_list": updated_todo_list,
            "metadata": {
                **state.get("metadata", {}),
                "plan_execution": {
                    "current_task_id": current_task["id"],
                    "current_task_title": current_task["title"],
                    "execution_timestamp": datetime.now().isoformat(),
                }
            }
        }

    except Exception as e:
        logger.error(f"计划执行节点执行失败: {e}")
        return {}


async def react_reasoning_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    ReAct推理节点
    实现 Thought → Action → Observation 循环

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    try:
        messages = state.get("messages", [])
        tool_results = state.get("tool_results", [])
        current_agent_id = state.get("current_agent", "")

        agent = agent_registry.get_agent(current_agent_id)
        if not agent or not getattr(agent.capabilities, "can_react", False):
            logger.debug(f"智能体 {current_agent_id} 不支持ReAct，跳过推理")
            return {}

        # 构建推理上下文
        last_message = messages[-1] if messages else {}
        last_tool_result = tool_results[-1] if tool_results else None

        react_context = {
            "thought": None,
            "action": None,
            "observation": None,
            "cycle": state.get("metadata", {}).get("react_cycle", 0) + 1,
        }

        # Thought阶段：分析当前状态，决定下一步
        if last_tool_result and not last_tool_result.get("is_error"):
            react_context["observation"] = last_tool_result.get("result")
            react_context["thought"] = "工具执行成功，分析结果并决定下一步"
        elif last_tool_result and last_tool_result.get("is_error"):
            react_context["observation"] = f"工具执行失败: {last_tool_result.get('error_message')}"
            react_context["thought"] = "工具执行失败，尝试替代方案"
        else:
            react_context["thought"] = f"分析用户请求: {last_message.get('content', '')[:100]}"

        max_cycles = 5
        if react_context["cycle"] >= max_cycles:
            logger.info(f"ReAct循环达到最大次数 ({max_cycles})，停止推理")
            react_context["thought"] = "已达到最大推理循环次数，给出最终回答"

        logger.info(f"ReAct推理周期 {react_context['cycle']}: {react_context['thought']}")

        return {
            "metadata": {
                **state.get("metadata", {}),
                "react_reasoning": react_context,
                "react_cycle": react_context["cycle"],
                "react_timestamp": datetime.now().isoformat(),
            }
        }

    except Exception as e:
        logger.error(f"ReAct推理节点执行失败: {e}")
        return {}


async def response_generation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    响应生成节点
    根据智能体输出、工具结果等生成最终响应

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    try:
        current_agent_id = state.get("current_agent", "general_chat_agent")
        messages = state.get("messages", [])
        tool_results = state.get("tool_results", [])
        todo_list = state.get("todo_list", [])

        # 检查是否已有助手消息
        assistant_messages = [m for m in messages if m.get("role") == "assistant"]
        if assistant_messages:
            latest_assistant = assistant_messages[-1]
            if not latest_assistant.get("is_error"):
                logger.debug("已有有效的助手响应，跳过响应生成")
                return {}

        response_parts = []

        # 汇总工具结果
        if tool_results:
            success_results = [r for r in tool_results if not r.get("is_error")]
            failed_results = [r for r in tool_results if r.get("is_error")]

            if success_results:
                summary = "; ".join([r.get("summary", "") for r in success_results if r.get("summary")])
                response_parts.append(f"工具执行结果: {summary}")

            if failed_results:
                errors = "; ".join([r.get("error_message", "") for r in failed_results if r.get("error_message")])
                response_parts.append(f"部分工具执行失败: {errors}")

        # 汇总待办列表进度
        if todo_list:
            completed = len([t for t in todo_list if t.get("status") == "completed"])
            total = len(todo_list)
            response_parts.append(f"任务进度: {completed}/{total}")

        if response_parts:
            formatted_response = "\n".join(response_parts)
        else:
            formatted_response = "处理完成"

        return {
            "messages": [{
                "role": "assistant",
                "content": formatted_response,
                "id": f"resp_{datetime.now().timestamp()}",
                "agent_id": current_agent_id,
            }],
            "metadata": {
                **state.get("metadata", {}),
                "response_generation": {
                    "parts_count": len(response_parts),
                    "generation_timestamp": datetime.now().isoformat(),
                }
            }
        }

    except Exception as e:
        logger.error(f"响应生成节点执行失败: {e}")
        return {
            "messages": [{
                "role": "assistant",
                "content": f"处理您的请求时出现问题: {str(e)}",
                "id": f"error_{datetime.now().timestamp()}",
                "is_error": True,
            }]
        }


async def _generate_plan(agent, content: str, state: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    使用智能体生成执行计划

    Args:
        agent: 智能体实例
        content: 用户消息内容
        state: 当前状态

    Returns:
        计划步骤列表
    """
    try:
        result = await agent.process_message(
            session_id=state.get("session_id", ""),
            message_id=f"plan_{datetime.now().timestamp()}",
            message_content=f"请为以下任务生成一个分步骤的执行计划:\n{content}",
            context={"mode": "planning"},
        )
        if isinstance(result, dict):
            steps = result.get("plan", result.get("steps", []))
            if isinstance(steps, list):
                return steps
        return [{"title": "分析请求", "description": content}, {"title": "执行处理", "description": "执行相应操作"}]
    except Exception as e:
        logger.error(f"生成计划失败: {e}")
        return [{"title": "默认步骤", "description": content}]
