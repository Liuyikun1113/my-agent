"""
LangGraph基础图定义
提供多智能体工作流的基础构建块
"""
import logging
from typing import Dict, Any, List, Optional, Callable, TypedDict, Annotated
from datetime import datetime
from enum import Enum

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from config.settings import settings
from agents.registry import agent_registry
from tools.registry import tool_registry
from intent.classifier import intent_classifier

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """智能体状态定义"""
    # 消息历史
    messages: Annotated[List[Dict[str, Any]], add_messages]

    # 当前会话信息
    session_id: str
    user_id: Optional[str]

    # 意图识别结果
    intent: Optional[str]
    intent_confidence: Optional[float]

    # 工具调用相关
    tool_calls: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]

    # 智能体执行上下文
    current_agent: Optional[str]
    agent_history: List[Dict[str, Any]]

    # 待办列表
    todo_list: List[Dict[str, Any]]
    current_task: Optional[Dict[str, Any]]

    # 元数据
    metadata: Dict[str, Any]
    timestamp: str


class GraphNodeType(Enum):
    """图节点类型枚举"""
    INTENT_CLASSIFICATION = "intent_classification"
    AGENT_ROUTING = "agent_routing"
    TOOL_EXECUTION = "tool_execution"
    RESPONSE_GENERATION = "response_generation"
    HUMAN_INTERVENTION = "human_intervention"
    MEMORY_COMPRESSION = "memory_compression"


class BaseGraphBuilder:
    """基础图构建器"""

    def __init__(self, graph_name: str = "multi_agent_workflow"):
        """
        初始化图构建器

        Args:
            graph_name: 图名称
        """
        self.graph_name = graph_name
        self.graph = StateGraph(AgentState)
        self.nodes: Dict[str, Callable] = {}
        self.edges: List[Dict[str, Any]] = []

    def add_node(self, name: str, node_func: Callable) -> None:
        """
        添加节点

        Args:
            name: 节点名称
            node_func: 节点函数
        """
        self.graph.add_node(name, node_func)
        self.nodes[name] = node_func

    def add_edge(self, start_node: str, end_node: str, condition: Optional[Callable] = None) -> None:
        """
        添加边

        Args:
            start_node: 起始节点
            end_node: 目标节点
            condition: 条件函数（可选）
        """
        if condition:
            self.graph.add_conditional_edges(start_node, condition, {True: end_node, False: END})
        else:
            self.graph.add_edge(start_node, end_node)
        self.edges.append({"start": start_node, "end": end_node, "condition": condition is not None})

    def add_entry_point(self, entry_node: str) -> None:
        """
        添加入口点

        Args:
            entry_node: 入口节点
        """
        self.graph.set_entry_point(entry_node)

    def add_finish_point(self, finish_node: str = END) -> None:
        """
        添加完成点

        Args:
            finish_node: 完成节点
        """
        self.graph.set_finish_point(finish_node)

    def compile(self) -> Any:
        """
        编译图

        Returns:
            编译后的图
        """
        try:
            compiled_graph = self.graph.compile()
            logger.info(f"图编译完成: {self.graph_name}, 节点数: {len(self.nodes)}, 边数: {len(self.edges)}")
            return compiled_graph
        except Exception as e:
            logger.error(f"图编译失败: {e}")
            raise

    def create_intent_classification_node(self) -> Callable:
        """
        创建意图分类节点

        Returns:
            意图分类节点函数
        """
        async def intent_classification_node(state: AgentState) -> Dict[str, Any]:
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

        return intent_classification_node

    def create_agent_routing_node(self) -> Callable:
        """
        创建智能体路由节点

        Returns:
            智能体路由节点函数
        """
        async def agent_routing_node(state: AgentState) -> Dict[str, Any]:
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

        return agent_routing_node

    def create_tool_execution_node(self) -> Callable:
        """
        创建工具执行节点

        Returns:
            工具执行节点函数
        """
        async def tool_execution_node(state: AgentState) -> Dict[str, Any]:
            """
            工具执行节点

            Args:
                state: 当前状态

            Returns:
                更新后的状态
            """
            try:
                tool_calls = state.get("tool_calls", [])
                if not tool_calls:
                    logger.debug("没有工具调用需要执行")
                    return {"tool_results": []}

                tool_results = []
                for tool_call in tool_calls:
                    try:
                        tool_name = tool_call.get("tool_name")
                        tool_input = tool_call.get("tool_input", {})
                        tool_id = tool_call.get("tool_call_id", f"tool_{tool_name}_{len(tool_results)}")

                        logger.info(f"执行工具: {tool_name}, 输入: {tool_input}")

                        # 获取工具
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

                        # 执行工具
                        result = await tool.execute(tool_input)

                        tool_results.append({
                            "tool_call_id": tool_id,
                            "tool_name": tool_name,
                            "result": result,
                            "is_error": False,
                            "execution_time": result.get("execution_time", 0) if isinstance(result, dict) else 0,
                        })

                        logger.info(f"工具执行成功: {tool_name}")

                    except Exception as e:
                        logger.error(f"工具执行失败: {tool_name}, 错误: {e}")
                        tool_results.append({
                            "tool_call_id": tool_call.get("tool_call_id", "unknown"),
                            "tool_name": tool_name,
                            "result": None,
                            "is_error": True,
                            "error_message": str(e),
                        })

                return {
                    "tool_results": tool_results,
                    "tool_calls": [],  # 清空待执行的工具调用
                    "metadata": {
                        **state.get("metadata", {}),
                        "tool_execution": {
                            "total_calls": len(tool_calls),
                            "successful_calls": len([r for r in tool_results if not r.get("is_error", False)]),
                            "failed_calls": len([r for r in tool_results if r.get("is_error", False)]),
                            "execution_timestamp": datetime.now().isoformat(),
                        }
                    }
                }

            except Exception as e:
                logger.error(f"工具执行节点执行失败: {e}")
                return {
                    "tool_results": [],
                    "tool_calls": state.get("tool_calls", []),  # 保留原始工具调用
                    "metadata": {
                        **state.get("metadata", {}),
                        "tool_execution_error": str(e),
                    }
                }

        return tool_execution_node

    def create_human_intervention_node(self) -> Callable:
        """
        创建人工干预节点

        Returns:
            人工干预节点函数
        """
        async def human_intervention_node(state: AgentState) -> Dict[str, Any]:
            """
            人工干预节点

            Args:
                state: 当前状态

            Returns:
                更新后的状态
            """
            try:
                # 检查是否需要人工干预
                requires_intervention = False
                intervention_reason = None

                # 规则1: 敏感操作（如删除文件、修改数据库）
                tool_calls = state.get("tool_calls", [])
                for tool_call in tool_calls:
                    tool_name = tool_call.get("tool_name", "")
                    if any(sensitive in tool_name.lower() for sensitive in ["delete", "remove", "drop", "update", "modify"]):
                        requires_intervention = True
                        intervention_reason = f"敏感工具调用: {tool_name}"
                        break

                # 规则2: 多次工具调用失败
                tool_results = state.get("tool_results", [])
                failed_calls = [r for r in tool_results if r.get("is_error", False)]
                if len(failed_calls) >= 3:
                    requires_intervention = True
                    intervention_reason = f"多次工具调用失败: {len(failed_calls)}次"

                # 规则3: 低置信度意图
                intent_confidence = state.get("intent_confidence", 0.0)
                if intent_confidence < settings.INTENT_REDIRECT_THRESHOLD:
                    requires_intervention = True
                    intervention_reason = f"意图置信度过低: {intent_confidence:.2f} < {settings.INTENT_REDIRECT_THRESHOLD}"

                if not requires_intervention:
                    logger.debug("不需要人工干预")
                    return {
                        "metadata": {
                            **state.get("metadata", {}),
                            "human_intervention": {
                                "required": False,
                                "reason": None,
                                "timestamp": datetime.now().isoformat(),
                            }
                        }
                    }

                logger.info(f"需要人工干预: {intervention_reason}")

                # 在实际应用中，这里应该触发人工干预流程
                # 例如：发送通知、等待审批、记录审计日志等

                return {
                    "metadata": {
                        **state.get("metadata", {}),
                        "human_intervention": {
                            "required": True,
                            "reason": intervention_reason,
                            "timestamp": datetime.now().isoformat(),
                            "session_id": state.get("session_id"),
                            "user_id": state.get("user_id"),
                            "intervention_data": {
                                "tool_calls": tool_calls,
                                "failed_tool_results": failed_calls,
                                "intent_confidence": intent_confidence,
                            }
                        }
                    }
                }

            except Exception as e:
                logger.error(f"人工干预节点执行失败: {e}")
                return {
                    "metadata": {
                        **state.get("metadata", {}),
                        "human_intervention_error": str(e),
                    }
                }

        return human_intervention_node


