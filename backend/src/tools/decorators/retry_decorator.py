"""
重试装饰器
为工具调用提供重试机制，支持指数退避策略
"""
import logging
import asyncio
import time
from typing import Callable, Any, Optional, Type, Tuple, List
from functools import wraps
from datetime import datetime

from config.settings import settings

logger = logging.getLogger(__name__)


class RetryConfig:
    """重试配置类"""

    def __init__(
        self,
        max_attempts: int = None,
        backoff_factor: float = None,
        max_delay: float = 60.0,
        retry_on_exceptions: Tuple[Type[Exception], ...] = None,
        jitter: bool = True,
    ):
        """
        初始化重试配置

        Args:
            max_attempts: 最大重试次数（包含第一次调用）
            backoff_factor: 退避因子，延迟时间 = backoff_factor * (2^(attempt-1))
            max_delay: 最大延迟时间（秒）
            retry_on_exceptions: 需要重试的异常类型
            jitter: 是否添加随机抖动，避免惊群效应
        """
        self.max_attempts = max_attempts or settings.TOOL_RETRY_MAX_ATTEMPTS
        self.backoff_factor = backoff_factor or settings.TOOL_RETRY_BACKOFF_FACTOR
        self.max_delay = max_delay
        self.retry_on_exceptions = retry_on_exceptions or (Exception,)
        self.jitter = jitter

    def calculate_delay(self, attempt: int) -> float:
        """
        计算重试延迟

        Args:
            attempt: 当前尝试次数（从0开始）

        Returns:
            float: 延迟时间（秒）
        """
        if attempt <= 0:
            return 0

        # 指数退避：delay = factor * 2^(attempt-1)
        delay = self.backoff_factor * (2 ** (attempt - 1))

        # 添加随机抖动（±10%）
        if self.jitter:
            import random
            jitter_factor = random.uniform(0.9, 1.1)
            delay *= jitter_factor

        # 限制最大延迟
        return min(delay, self.max_delay)


