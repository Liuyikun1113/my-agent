"""
降级装饰器
为工具调用提供降级机制，在主功能失败时提供备用方案
"""
import logging
import asyncio
import inspect
from typing import Callable, Any, Optional, Union, Type, Tuple, List, Dict
from functools import wraps
from enum import Enum, auto

from config.settings import settings

logger = logging.getLogger(__name__)


class FallbackStrategy(Enum):
    """降级策略"""
    NONE = auto()           # 无降级，直接抛出异常
    DEFAULT_VALUE = auto()  # 返回默认值
    ALTERNATIVE_FUNC = auto()  # 调用备用函数
    CACHED_VALUE = auto()   # 返回缓存值
    RETRY_THEN_FALLBACK = auto()  # 先重试，失败后降级


@dataclass
class FallbackConfig:
    """降级配置"""

    # 降级策略
    strategy: FallbackStrategy = FallbackStrategy.DEFAULT_VALUE

    # 默认值策略配置
    default_value: Any = None

    # 备用函数策略配置
    alternative_func: Optional[Callable] = None
    alternative_func_args: Optional[tuple] = None
    alternative_func_kwargs: Optional[dict] = None

    # 缓存策略配置
    cache_key: Optional[str] = None
    cache_ttl: int = 300  # 缓存TTL（秒）

    # 异常类型配置
    fallback_on_exceptions: Tuple[Type[Exception], ...] = (Exception,)

    # 条件降级配置
    condition_func: Optional[Callable] = None  # 返回bool，True表示需要降级

    # 日志配置
    log_fallback: bool = True


