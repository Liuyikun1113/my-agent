"""
研究工作流定义
适用于信息检索、知识查询、数据分析等研究类任务
"""
import logging
from typing import Dict, Any

from langgraph.graph import StateGraph, END

from graph.base_graph import BaseGraphBuilder, AgentState, graph_registry
from graph.nodes.intent_node import intent_classification_node, agent_routing_node
from graph.nodes.tool_node import tool_selection_node, tool_execution_node, tool_result_processing_node
from graph.nodes.agent_node import agent_execution_node, response_generation_node

logger = logging.getLogger(__name__)


def create_research_workflow() -> Any:
    """
    创建研究工作流

    工作流结构:
    intent_classification → agent_routing → tool_selection → tool_execution
                                                        ↓
    response_generation ← agent_execution ← tool_result_processing

    特点:
    - 优先使用网络搜索和数据检索工具
    - 多轮工具调用支持深度研究
    - 结果汇总和引用生成

    Returns:
        编译后的研究工作流图
    """
    workflow_name = "research_workflow"

    cached = graph_registry.get_graph(workflow_name)
    if cached:
        logger.info(f"使用缓存的图: {workflow_name}")
        return cached

    try:
        builder = BaseGraphBuilder(graph_name=workflow_name)

        # 添加节点
        builder.add_node("intent_classification", intent_classification_node)
        builder.add_node("agent_routing", agent_routing_node)
        builder.add_node("tool_selection", tool_selection_node)
        builder.add_node("tool_execution", tool_execution_node)
        builder.add_node("tool_result_processing", tool_result_processing_node)
        builder.add_node("agent_execution", agent_execution_node)
        builder.add_node("response_generation", response_generation_node)

        # 入口
        builder.add_entry_point("intent_classification")

        # 意图分类 → 智能体路由
        builder.add_edge("intent_classification", "agent_routing")

        # 智能体路由 → 工具选择
        builder.add_edge("agent_routing", "tool_selection")

        # 工具选择 → 工具执行
        builder.add_edge("tool_selection", "tool_execution")

        # 工具执行 → 工具结果处理
        builder.add_edge("tool_execution", "tool_result_processing")

        # 工具结果处理 → 智能体执行
        builder.add_edge("tool_result_processing", "agent_execution")

        # 智能体执行 → 响应生成
        builder.add_edge("agent_execution", "response_generation")

        builder.add_finish_point()

        graph = builder.compile()
        graph_registry.register_graph(workflow_name, graph)

        logger.info(f"研究工作流创建完成: {workflow_name}")
        return graph

    except Exception as e:
        logger.error(f"创建工作流失败: {workflow_name}, 错误: {e}")
        raise
