"""
工具执行图节点
处理工具调用、重试、熔断和降级逻辑
"""
import logging
from typing import Dict, Any, List
from datetime import datetime

from config.settings import settings
from tools.registry import tool_registry, ToolResult

logger = logging.getLogger(__name__)


async def tool_selection_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    工具选择节点
    根据当前智能体和意图选择合适的工具

    Args:
        state: 当前状态

    Returns:
        更新后的状态（包含待执行的工具调用列表）
    """
    try:
        current_agent = state.get("current_agent", "general_chat_agent")
        intent = state.get("intent")
        messages = state.get("messages", [])

        if not messages:
            return {"tool_calls": []}

        last_message = messages[-1]
        content = last_message.get("content", "")

        tool_calls = []

        # 根据意图和智能体类型预选工具
        if intent == "coding":
            tool_calls.append({
                "tool_name": "file_operations",
                "tool_input": {"action": "read", "content": content},
                "tool_call_id": f"tool_file_ops_{datetime.now().timestamp()}",
                "priority": 1,
            })

        elif intent == "research":
            tool_calls.append({
                "tool_name": "web_search",
                "tool_input": {"query": content},
                "tool_call_id": f"tool_web_search_{datetime.now().timestamp()}",
                "priority": 1,
            })

        elif intent == "analysis":
            tool_calls.append({
                "tool_name": "calculator",
                "tool_input": {"expression": content},
                "tool_call_id": f"tool_calc_{datetime.now().timestamp()}",
                "priority": 1,
            })

        logger.info(f"为意图 '{intent}' 选择了 {len(tool_calls)} 个工具: {[t['tool_name'] for t in tool_calls]}")

        return {
            "tool_calls": tool_calls,
            "metadata": {
                **state.get("metadata", {}),
                "tool_selection": {
                    "selected_tools": [t["tool_name"] for t in tool_calls],
                    "intent": intent,
                    "agent": current_agent,
                    "selection_timestamp": datetime.now().isoformat(),
                }
            }
        }

    except Exception as e:
        logger.error(f"工具选择节点执行失败: {e}")
        return {"tool_calls": []}


async def tool_execution_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    工具执行节点
    依次执行工具调用列表，支持重试和熔断

    Args:
        state: 当前状态

    Returns:
        更新后的状态（包含工具执行结果）
    """
    try:
        tool_calls = state.get("tool_calls", [])
        if not tool_calls:
            logger.debug("没有工具调用需要执行")
            return {"tool_results": []}

        tool_results = []
        for tool_call in tool_calls:
            tool_name = tool_call.get("tool_name")
            tool_input = tool_call.get("tool_input", {})
            tool_id = tool_call.get("tool_call_id", f"tool_{tool_name}_{len(tool_results)}")

            logger.info(f"执行工具: {tool_name}")

            tool = tool_registry.get_tool(tool_name)
            if not tool:
                logger.error(f"工具不存在: {tool_name}")
                tool_results.append({
                    "tool_call_id": tool_id,
                    "tool_name": tool_name,
                    "result": None,
                    "is_error": True,
                    "error_message": f"工具 {tool_name} 不存在",
                })
                continue

            # 带重试的执行
            result = await _execute_with_retry(tool, tool_input, tool_name)

            tool_results.append({
                "tool_call_id": tool_id,
                "tool_name": tool_name,
                "result": result.data if result.success else None,
                "is_error": not result.success,
                "error_message": result.error_message,
                "execution_time": result.execution_time,
            })

            if result.success:
                logger.info(f"工具执行成功: {tool_name} ({result.execution_time:.2f}s)")
            else:
                logger.warning(f"工具执行失败: {tool_name}, 错误: {result.error_message}")

        return {
            "tool_results": tool_results,
            "tool_calls": [],
            "metadata": {
                **state.get("metadata", {}),
                "tool_execution": {
                    "total_calls": len(tool_calls),
                    "successful_calls": len([r for r in tool_results if not r.get("is_error")]),
                    "failed_calls": len([r for r in tool_results if r.get("is_error")]),
                    "execution_timestamp": datetime.now().isoformat(),
                }
            }
        }

    except Exception as e:
        logger.error(f"工具执行节点执行失败: {e}")
        return {
            "tool_results": [],
            "tool_calls": state.get("tool_calls", []),
            "metadata": {
                **state.get("metadata", {}),
                "tool_execution_error": str(e),
            }
        }