class FallbackHandler:
    """降级处理器"""

    def __init__(self, config: FallbackConfig):
        self.config = config
        self.cache = {}  # 简单的内存缓存，实际使用时应使用Redis等外部缓存

    async def execute_with_fallback(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        执行函数并应用降级策略

        Args:
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数

        Returns:
            函数结果或降级结果
        """
        try:
            # 检查是否需要降级（条件降级）
            if self.config.condition_func and self.config.condition_func():
                logger.info(f"条件降级触发: {func.__name__}")
                return await self._execute_fallback(func, *args, **kwargs)

            # 执行主函数
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            return result

        except Exception as e:
            # 检查是否是需要降级的异常类型
            if not isinstance(e, self.config.fallback_on_exceptions):
                logger.warning(
                    f"遇到非降级异常，不执行降级: {func.__name__}, "
                    f"异常类型: {type(e).__name__}"
                )
                raise

            # 执行降级
            logger.warning(
                f"执行降级: {func.__name__}, "
                f"异常: {type(e).__name__}: {str(e)[:100]}"
            )
            return await self._execute_fallback(func, *args, **kwargs, exception=e)

    async def _execute_fallback(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """执行降级逻辑"""
        exception = kwargs.pop('exception', None)

        if self.config.strategy == FallbackStrategy.NONE:
            if exception:
                raise exception
            else:
                raise Exception(f"函数执行失败且未配置降级策略: {func.__name__}")

        elif self.config.strategy == FallbackStrategy.DEFAULT_VALUE:
            result = self.config.default_value
            self._log_fallback(func.__name__, "默认值降级", result)
            return result

        elif self.config.strategy == FallbackStrategy.ALTERNATIVE_FUNC:
            if not self.config.alternative_func:
                raise ValueError("备用函数未配置")

            try:
                alt_func = self.config.alternative_func
                alt_args = self.config.alternative_func_args or ()
                alt_kwargs = self.config.alternative_func_kwargs or {}

                if asyncio.iscoroutinefunction(alt_func):
                    result = await alt_func(*alt_args, **alt_kwargs)
                else:
                    result = alt_func(*alt_args, **alt_kwargs)

                self._log_fallback(func.__name__, "备用函数降级", result)
                return result

            except Exception as e:
                logger.error(f"备用函数也失败: {func.__name__}, 异常: {str(e)}")
                # 备用函数失败，尝试默认值降级
                return self.config.default_value

        elif self.config.strategy == FallbackStrategy.CACHED_VALUE:
            if self.config.cache_key:
                # 从缓存获取
                cached_result = self.cache.get(self.config.cache_key)
                if cached_result is not None:
                    self._log_fallback(func.__name__, "缓存降级", cached_result)
                    return cached_result

            # 缓存未命中，返回默认值
            result = self.config.default_value
            self._log_fallback(func.__name__, "缓存降级（使用默认值）", result)
            return result

        elif self.config.strategy == FallbackStrategy.RETRY_THEN_FALLBACK:
            # 这里可以集成重试装饰器，先重试，失败后再降级
            # 简化实现：直接降级
            logger.info(f"重试-降级策略: {func.__name__}，直接执行降级")
            return await self._execute_fallback(func, *args, **kwargs)

        else:
            raise ValueError(f"未知的降级策略: {self.config.strategy}")

    def _log_fallback(self, func_name: str, strategy: str, result: Any):
        """记录降级日志"""
        if self.config.log_fallback:
            logger.info(
                f"降级执行完成: {func_name}, "
                f"策略: {strategy}, "
                f"结果类型: {type(result).__name__}"
            )

    def set_cache(self, key: str, value: Any, ttl: Optional[int] = None):
        """设置缓存值"""
        self.cache[key] = value
        # 在实际应用中，这里应该设置TTL
        # 简化实现：只存储，不实现TTL清理

    def get_cache(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        return self.cache.get(key)

    def clear_cache(self, key: Optional[str] = None):
        """清理缓存"""
        if key:
            self.cache.pop(key, None)
        else:
            self.cache.clear()


def fallback(config: Optional[FallbackConfig] = None):
    """
    降级装饰器工厂函数

    Args:
        config: 降级配置

    Returns:
        装饰器函数
    """
    if config is None:
        config = FallbackConfig()

    def decorator(func: Callable):
        handler = FallbackHandler(config)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            """异步函数包装器"""
            return await handler.execute_with_fallback(func, *args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            """同步函数包装器"""
            # 对于同步函数，我们仍然使用异步处理器，但同步执行
            async def async_execute():
                return await handler.execute_with_fallback(func, *args, **kwargs)

            # 运行异步函数
            try:
                import asyncio
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # 如果没有事件循环，创建一个新的
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            return loop.run_until_complete(async_execute())

        # 根据函数类型返回相应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# 快捷装饰器函数

def fallback_default_value(default_value: Any, exceptions: Tuple[Type[Exception], ...] = (Exception,)):
    """
    默认值降级装饰器

    Args:
        default_value: 默认值
        exceptions: 触发降级的异常类型

    Returns:
        装饰器函数
    """
    config = FallbackConfig(
        strategy=FallbackStrategy.DEFAULT_VALUE,
        default_value=default_value,
        fallback_on_exceptions=exceptions,
    )
    return fallback(config)


def fallback_alternative(
    alternative_func: Callable,
    alt_args: Optional[tuple] = None,
    alt_kwargs: Optional[dict] = None,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    备用函数降级装饰器

    Args:
        alternative_func: 备用函数
        alt_args: 备用函数参数
        alt_kwargs: 备用函数关键字参数
        exceptions: 触发降级的异常类型

    Returns:
        装饰器函数
    """
    config = FallbackConfig(
        strategy=FallbackStrategy.ALTERNATIVE_FUNC,
        alternative_func=alternative_func,
        alternative_func_args=alt_args,
        alternative_func_kwargs=alt_kwargs,
        fallback_on_exceptions=exceptions,
    )
    return fallback(config)


def fallback_cached(
    cache_key: str,
    default_value: Any,
    cache_ttl: int = 300,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    缓存降级装饰器

    Args:
        cache_key: 缓存键
        default_value: 默认值（缓存未命中时使用）
        cache_ttl: 缓存TTL（秒）
        exceptions: 触发降级的异常类型

    Returns:
        装饰器函数
    """
    config = FallbackConfig(
        strategy=FallbackStrategy.CACHED_VALUE,
        cache_key=cache_key,
        default_value=default_value,
        cache_ttl=cache_ttl,
        fallback_on_exceptions=exceptions,
    )
    return fallback(config)


def fallback_with_condition(
    condition_func: Callable,
    default_value: Any,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    条件降级装饰器

    Args:
        condition_func: 条件函数，返回True时触发降级
        default_value: 默认值
        exceptions: 触发降级的异常类型

    Returns:
        装饰器函数
    """
    config = FallbackConfig(
        strategy=FallbackStrategy.DEFAULT_VALUE,
        default_value=default_value,
        fallback_on_exceptions=exceptions,
        condition_func=condition_func,
    )
    return fallback(config)


class FallbackRegistry:
    """降级处理器注册表"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._handlers = {}
        return cls._instance

    def register_handler(self, name: str, handler: FallbackHandler):
        """注册降级处理器"""
        self._handlers[name] = handler

    def get_handler(self, name: str) -> Optional[FallbackHandler]:
        """获取降级处理器"""
        return self._handlers.get(name)

    def get_all_handlers(self) -> Dict[str, FallbackHandler]:
        """获取所有降级处理器"""
        return self._handlers.copy()

    def clear_all_caches(self):
        """清理所有处理器的缓存"""
        for handler in self._handlers.values():
            handler.clear_cache()


# 全局降级处理器注册表
fallback_registry = FallbackRegistry()


# 复合装饰器：重试 + 熔断 + 降级

def resilient_tool(
    retry_config=None,
    circuit_breaker_config=None,
    fallback_config=None,
    tool_name: Optional[str] = None,
):
    """
    复合弹性装饰器：集成重试、熔断和降级

    Args:
        retry_config: 重试配置
        circuit_breaker_config: 熔断器配置
        fallback_config: 降级配置
        tool_name: 工具名称

    Returns:
        装饰器函数
    """
    from .retry_decorator import retry_with_config as retry_decorator
    from .circuit_breaker import circuit_breaker_with_config as circuit_breaker_decorator

    def decorator(func: Callable):
        # 应用重试装饰器
        if retry_config is not None:
            if isinstance(retry_config, dict):
                func = retry_decorator(**retry_config)(func)
            else:
                func = retry_decorator()(func)

        # 应用熔断器装饰器
        if circuit_breaker_config is not None:
            cb_name = tool_name or func.__name__
            if isinstance(circuit_breaker_config, dict):
                func = circuit_breaker_decorator(
                    name=cb_name,
                    **circuit_breaker_config
                )(func)
            else:
                func = circuit_breaker_decorator(name=cb_name)(func)

        # 应用降级装饰器
        if fallback_config is not None:
            if isinstance(fallback_config, dict):
                # 从字典创建FallbackConfig
                config = FallbackConfig(**fallback_config)
                func = fallback(config)(func)
            else:
                func = fallback(fallback_config)(func)

        return func

    return decorator