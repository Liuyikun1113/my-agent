"""
工具系统模块
"""
from .registry import tool_registry
from .base_tool import (
    BaseTool, ToolMetadata, ToolCategory, ToolPermission,
    ToolError, ToolOutput, ToolInput, ToolFactory,
    tool as tool_decorator
)
from .tool_result import (
    ToolResult, ToolResultBuilder, ToolResultProcessor,
    ResultStatus, ExecutionContext
)
from .decorators.retry_decorator import (
    retry, retry_with_config, retry_with_stats,
    RetryConfig, RetryStatistics, retry_statistics
)
from .decorators.circuit_breaker import (
    circuit_breaker, circuit_breaker_with_config,
    CircuitBreakerConfig, CircuitBreaker, CircuitState,
    circuit_breaker_registry
)
from .decorators.fallback_decorator import (
    fallback, fallback_default_value, fallback_alternative,
    fallback_cached, fallback_with_condition, resilient_tool,
    FallbackConfig, FallbackStrategy, FallbackHandler, fallback_registry
)

# 导入实现
try:
    from .implementations.calculator_tool import CalculatorTool, CalculatorInput
    from .implementations.web_search_tool import WebSearchTool, SearchQuery, SearchResult
    from .implementations.file_operations_tool import (
        FileOperationsTool, FileReadRequest, FileWriteRequest, FileInfo
    )
    HAS_IMPLEMENTATIONS = True
except ImportError:
    HAS_IMPLEMENTATIONS = False

__all__ = [
    # 注册表
    "tool_registry",

    # 基类和接口
    "BaseTool", "ToolMetadata", "ToolCategory", "ToolPermission",
    "ToolError", "ToolOutput", "ToolInput", "ToolFactory",
    "tool_decorator",

    # 结果处理
    "ToolResult", "ToolResultBuilder", "ToolResultProcessor",
    "ResultStatus", "ExecutionContext",

    # 重试装饰器
    "retry", "retry_with_config", "retry_with_stats",
    "RetryConfig", "RetryStatistics", "retry_statistics",

    # 熔断器装饰器
    "circuit_breaker", "circuit_breaker_with_config",
    "CircuitBreakerConfig", "CircuitBreaker", "CircuitState",
    "circuit_breaker_registry",

    # 降级装饰器
    "fallback", "fallback_default_value", "fallback_alternative",
    "fallback_cached", "fallback_with_condition", "resilient_tool",
    "FallbackConfig", "FallbackStrategy", "FallbackHandler", "fallback_registry",
]

if HAS_IMPLEMENTATIONS:
    __all__.extend([
        "CalculatorTool", "CalculatorInput",
        "WebSearchTool", "SearchQuery", "SearchResult",
        "FileOperationsTool", "FileReadRequest", "FileWriteRequest", "FileInfo",
    ])