async def _execute_with_retry(tool, tool_input: Dict[str, Any], tool_name: str) -> ToolResult:
    """
    带指数退避重试的工具执行

    Args:
        tool: 工具实例
        tool_input: 工具输入
        tool_name: 工具名称

    Returns:
        ToolResult: 工具执行结果
    """
    last_result = None
    max_attempts = settings.TOOL_RETRY_MAX_ATTEMPTS

    for attempt in range(1, max_attempts + 1):
        try:
            result = await tool.execute(tool_input)
            if result.success:
                return result
            last_result = result
            logger.warning(f"工具执行失败 (尝试 {attempt}/{max_attempts}): {tool_name}, 错误: {result.error_message}")
        except Exception as e:
            logger.error(f"工具执行异常 (尝试 {attempt}/{max_attempts}): {tool_name}, 异常: {e}")
            last_result = ToolResult(success=False, data=None, error_message=str(e))

        if attempt < max_attempts:
            import asyncio
            delay = settings.TOOL_RETRY_BACKOFF_FACTOR ** attempt
            logger.info(f"等待 {delay:.1f}s 后重试...")
            await asyncio.sleep(delay)

    return last_result or ToolResult(success=False, data=None, error_message=f"工具 {tool_name} 重试耗尽")


async def tool_result_processing_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    工具结果处理节点
    对工具执行结果进行后处理和格式化

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    try:
        tool_results = state.get("tool_results", [])
        if not tool_results:
            return {}

        processed_results = []
        for result in tool_results:
            processed = {
                **result,
                "processed": True,
                "processed_timestamp": datetime.now().isoformat(),
            }

            if result.get("is_error"):
                processed["summary"] = f"工具 {result.get('tool_name')} 执行失败: {result.get('error_message', '未知错误')}"
            else:
                tool_name = result.get("tool_name", "unknown")
                exec_time = result.get("execution_time", 0)
                processed["summary"] = f"工具 {tool_name} 执行成功 ({exec_time:.2f}s)"

            processed_results.append(processed)

        success_count = len([r for r in tool_results if not r.get("is_error")])
        failure_count = len([r for r in tool_results if r.get("is_error")])

        return {
            "tool_results": processed_results,
            "metadata": {
                **state.get("metadata", {}),
                "tool_result_processing": {
                    "total": len(tool_results),
                    "success": success_count,
                    "failure": failure_count,
                    "processing_timestamp": datetime.now().isoformat(),
                }
            }
        }

    except Exception as e:
        logger.error(f"工具结果处理节点执行失败: {e}")
        return {}


async def tool_fallback_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    工具降级节点
    当所有重试都失败时，执行降级策略

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    try:
        tool_results = state.get("tool_results", [])
        failed_results = [r for r in tool_results if r.get("is_error")]

        if not failed_results:
            logger.debug("没有失败的工具调用，无需降级")
            return {"fallback_activated": False}

        logger.info(f"有 {len(failed_results)} 个工具调用失败，执行降级策略")

        fallback_results = []
        for failed in failed_results:
            tool_name = failed.get("tool_name", "")
            fallback_result = {
                "original_tool": tool_name,
                "fallback_used": True,
                "fallback_timestamp": datetime.now().isoformat(),
            }

            # 根据失败的工具选择降级策略
            if tool_name == "web_search":
                fallback_result["fallback_tool"] = "local_knowledge_base"
                fallback_result["result"] = {"message": "网络搜索不可用，使用本地知识库"}
            elif tool_name == "calculator":
                fallback_result["fallback_tool"] = "simple_eval"
                fallback_result["result"] = {"message": "高级计算器不可用，使用简单求值"}
            elif tool_name == "file_operations":
                fallback_result["fallback_tool"] = "memory_cache"
                fallback_result["result"] = {"message": "文件操作不可用，使用内存缓存"}
            else:
                fallback_result["fallback_tool"] = "default_response"
                fallback_result["result"] = {"message": f"工具 {tool_name} 不可用，使用默认响应"}

            fallback_results.append(fallback_result)

        return {
            "fallback_activated": True,
            "fallback_results": fallback_results,
            "metadata": {
                **state.get("metadata", {}),
                "tool_fallback": {
                    "failed_tools": [r.get("tool_name") for r in failed_results],
                    "fallback_tools": [r.get("fallback_tool") for r in fallback_results],
                    "fallback_timestamp": datetime.now().isoformat(),
                }
            }
        }

    except Exception as e:
        logger.error(f"工具降级节点执行失败: {e}")
        return {"fallback_activated": False}
