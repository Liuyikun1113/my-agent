"""
异步工具函数
提供通用的异步操作工具
"""
import asyncio
import logging
from typing import (
    TypeVar, Callable, Coroutine, List, Any, Optional, Tuple,
)
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def run_async(func: Callable[..., T], *args, **kwargs) -> T:
    """
    在线程池中运行同步函数

    Args:
        func: 同步函数
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        函数返回值
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))


async def gather_with_concurrency(
    concurrency: int,
    *coroutines: Coroutine,
    return_exceptions: bool = False,
) -> List[Any]:
    """
    带并发控制的gather

    Args:
        concurrency: 最大并发数
        *coroutines: 协程列表
        return_exceptions: 是否返回异常而不是抛出

    Returns:
        结果列表
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def _wrap(coro: Coroutine) -> Any:
        async with semaphore:
            return await coro

    tasks = [_wrap(coro) for coro in coroutines]
    return await asyncio.gather(*tasks, return_exceptions=return_exceptions)


async def retry_async(
    coro_func: Callable[..., Coroutine],
    max_attempts: int = 3,
    backoff_factor: float = 2.0,
    exceptions: Tuple = (Exception,),
    *args,
    **kwargs,
) -> Any:
    """
    异步重试

    Args:
        coro_func: 返回协程的可调用对象
        max_attempts: 最大尝试次数
        backoff_factor: 退避因子
        exceptions: 需要重试的异常类型
        *args: 传递给coro_func的位置参数
        **kwargs: 传递给coro_func的关键字参数

    Returns:
        函数返回值

    Raises:
        最后一次尝试的异常
    """
    last_exception = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await coro_func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            if attempt < max_attempts:
                delay = backoff_factor ** attempt
                logger.warning(f"重试 {attempt}/{max_attempts}，等待 {delay:.1f}s: {e}")
                await asyncio.sleep(delay)
            else:
                logger.error(f"重试耗尽 {max_attempts}次: {e}")

    raise last_exception


async def timeout_async(
    coro: Coroutine,
    timeout: float,
    default: Any = None,
) -> Any:
    """
    带超时的异步操作

    Args:
        coro: 协程
        timeout: 超时时间（秒）
        default: 超时时的默认返回值

    Returns:
        协程返回值或默认值
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(f"操作超时: {timeout}s")
        return default


class AsyncTaskPool:
    """
    异步任务池
    管理并发异步任务的执行
    """

    def __init__(self, max_workers: int = 10):
        """
        初始化任务池

        Args:
            max_workers: 最大并发任务数
        """
        self.max_workers = max_workers
        self._semaphore = asyncio.Semaphore(max_workers)
        self._tasks: List[asyncio.Task] = []
        self._results: List[Any] = []
        self._errors: List[Exception] = []

    async def submit(self, coro: Coroutine) -> None:
        """提交任务"""
        async def _run():
            async with self._semaphore:
                try:
                    result = await coro
                    self._results.append(result)
                except Exception as e:
                    self._errors.append(e)
                    logger.error(f"任务执行失败: {e}")

        task = asyncio.create_task(_run())
        self._tasks.append(task)

    async def wait_all(self) -> Tuple[List[Any], List[Exception]]:
        """等待所有任务完成"""
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        return self._results, self._errors

    @property
    def active_count(self) -> int:
        """活跃任务数"""
        return len([t for t in self._tasks if not t.done()])

    @property
    def completed_count(self) -> int:
        """已完成任务数"""
        return len([t for t in self._tasks if t.done()])

    def cancel_all(self):
        """取消所有任务"""
        for task in self._tasks:
            if not task.done():
                task.cancel()
