"""
熔断器装饰器
为工具调用提供熔断机制，防止级联故障
"""
import logging
import time
import asyncio
from typing import Callable, Any, Optional, Type, Tuple
from functools import wraps
from enum import Enum, auto
from dataclasses import dataclass
from datetime import datetime, timedelta

from config.settings import settings

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = auto()      # 正常状态，请求可以通过
    OPEN = auto()        # 熔断状态，请求被拒绝
    HALF_OPEN = auto()   # 半开状态，允许部分请求通过以测试服务恢复情况


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""

    # 失败阈值配置
    failure_threshold: int = 5           # 触发熔断的连续失败次数
    failure_window: float = 60.0         # 统计失败的时间窗口（秒）

    # 熔断持续时间配置
    reset_timeout: float = 30.0          # 熔断器保持OPEN状态的时间（秒）

    # 半开状态配置
    half_open_max_requests: int = 3      # 半开状态允许的最大请求数
    half_open_success_threshold: int = 2 # 半开状态下恢复服务需要的最小成功数

    # 统计配置
    sliding_window_size: int = 100       # 滑动窗口大小，用于计算失败率


class CircuitBreaker:
    """熔断器实现"""

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        """
        初始化熔断器

        Args:
            name: 熔断器名称（通常为工具名称）
            config: 熔断器配置
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()

        # 状态变量
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.last_state_change_time: Optional[float] = time.time()

        # 统计变量
        self.total_requests = 0
        self.total_failures = 0
        self.total_successes = 0
        self.trip_count = 0

        # 滑动窗口
        self.request_window: list[tuple[float, bool]] = []  # (时间戳, 是否成功)

        logger.info(f"熔断器初始化: {name}, 配置: {self.config}")

    def _should_trip(self) -> bool:
        """检查是否应该触发熔断"""
        if self.state == CircuitState.OPEN:
            return True

        current_time = time.time()

        # 检查是否有超过时间窗口的失败记录
        if self.last_failure_time is not None:
            if current_time - self.last_failure_time > self.config.failure_window:
                # 失败记录已过期，重置计数器
                self.failure_count = 0
                self.last_failure_time = None

        # 检查失败次数是否超过阈值
        if self.failure_count >= self.config.failure_threshold:
            logger.warning(
                f"熔断器触发: {self.name}, "
                f"失败次数: {self.failure_count}/{self.config.failure_threshold}"
            )
            return True

        return False

    def _should_reset(self) -> bool:
        """检查是否应该重置熔断器（从OPEN到HALF_OPEN）"""
        if self.state != CircuitState.OPEN:
            return False

        current_time = time.time()
        time_in_open_state = current_time - self.last_state_change_time

        if time_in_open_state >= self.config.reset_timeout:
            logger.info(
                f"熔断器重置超时到达: {self.name}, "
                f"OPEN状态持续时间: {time_in_open_state:.1f}秒"
            )
            return True

        return False

    def _should_close(self) -> bool:
        """检查是否应该关闭熔断器（从HALF_OPEN到CLOSED）"""
        if self.state != CircuitState.HALF_OPEN:
            return False

        if self.success_count >= self.config.half_open_success_threshold:
            logger.info(
                f"熔断器恢复: {self.name}, "
                f"半开状态成功次数: {self.success_count}/{self.config.half_open_success_threshold}"
            )
            return True

        return False

    def record_success(self):
        """记录成功"""
        current_time = time.time()

        # 更新统计
        self.total_requests += 1
        self.total_successes += 1
        self.request_window.append((current_time, True))

        # 清理过期的窗口记录
        self._clean_window(current_time)

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            logger.debug(
                f"熔断器半开状态成功: {self.name}, "
                f"成功次数: {self.success_count}/{self.config.half_open_success_threshold}"
            )

        # 重置失败计数器
        self.failure_count = 0
        self.last_failure_time = None

        # 检查状态转换
        self._update_state()

    def record_failure(self):
        """记录失败"""
        current_time = time.time()

        # 更新统计
        self.total_requests += 1
        self.total_failures += 1
        self.request_window.append((current_time, False))

        # 清理过期的窗口记录
        self._clean_window(current_time)

        # 更新失败计数器
        self.failure_count += 1
        self.last_failure_time = current_time

        if self.state == CircuitState.HALF_OPEN:
            # 半开状态下失败，立即回到OPEN状态
            self.state = CircuitState.OPEN
            self.last_state_change_time = current_time
            self.success_count = 0
            self.trip_count += 1
            logger.warning(
                f"熔断器半开状态失败，重新熔断: {self.name}"
            )

        # 检查状态转换
        self._update_state()

    def _clean_window(self, current_time: float):
        """清理滑动窗口中的过期记录"""
        cutoff_time = current_time - self.config.failure_window
        self.request_window = [
            (ts, success) for ts, success in self.request_window
            if ts >= cutoff_time
        ]

    def _update_state(self):
        """更新熔断器状态"""
        current_time = time.time()

        if self.state == CircuitState.CLOSED:
            if self._should_trip():
                self.state = CircuitState.OPEN
                self.last_state_change_time = current_time
                self.trip_count += 1
                logger.error(f"熔断器已熔断: {self.name}, 状态: OPEN")

        elif self.state == CircuitState.OPEN:
            if self._should_reset():
                self.state = CircuitState.HALF_OPEN
                self.last_state_change_time = current_time
                self.success_count = 0
                logger.info(f"熔断器进入半开状态: {self.name}, 状态: HALF_OPEN")

        elif self.state == CircuitState.HALF_OPEN:
            if self._should_close():
                self.state = CircuitState.CLOSED
                self.last_state_change_time = current_time
                self.failure_count = 0
                self.success_count = 0
                logger.info(f"熔断器已关闭: {self.name}, 状态: CLOSED")

    def allow_request(self) -> bool:
        """检查是否允许请求通过"""
        current_time = time.time()

        # 检查状态转换
        self._update_state()

        if self.state == CircuitState.OPEN:
            logger.debug(f"熔断器拒绝请求: {self.name}, 状态: OPEN")
            return False

        if self.state == CircuitState.HALF_OPEN:
            # 检查半开状态下的请求限制
            half_open_requests = self.success_count + self.failure_count
            if half_open_requests >= self.config.half_open_max_requests:
                logger.debug(
                    f"熔断器半开状态请求限制: {self.name}, "
                    f"已处理请求: {half_open_requests}/{self.config.half_open_max_requests}"
                )
                return False

        return True

    def get_stats(self) -> dict:
        """获取熔断器统计信息"""
        current_time = time.time()

        # 计算失败率
        failure_rate = 0.0
        if self.total_requests > 0:
            failure_rate = self.total_failures / self.total_requests * 100

        # 计算窗口内失败率
        window_failure_rate = 0.0
        window_requests = len(self.request_window)
        if window_requests > 0:
            window_failures = sum(1 for _, success in self.request_window if not success)
            window_failure_rate = window_failures / window_requests * 100

        return {
            "name": self.name,
            "state": self.state.name,
            "failure_count": self.failure_count,
            "failure_threshold": self.config.failure_threshold,
            "success_count": self.success_count,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "failure_rate": round(failure_rate, 2),
            "window_failure_rate": round(window_failure_rate, 2),
            "trip_count": self.trip_count,
            "time_in_state": round(current_time - self.last_state_change_time, 1),
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "failure_window": self.config.failure_window,
                "reset_timeout": self.config.reset_timeout,
                "half_open_max_requests": self.config.half_open_max_requests,
                "half_open_success_threshold": self.config.half_open_success_threshold,
            }
        }


class CircuitBreakerRegistry:
    """熔断器注册表"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._breakers = {}
            cls._instance._default_config = CircuitBreakerConfig()
        return cls._instance

    def get_breaker(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """
        获取或创建熔断器

        Args:
            name: 熔断器名称
            config: 熔断器配置

        Returns:
            CircuitBreaker: 熔断器实例
        """
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                name,
                config or self._default_config
            )

        return self._breakers[name]

    def get_all_stats(self) -> dict:
        """获取所有熔断器的统计信息"""
        return {
            name: breaker.get_stats()
            for name, breaker in self._breakers.items()
        }

    def reset_all(self):
        """重置所有熔断器"""
        for breaker in self._breakers.values():
            breaker.state = CircuitState.CLOSED
            breaker.failure_count = 0
            breaker.success_count = 0
            breaker.last_failure_time = None
            breaker.last_state_change_time = time.time()

        logger.info("所有熔断器已重置")


