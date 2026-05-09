"""
工具装饰器模块
提供重试、熔断、降级等弹性模式装饰器
"""
from .retry_decorator import (
    retry, retry_with_config, retry_with_stats,
    RetryConfig, RetryStatistics, retry_statistics
)
from .circuit_breaker import (
    circuit_breaker, circuit_breaker_with_config,
    CircuitBreakerConfig, CircuitBreaker, CircuitState,
    circuit_breaker_registry
)
from .fallback_decorator import (
    fallback, fallback_default_value, fallback_alternative,
    fallback_cached, fallback_with_condition, resilient_tool,
    FallbackConfig, FallbackStrategy, FallbackHandler, fallback_registry
)

__all__ = [
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