def retry(config: Optional[RetryConfig] = None):
    """
    重试装饰器工厂函数

    Args:
        config: 重试配置，如果为None则使用默认配置

    Returns:
        装饰器函数
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable):
        """
        重试装饰器

        Args:
            func: 被装饰的函数

        Returns:
            包装后的函数
        """
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            """异步函数包装器"""
            last_exception = None
            start_time = time.time()

            for attempt in range(config.max_attempts):
                try:
                    # 如果不是第一次尝试，等待延迟
                    if attempt > 0:
                        delay = config.calculate_delay(attempt)
                        logger.info(
                            f"工具重试: {func.__name__}, 尝试 {attempt + 1}/{config.max_attempts}, "
                            f"延迟 {delay:.2f} 秒"
                        )
                        await asyncio.sleep(delay)

                    # 执行函数
                    result = await func(*args, **kwargs)

                    # 如果成功，记录统计信息
                    if attempt > 0:
                        total_time = time.time() - start_time
                        logger.info(
                            f"工具重试成功: {func.__name__}, "
                            f"经过 {attempt} 次重试, 总耗时 {total_time:.2f} 秒"
                        )

                    return result

                except Exception as e:
                    last_exception = e

                    # 检查是否是需要重试的异常
                    if not isinstance(e, config.retry_on_exceptions):
                        logger.warning(
                            f"工具调用遇到非重试异常，停止重试: {func.__name__}, "
                            f"异常类型: {type(e).__name__}, 错误: {str(e)}"
                        )
                        raise

                    # 记录重试信息
                    logger.warning(
                        f"工具调用失败，准备重试: {func.__name__}, "
                        f"尝试 {attempt + 1}/{config.max_attempts}, "
                        f"异常: {type(e).__name__}, 错误: {str(e)[:100]}"
                    )

                    # 如果是最后一次尝试，则抛出异常
                    if attempt == config.max_attempts - 1:
                        total_time = time.time() - start_time
                        logger.error(
                            f"工具重试耗尽: {func.__name__}, "
                            f"{config.max_attempts} 次尝试全部失败, "
                            f"总耗时 {total_time:.2f} 秒, "
                            f"最后异常: {type(last_exception).__name__}: {str(last_exception)}"
                        )
                        raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            """同步函数包装器"""
            last_exception = None
            start_time = time.time()

            for attempt in range(config.max_attempts):
                try:
                    # 如果不是第一次尝试，等待延迟
                    if attempt > 0:
                        delay = config.calculate_delay(attempt)
                        logger.info(
                            f"工具重试: {func.__name__}, 尝试 {attempt + 1}/{config.max_attempts}, "
                            f"延迟 {delay:.2f} 秒"
                        )
                        time.sleep(delay)

                    # 执行函数
                    result = func(*args, **kwargs)

                    # 如果成功，记录统计信息
                    if attempt > 0:
                        total_time = time.time() - start_time
                        logger.info(
                            f"工具重试成功: {func.__name__}, "
                            f"经过 {attempt} 次重试, 总耗时 {total_time:.2f} 秒"
                        )

                    return result

                except Exception as e:
                    last_exception = e

                    # 检查是否是需要重试的异常
                    if not isinstance(e, config.retry_on_exceptions):
                        logger.warning(
                            f"工具调用遇到非重试异常，停止重试: {func.__name__}, "
                            f"异常类型: {type(e).__name__}, 错误: {str(e)}"
                        )
                        raise

                    # 记录重试信息
                    logger.warning(
                        f"工具调用失败，准备重试: {func.__name__}, "
                        f"尝试 {attempt + 1}/{config.max_attempts}, "
                        f"异常: {type(e).__name__}, 错误: {str(e)[:100]}"
                    )

                    # 如果是最后一次尝试，则抛出异常
                    if attempt == config.max_attempts - 1:
                        total_time = time.time() - start_time
                        logger.error(
                            f"工具重试耗尽: {func.__name__}, "
                            f"{config.max_attempts} 次尝试全部失败, "
                            f"总耗时 {total_time:.2f} 秒, "
                            f"最后异常: {type(last_exception).__name__}: {str(last_exception)}"
                        )
                        raise

        # 根据函数类型返回相应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def retry_with_config(
    max_attempts: int = None,
    backoff_factor: float = None,
    max_delay: float = 60.0,
    retry_on_exceptions: Tuple[Type[Exception], ...] = None,
    jitter: bool = True,
):
    """
    带参数的重试装饰器快捷函数

    Args:
        max_attempts: 最大重试次数
        backoff_factor: 退避因子
        max_delay: 最大延迟时间
        retry_on_exceptions: 需要重试的异常类型
        jitter: 是否添加随机抖动

    Returns:
        装饰器函数
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        backoff_factor=backoff_factor,
        max_delay=max_delay,
        retry_on_exceptions=retry_on_exceptions,
        jitter=jitter,
    )
    return retry(config)


class RetryStatistics:
    """重试统计管理器"""

    def __init__(self):
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "retried_calls": 0,
            "total_retries": 0,
            "total_time_saved": 0.0,
            "tool_stats": {},
        }

    def record_call(
        self,
        tool_name: str,
        success: bool,
        retry_count: int,
        execution_time: float,
    ):
        """
        记录调用统计

        Args:
            tool_name: 工具名称
            success: 是否成功
            retry_count: 重试次数
            execution_time: 执行时间
        """
        self.stats["total_calls"] += 1

        if success:
            self.stats["successful_calls"] += 1
        else:
            self.stats["failed_calls"] += 1

        if retry_count > 0:
            self.stats["retried_calls"] += 1
            self.stats["total_retries"] += retry_count

        # 更新工具特定统计
        if tool_name not in self.stats["tool_stats"]:
            self.stats["tool_stats"][tool_name] = {
                "calls": 0,
                "successes": 0,
                "failures": 0,
                "retries": 0,
                "total_time": 0.0,
            }

        tool_stat = self.stats["tool_stats"][tool_name]
        tool_stat["calls"] += 1
        tool_stat["total_time"] += execution_time

        if success:
            tool_stat["successes"] += 1
        else:
            tool_stat["failures"] += 1

        tool_stat["retries"] += retry_count

    def get_stats(self) -> dict:
        """
        获取统计信息

        Returns:
            dict: 统计信息
        """
        stats = self.stats.copy()

        # 计算成功率
        if stats["total_calls"] > 0:
            stats["success_rate"] = (
                stats["successful_calls"] / stats["total_calls"] * 100
            )
        else:
            stats["success_rate"] = 0.0

        # 计算平均重试次数
        if stats["retried_calls"] > 0:
            stats["average_retries_per_retried_call"] = (
                stats["total_retries"] / stats["retried_calls"]
            )
        else:
            stats["average_retries_per_retried_call"] = 0.0

        return stats

    def reset(self):
        """重置统计信息"""
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "retried_calls": 0,
            "total_retries": 0,
            "total_time_saved": 0.0,
            "tool_stats": {},
        }


