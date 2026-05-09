"""
工具注册表
"""
import logging
import time
from typing import Dict, List, Optional, Any

from tools.base_tool import BaseTool, ToolMetadata, ToolOutput
from tools.tool_result import ToolResult, ResultStatus

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    工具注册表
    管理所有可用工具的注册和发现
    """

    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}
        self.tool_stats: Dict[str, Dict[str, Any]] = {}
        self._initialized = False

    def initialize(self):
        """
        初始化工具注册表
        """
        if self._initialized:
            return

        try:
            self._register_default_tools()
            self._initialized = True
            logger.info("工具注册表初始化完成")
            logger.info(f"已注册工具: {list(self.tools.keys())}")

        except Exception as e:
            logger.error(f"工具注册表初始化失败: {e}", exc_info=True)
            raise

    def _register_default_tools(self):
        """注册默认工具"""
        from tools.implementations.calculator_tool import CalculatorTool
        from tools.implementations.web_search_tool import WebSearchTool
        from tools.implementations.file_operations_tool import FileOperationsTool

        self.register_tool(CalculatorTool())
        self.register_tool(WebSearchTool())
        self.register_tool(FileOperationsTool())

    def register_tool(self, tool: BaseTool):
        """
        注册工具

        Args:
            tool: 工具实例
        """
        tool_name = tool.metadata.name

        if tool_name in self.tools:
            logger.warning(f"工具已存在，将覆盖: {tool_name}")

        self.tools[tool_name] = tool
        self.tool_stats[tool_name] = {
            "call_count": 0,
            "success_count": 0,
            "error_count": 0,
            "total_execution_time": 0.0,
            "last_called": None,
        }

        logger.info(f"工具注册成功: {tool_name}")

    def unregister_tool(self, tool_name: str):
        """
        注销工具

        Args:
            tool_name: 工具名称
        """
        if tool_name in self.tools:
            tool = self.tools.pop(tool_name)
            self.tool_stats.pop(tool_name, None)

            logger.info(f"工具注销成功: {tool_name}")

            try:
                # base_tool.BaseTool 没有 cleanup 抽象方法，尝试调用
                if hasattr(tool, 'cleanup'):
                    tool.cleanup()
            except Exception as e:
                logger.error(f"清理工具资源失败: {tool_name}, error={e}")

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """
        获取工具

        Args:
            tool_name: 工具名称

        Returns:
            Optional[BaseTool]: 工具实例，如果不存在则返回None
        """
        return self.tools.get(tool_name)

    def list_tools(
        self,
        tag: Optional[str] = None,
        require_auth: Optional[bool] = None,
    ) -> List[BaseTool]:
        """
        列出工具

        Args:
            tag: 标签过滤
            require_auth: 是否需要认证过滤

        Returns:
            List[BaseTool]: 工具列表
        """
        from tools.base_tool import ToolPermission

        filtered_tools = []

        for tool in self.tools.values():
            if tag and tag not in tool.metadata.tags:
                continue

            if require_auth is not None:
                tool_requires_auth = ToolPermission.PUBLIC not in tool.metadata.permissions
                if tool_requires_auth != require_auth:
                    continue

            filtered_tools.append(tool)

        return filtered_tools

    async def call_tool(self, tool_name: str, input_data: Dict[str, Any]) -> ToolResult:
        """
        调用工具

        Args:
            tool_name: 工具名称
            input_data: 输入数据

        Returns:
            ToolResult: 工具调用结果
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult(
                status=ResultStatus.FAILURE,
                message=f"工具不存在: {tool_name}",
                error_code="TOOL_NOT_FOUND",
            )

        try:
            start_time = time.time()

            output = await tool.execute(input_data)
            execution_time = time.time() - start_time

            self._update_tool_stats(tool_name, output.success, execution_time)

            return ToolResult(
                status=ResultStatus.SUCCESS if output.success else ResultStatus.FAILURE,
                message=output.message,
                data=output.data,
                error_code=output.error_code,
                execution_time=execution_time,
            )

        except Exception as e:
            logger.error(f"工具调用失败: {tool_name}, error={e}", exc_info=True)
            self._update_tool_stats(tool_name, False, 0)

            return ToolResult(
                status=ResultStatus.FAILURE,
                message=f"工具调用异常: {str(e)}",
                error_code="TOOL_EXECUTION_ERROR",
            )

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            Dict[str, Any]: 健康状态信息
        """
        try:
            total_tools = len(self.tools)
            healthy_tools = 0
            tool_health = {}

            for tool_name in self.tools:
                try:
                    # base_tool.BaseTool 没有抽象 health_check，尝试调用
                    if hasattr(self.tools[tool_name], 'health_check'):
                        status = self.tools[tool_name].health_check()
                        tool_health[tool_name] = status
                        if status.get("status") == "healthy":
                            healthy_tools += 1
                    else:
                        tool_health[tool_name] = {"status": "healthy", "note": "no health_check method"}
                        healthy_tools += 1
                except Exception as e:
                    logger.error(f"工具健康检查失败: {tool_name}, error={e}")
                    tool_health[tool_name] = {"status": "error", "error": str(e)}

            return {
                "status": "healthy" if healthy_tools == total_tools > 0 else "unhealthy",
                "total_tools": total_tools,
                "healthy_tools": healthy_tools,
                "tools": tool_health,
            }

        except Exception as e:
            logger.error(f"工具注册表健康检查失败: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    def get_tool_stats(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        获取工具统计信息

        Args:
            tool_name: 工具名称

        Returns:
            Optional[Dict[str, Any]]: 工具统计信息
        """
        return self.tool_stats.get(tool_name)

    def list_tool_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        列出所有工具统计信息

        Returns:
            Dict[str, Dict[str, Any]]: 工具统计信息字典
        """
        return self.tool_stats.copy()

    def _update_tool_stats(self, tool_name: str, success: bool, execution_time: float):
        """
        更新工具统计信息

        Args:
            tool_name: 工具名称
            success: 是否成功
            execution_time: 执行时间
        """
        if tool_name not in self.tool_stats:
            self.tool_stats[tool_name] = {
                "call_count": 0,
                "success_count": 0,
                "error_count": 0,
                "total_execution_time": 0.0,
                "last_called": None,
            }

        stats = self.tool_stats[tool_name]
        stats["call_count"] += 1
        if success:
            stats["success_count"] += 1
        else:
            stats["error_count"] += 1
        stats["total_execution_time"] += execution_time
        stats["last_called"] = time.time()

        if stats["call_count"] > 0:
            stats["avg_execution_time"] = stats["total_execution_time"] / stats["call_count"]

    def search_tools(self, query: str) -> List[BaseTool]:
        """
        搜索工具

        Args:
            query: 搜索查询

        Returns:
            List[BaseTool]: 搜索结果
        """
        query_lower = query.lower()
        results = []

        for tool in self.tools.values():
            if query_lower in tool.metadata.name.lower():
                results.append(tool)
                continue

            if query_lower in tool.metadata.description.lower():
                results.append(tool)
                continue

            for tag in tool.metadata.tags:
                if query_lower in tag.lower():
                    results.append(tool)
                    break

        return results


# 全局工具注册表实例
tool_registry = ToolRegistry()