# 全局熔断器注册表
circuit_breaker_registry = CircuitBreakerRegistry()


def circuit_breaker(
    name: Optional[str] = None,
    config: Optional[CircuitBreakerConfig] = None,
):
    """
    熔断器装饰器工厂函数

    Args:
        name: 熔断器名称，如果为None则使用函数名
        config: 熔断器配置

    Returns:
        装饰器函数
    """
    def decorator(func: Callable):
        breaker_name = name or func.__name__
        breaker = circuit_breaker_registry.get_breaker(breaker_name, config)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            """异步函数包装器"""
            # 检查是否允许请求
            if not breaker.allow_request():
                raise Exception(
                    f"熔断器已熔断: {breaker_name}, "
                    f"状态: {breaker.state.name}"
                )

            try:
                # 执行函数
                result = await func(*args, **kwargs)

                # 记录成功
                breaker.record_success()

                return result

            except Exception as e:
                # 记录失败
                breaker.record_failure()
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            """同步函数包装器"""
            # 检查是否允许请求
            if not breaker.allow_request():
                raise Exception(
                    f"熔断器已熔断: {breaker_name}, "
                    f"状态: {breaker.state.name}"
                )

            try:
                # 执行函数
                result = func(*args, **kwargs)

                # 记录成功
                breaker.record_success()

                return result

            except Exception as e:
                # 记录失败
                breaker.record_failure()
                raise

        # 根据函数类型返回相应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def circuit_breaker_with_config(
    failure_threshold: int = 5,
    failure_window: float = 60.0,
    reset_timeout: float = 30.0,
    half_open_max_requests: int = 3,
    half_open_success_threshold: int = 2,
    name: Optional[str] = None,
):
    """
    带配置的熔断器装饰器快捷函数

    Args:
        failure_threshold: 触发熔断的连续失败次数
        failure_window: 统计失败的时间窗口（秒）
        reset_timeout: 熔断器保持OPEN状态的时间（秒）
        half_open_max_requests: 半开状态允许的最大请求数
        half_open_success_threshold: 半开状态下恢复服务需要的最小成功数
        name: 熔断器名称

    Returns:
        装饰器函数
    """
    config = CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        failure_window=failure_window,
        reset_timeout=reset_timeout,
        half_open_max_requests=half_open_max_requests,
        half_open_success_threshold=half_open_success_threshold,
    )

    return circuit_breaker(name=name, config=config)