class GraphRegistry:
    """图注册表"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._graphs: Dict[str, Any] = {}
            cls._instance._graph_builders: Dict[str, BaseGraphBuilder] = {}
        return cls._instance

    def register_graph(self, graph_name: str, graph: Any) -> None:
        """
        注册图

        Args:
            graph_name: 图名称
            graph: 图对象
        """
        self._graphs[graph_name] = graph
        logger.info(f"图已注册: {graph_name}")

    def get_graph(self, graph_name: str) -> Optional[Any]:
        """
        获取图

        Args:
            graph_name: 图名称

        Returns:
            图对象或None
        """
        return self._graphs.get(graph_name)

    def create_workflow_graph(self, workflow_name: str = "default_workflow") -> Any:
        """
        创建工作流图

        Args:
            workflow_name: 工作流名称

        Returns:
            编译后的图
        """
        if workflow_name in self._graphs:
            logger.info(f"使用缓存的图: {workflow_name}")
            return self._graphs[workflow_name]

        try:
            builder = BaseGraphBuilder(graph_name=workflow_name)

            # 创建节点
            intent_node = builder.create_intent_classification_node()
            routing_node = builder.create_agent_routing_node()
            tool_node = builder.create_tool_execution_node()
            intervention_node = builder.create_human_intervention_node()

            # 添加节点
            builder.add_node("intent_classification", intent_node)
            builder.add_node("agent_routing", routing_node)
            builder.add_node("tool_execution", tool_node)
            builder.add_node("human_intervention", intervention_node)

            # 添加边
            builder.add_entry_point("intent_classification")
            builder.add_edge("intent_classification", "agent_routing")
            builder.add_edge("agent_routing", "tool_execution")
            builder.add_edge("tool_execution", "human_intervention")
            builder.add_finish_point()

            # 编译图
            graph = builder.compile()

            # 注册图
            self.register_graph(workflow_name, graph)

            return graph

        except Exception as e:
            logger.error(f"创建工作流图失败: {e}")
            raise


# 全局图注册表实例
graph_registry = GraphRegistry()