# 全局重试统计实例
retry_statistics = RetryStatistics()


def retry_with_stats(config: Optional[RetryConfig] = None):
    """
    带统计的重试装饰器

    Args:
        config: 重试配置

    Returns:
        装饰器函数
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            """异步函数包装器（带统计）"""
            last_exception = None
            start_time = time.time()
            retry_count = 0

            for attempt in range(config.max_attempts):
                try:
                    # 如果不是第一次尝试，等待延迟
                    if attempt > 0:
                        delay = config.calculate_delay(attempt)
                        retry_count += 1
                        await asyncio.sleep(delay)

                    # 执行函数
                    result = await func(*args, **kwargs)

                    # 记录成功统计
                    execution_time = time.time() - start_time
                    retry_statistics.record_call(
                        tool_name=func.__name__,
                        success=True,
                        retry_count=retry_count,
                        execution_time=execution_time,
                    )

                    return result

                except Exception as e:
                    last_exception = e

                    # 检查是否是需要重试的异常
                    if not isinstance(e, config.retry_on_exceptions):
                        # 记录失败统计（非重试异常）
                        execution_time = time.time() - start_time
                        retry_statistics.record_call(
                            tool_name=func.__name__,
                            success=False,
                            retry_count=retry_count,
                            execution_time=execution_time,
                        )
                        raise

                    # 如果是最后一次尝试，记录失败统计并抛出异常
                    if attempt == config.max_attempts - 1:
                        execution_time = time.time() - start_time
                        retry_statistics.record_call(
                            tool_name=func.__name__,
                            success=False,
                            retry_count=retry_count,
                            execution_time=execution_time,
                        )
                        raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            """同步函数包装器（带统计）"""
            last_exception = None
            start_time = time.time()
            retry_count = 0

            for attempt in range(config.max_attempts):
                try:
                    # 如果不是第一次尝试，等待延迟
                    if attempt > 0:
                        delay = config.calculate_delay(attempt)
                        retry_count += 1
                        time.sleep(delay)

                    # 执行函数
                    result = func(*args, **kwargs)

                    # 记录成功统计
                    execution_time = time.time() - start_time
                    retry_statistics.record_call(
                        tool_name=func.__name__,
                        success=True,
                        retry_count=retry_count,
                        execution_time=execution_time,
                    )

                    return result

                except Exception as e:
                    last_exception = e

                    # 检查是否是需要重试的异常
                    if not isinstance(e, config.retry_on_exceptions):
                        # 记录失败统计（非重试异常）
                        execution_time = time.time() - start_time
                        retry_statistics.record_call(
                            tool_name=func.__name__,
                            success=False,
                            retry_count=retry_count,
                            execution_time=execution_time,
                        )
                        raise

                    # 如果是最后一次尝试，记录失败统计并抛出异常
                    if attempt == config.max_attempts - 1:
                        execution_time = time.time() - start_time
                        retry_statistics.record_call(
                            tool_name=func.__name__,
                            success=False,
                            retry_count=retry_count,
                            execution_time=execution_time,
                        )
                        raise

        # 根据函数类型返回相应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator