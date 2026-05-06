"""
限流中间件
提供基于令牌桶和滑动窗口的请求限流
"""
import logging
import time
import asyncio
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from fastapi import Request, HTTPException

from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class TokenBucket:
    """令牌桶"""
    tokens: float = 0.0
    max_tokens: float = 60.0
    refill_rate: float = 1.0  # 令牌/秒
    last_refill: float = field(default_factory=time.time)

    def consume(self, tokens: float = 1.0) -> bool:
        """尝试消费令牌"""
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def _refill(self):
        """补充令牌"""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now


@dataclass
class SlidingWindow:
    """滑动窗口"""
    window_size: float = 60.0  # 秒
    max_requests: int = 60
    requests: list = field(default_factory=list)

    def allow(self) -> bool:
        """检查是否允许请求"""
        now = time.time()
        cutoff = now - self.window_size

        # 清理过期请求
        self.requests = [t for t in self.requests if t > cutoff]

        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True
        return False

    @property
    def current_count(self) -> int:
        """当前窗口内请求数"""
        cutoff = time.time() - self.window_size
        return len([t for t in self.requests if t > cutoff])


class RateLimiter:
    """
    限流器
    支持多种限流策略：令牌桶、滑动窗口
    """

    def __init__(
        self,
        strategy: str = "token_bucket",
        requests_per_minute: Optional[int] = None,
    ):
        """
        初始化限流器

        Args:
            strategy: 限流策略 (token_bucket/sliding_window)
            requests_per_minute: 每分钟允许的请求数
        """
        self.strategy = strategy
        self.requests_per_minute = requests_per_minute or settings.RATE_LIMIT_REQUESTS_PER_MINUTE

        # 令牌桶存储 (按IP/用户)
        self._buckets: Dict[str, TokenBucket] = {}
        self._buckets_lock = asyncio.Lock()

        # 滑动窗口存储 (按IP/用户)
        self._windows: Dict[str, SlidingWindow] = {}
        self._windows_lock = asyncio.Lock()

        # 黑名单
        self._blacklist: Dict[str, float] = {}  # key -> banned_until timestamp

        # 统计
        self._stats: Dict[str, int] = defaultdict(int)

        self._cleanup_task = None

    async def start(self):
        """启动限流器"""
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        logger.info(f"限流器已启动: strategy={self.strategy}, rpm={self.requests_per_minute}")

    async def stop(self):
        """停止限流器"""
        if self._cleanup_task:
            self._cleanup_task.cancel()

    async def is_allowed(self, key: str, cost: float = 1.0) -> Tuple[bool, str]:
        """
        检查是否允许请求

        Args:
            key: 限流键（IP或用户ID）
            cost: 请求成本

        Returns:
            (是否允许, 原因)
        """
        # 检查黑名单
        if key in self._blacklist:
            banned_until = self._blacklist[key]
            if time.time() < banned_until:
                remaining = int(banned_until - time.time())
                return False, f"已被限流，请在 {remaining} 秒后重试"
            else:
                del self._blacklist[key]

        if self.strategy == "token_bucket":
            return await self._check_token_bucket(key, cost)
        elif self.strategy == "sliding_window":
            return await self._check_sliding_window(key)
        else:
            return True, "ok"

    async def _check_token_bucket(self, key: str, cost: float) -> Tuple[bool, str]:
        """令牌桶检查"""
        async with self._buckets_lock:
            if key not in self._buckets:
                refill_rate = self.requests_per_minute / 60.0
                self._buckets[key] = TokenBucket(
                    tokens=self.requests_per_minute,
                    max_tokens=self.requests_per_minute,
                    refill_rate=refill_rate,
                )

            bucket = self._buckets[key]
            if bucket.consume(cost):
                self._stats["allowed"] += 1
                return True, "ok"
            else:
                self._stats["rejected"] += 1
                return False, "请求频率过高，请稍后重试"

    async def _check_sliding_window(self, key: str) -> Tuple[bool, str]:
        """滑动窗口检查"""
        async with self._windows_lock:
            if key not in self._windows:
                self._windows[key] = SlidingWindow(
                    window_size=60.0,
                    max_requests=self.requests_per_minute,
                )

            window = self._windows[key]
            if window.allow():
                self._stats["allowed"] += 1
                return True, "ok"
            else:
                self._stats["rejected"] += 1
                return False, "请求频率过高，请稍后重试"

    def ban(self, key: str, duration_seconds: float = 300.0):
        """
        封禁用户/IP

        Args:
            key: 限流键
            duration_seconds: 封禁时长（秒）
        """
        self._blacklist[key] = time.time() + duration_seconds
        logger.warning(f"已封禁: {key}, 时长: {duration_seconds}s")

    def unban(self, key: str):
        """解除封禁"""
        self._blacklist.pop(key, None)
        logger.info(f"已解除封禁: {key}")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "strategy": self.strategy,
            "requests_per_minute": self.requests_per_minute,
            "active_buckets": len(self._buckets),
            "active_windows": len(self._windows),
            "blacklisted": len(self._blacklist),
            "stats": dict(self._stats),
        }

    async def _periodic_cleanup(self):
        """定期清理过期数据"""
        while True:
            try:
                await asyncio.sleep(300)  # 5分钟清理一次
                now = time.time()

                # 清理过期黑名单
                expired_bans = [k for k, v in self._blacklist.items() if now >= v]
                for key in expired_bans:
                    del self._blacklist[key]

                # 清理过期窗口
                async with self._windows_lock:
                    expired_windows = [
                        k for k, w in self._windows.items()
                        if w.current_count == 0
                    ]
                    for key in expired_windows:
                        del self._windows[key]

                logger.debug(f"限流器清理: {len(expired_bans)} bans, {len(expired_windows)} windows")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"限流器清理异常: {e}")


# 全局限流器实例
rate_limiter = RateLimiter()


async def rate_limit_middleware(request: Request):
    """
    限流中间件
    对每个请求进行限流检查

    Args:
        request: HTTP请求

    Raises:
        HTTPException: 限流
    """
    # 跳过不需要限流的路径
    skip_paths = ["/health", "/metrics", "/docs", "/openapi.json", "/redoc"]
    if any(request.url.path.startswith(p) for p in skip_paths):
        return

    # 使用客户端IP作为限流键
    client_ip = request.client.host if request.client else "unknown"
    user_id = getattr(request.state, "user_id", None)
    rate_key = user_id or client_ip

    allowed, reason = await rate_limiter.is_allowed(rate_key)

    if not allowed:
        logger.warning(f"限流触发: key={rate_key}, path={request.url.path}")
        raise HTTPException(status_code=429, detail=reason)

    # 添加限流头
    request.state.rate_limit_key = rate_key
