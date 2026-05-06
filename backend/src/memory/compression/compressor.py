"""
记忆压缩器
协调记忆压缩过程，管理压缩任务
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
import threading
import uuid

from config.settings import settings
from memory.interfaces.memory_item import MemoryItem
from memory.interfaces.memory_store import MemoryStore
from .summarizer import summarizer
from .compression_strategies import (
    CompressionStrategy,
    get_strategy,
    STRATEGY_REGISTRY,
)

logger = logging.getLogger(__name__)


class MemoryCompressor:
    """
    记忆压缩器
    管理记忆压缩任务和策略
    """

    def __init__(
        self,
        memory_store: MemoryStore,
        strategy_name: str = "hybrid",
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化记忆压缩器

        Args:
            memory_store: 记忆存储实例
            strategy_name: 压缩策略名称
            config: 压缩配置
        """
        self.memory_store = memory_store
        self.strategy_name = strategy_name
        self.config = config or {}

        # 设置默认配置
        default_config = {
            "compression_threshold": settings.MEMORY_COMPRESSION_THRESHOLD,
            "compression_interval": settings.MEMORY_COMPRESSION_INTERVAL,
            "compression_ratio": 0.5,
            "max_items_per_compression": 1000,
            "enable_async_compression": True,
            "retry_on_failure": True,
            "max_retries": 3,
        }
        self.config = {**default_config, **self.config}

        # 压缩策略
        self.strategy: Optional[CompressionStrategy] = None

        # 压缩任务状态
        self._compression_lock = asyncio.Lock()
        self._is_compressing = False
        self._last_compression_time: Optional[datetime] = None
        self._compression_stats: Dict[str, Any] = {
            "total_compressions": 0,
            "total_items_compressed": 0,
            "total_reduction": 0,
            "last_compression_result": None,
            "errors": [],
        }

        # 异步任务
        self._compression_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def initialize(self):
        """
        初始化压缩器
        """
        try:
            # 初始化摘要生成器
            await summarizer.initialize()

            # 初始化压缩策略
            self.strategy = get_strategy(self.strategy_name)

            # 启动定期压缩检查（如果启用）
            if self.config.get("enable_async_compression", True):
                self._compression_task = asyncio.create_task(
                    self._periodic_compression_check()
                )

            logger.info(f"记忆压缩器初始化完成，使用策略: {self.strategy_name}")

        except Exception as e:
            logger.error(f"记忆压缩器初始化失败: {e}")
            raise

    async def compress_memory(
        self,
        memory_items: Optional[List[MemoryItem]] = None,
        item_ids: Optional[List[str]] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        压缩记忆

        Args:
            memory_items: 要压缩的记忆项列表（如果为None，则从存储中获取）
            item_ids: 要压缩的记忆项ID列表
            force: 是否强制压缩（忽略时间和数量检查）

        Returns:
            Dict[str, Any]: 压缩结果统计
        """
        async with self._compression_lock:
            if self._is_compressing:
                logger.warning("压缩任务已在运行，跳过")
                return {
                    "status": "skipped",
                    "message": "压缩任务已在运行",
                    **self._compression_stats,
                }

            self._is_compressing = True

            try:
                # 获取要压缩的记忆项
                items_to_compress = await self._get_memory_items_to_compress(
                    memory_items, item_ids
                )

                if not items_to_compress:
                    result = {
                        "status": "skipped",
                        "message": "没有需要压缩的记忆项",
                        "original_count": 0,
                        "compressed_count": 0,
                        "reduction": 0,
                    }
                    return result

                # 检查是否应该压缩
                if not force and not self._should_compress(items_to_compress):
                    result = {
                        "status": "skipped",
                        "message": "未达到压缩条件",
                        "original_count": len(items_to_compress),
                        "compressed_count": len(items_to_compress),
                        "reduction": 0,
                    }
                    return result

                # 执行压缩
                compressed_items = await self._execute_compression(items_to_compress)

                # 保存压缩结果
                await self._save_compression_result(compressed_items, items_to_compress)

                # 更新统计信息
                original_count = len(items_to_compress)
                compressed_count = len(compressed_items)
                reduction = original_count - compressed_count

                self._update_stats(
                    original_count=original_count,
                    compressed_count=compressed_count,
                    reduction=reduction,
                )

                result = {
                    "status": "success",
                    "message": f"压缩完成: {original_count} -> {compressed_count} 项",
                    "original_count": original_count,
                    "compressed_count": compressed_count,
                    "reduction": reduction,
                    "reduction_percentage": (
                        reduction / original_count * 100 if original_count > 0 else 0
                    ),
                    "compression_time": datetime.now().isoformat(),
                    "strategy": self.strategy_name,
                }

                logger.info(f"记忆压缩成功: {result['message']}")

                return result

            except Exception as e:
                logger.error(f"记忆压缩失败: {e}", exc_info=True)

                error_result = {
                    "status": "error",
                    "message": f"压缩失败: {str(e)}",
                    "error": str(e),
                    "compression_time": datetime.now().isoformat(),
                }

                self._compression_stats["errors"].append(error_result)

                return error_result

            finally:
                self._is_compressing = False
                self._last_compression_time = datetime.now()

    async def _get_memory_items_to_compress(
        self,
        memory_items: Optional[List[MemoryItem]],
        item_ids: Optional[List[str]],
    ) -> List[MemoryItem]:
        """获取要压缩的记忆项"""
        if memory_items is not None:
            return memory_items

        if item_ids is not None:
            # 根据ID获取记忆项
            items = []
            for item_id in item_ids:
                try:
                    item = await self.memory_store.get(item_id)
                    if item:
                        items.append(item)
                except Exception as e:
                    logger.error(f"获取记忆项失败: item_id={item_id}, error={e}")
            return items

        # 从存储中获取需要压缩的记忆项
        # 这里简单实现：获取所有记忆项，实际应用中可能需要更智能的选择
        try:
            # 假设memory_store有list方法
            if hasattr(self.memory_store, "list"):
                items, total = await self.memory_store.list(
                    page=1,
                    page_size=self.config.get("max_items_per_compression", 1000),
                    order_by="-created_at",  # 按时间倒序，先压缩旧的
                )
                return items
            else:
                logger.warning("记忆存储不支持list方法，无法自动获取记忆项")
                return []
        except Exception as e:
            logger.error(f"从存储获取记忆项失败: {e}")
            return []

    def _should_compress(self, memory_items: List[MemoryItem]) -> bool:
        """判断是否应该压缩"""
        # 检查数量阈值
        compression_threshold = self.config.get("compression_threshold", 20)
        if len(memory_items) < compression_threshold:
            logger.debug(f"记忆项数量 ({len(memory_items)}) 未达到阈值 ({compression_threshold})")
            return False

        # 检查时间间隔
        if self._last_compression_time:
            compression_interval = self.config.get("compression_interval", 300)
            time_since_last = (datetime.now() - self._last_compression_time).total_seconds()
            if time_since_last < compression_interval:
                logger.debug(f"距离上次压缩仅 {time_since_last:.1f} 秒，跳过")
                return False

        # 使用策略的判断
        if self.strategy:
            return self.strategy.should_compress(memory_items, self.config)

        return True

    async def _execute_compression(
        self,
        memory_items: List[MemoryItem],
    ) -> List[MemoryItem]:
        """执行压缩"""
        if not self.strategy:
            raise ValueError("压缩策略未初始化")

        # 限制每次压缩的最大项数
        max_items = self.config.get("max_items_per_compression", 1000)
        if len(memory_items) > max_items:
            logger.warning(f"记忆项数量 ({len(memory_items)}) 超过最大值 ({max_items})，将进行分批压缩")

            # 分批压缩
            batches = [
                memory_items[i:i + max_items]
                for i in range(0, len(memory_items), max_items)
            ]

            compressed_items = []
            for i, batch in enumerate(batches):
                logger.info(f"压缩批次 {i+1}/{len(batches)} ({len(batch)} 项)")
                compressed_batch = await self.strategy.compress(batch, self.config)
                compressed_items.extend(compressed_batch)

            return compressed_items
        else:
            # 单批压缩
            return await self.strategy.compress(memory_items, self.config)

    async def _save_compression_result(
        self,
        compressed_items: List[MemoryItem],
        original_items: List[MemoryItem],
    ):
        """保存压缩结果到存储"""
        try:
            # 保存压缩后的项
            for item in compressed_items:
                await self.memory_store.save(item)

            # 标记原始项为已压缩（在实际应用中，可能需要删除或归档原始项）
            # 这里简化处理：只记录日志
            logger.info(f"保存 {len(compressed_items)} 个压缩后的记忆项")

        except Exception as e:
            logger.error(f"保存压缩结果失败: {e}")
            raise

    def _update_stats(
        self,
        original_count: int,
        compressed_count: int,
        reduction: int,
    ):
        """更新压缩统计"""
        self._compression_stats["total_compressions"] += 1
        self._compression_stats["total_items_compressed"] += original_count
        self._compression_stats["total_reduction"] += reduction

        self._compression_stats["last_compression_result"] = {
            "timestamp": datetime.now().isoformat(),
            "original_count": original_count,
            "compressed_count": compressed_count,
            "reduction": reduction,
            "reduction_percentage": (
                reduction / original_count * 100 if original_count > 0 else 0
            ),
        }

    async def _periodic_compression_check(self):
        """定期检查并执行压缩"""
        check_interval = self.config.get("compression_interval", 300)

        logger.info(f"启动定期压缩检查，间隔: {check_interval} 秒")

        while not self._stop_event.is_set():
            try:
                # 等待检查间隔
                await asyncio.sleep(check_interval)

                # 执行压缩检查
                logger.debug("执行定期压缩检查")
                await self.compress_memory(force=False)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"定期压缩检查失败: {e}")
                # 继续执行，不中断循环

    async def get_stats(self) -> Dict[str, Any]:
        """
        获取压缩统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            **self._compression_stats,
            "is_compressing": self._is_compressing,
            "last_compression_time": (
                self._last_compression_time.isoformat()
                if self._last_compression_time
                else None
            ),
            "strategy": self.strategy_name,
            "config": self.config,
        }

    async def change_strategy(
        self,
        strategy_name: str,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        更改压缩策略

        Args:
            strategy_name: 新策略名称
            config: 新配置
        """
        if strategy_name not in STRATEGY_REGISTRY:
            raise ValueError(f"未知的压缩策略: {strategy_name}")

        self.strategy_name = strategy_name
        self.strategy = get_strategy(strategy_name)

        if config:
            self.config = {**self.config, **config}

        logger.info(f"压缩策略已更改为: {strategy_name}")

    async def stop(self):
        """停止压缩器"""
        self._stop_event.set()

        if self._compression_task:
            self._compression_task.cancel()
            try:
                await self._compression_task
            except asyncio.CancelledError:
                pass

        await summarizer.close()

        logger.info("记忆压缩器已停止")

    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            Dict[str, Any]: 健康状态信息
        """
        try:
            stats = await self.get_stats()

            # 检查压缩策略
            strategy_status = "initialized" if self.strategy else "not_initialized"

            # 检查最近是否成功压缩
            last_result = stats.get("last_compression_result")
            if last_result and last_result.get("status") == "success":
                last_success = True
                last_message = "最近压缩成功"
            else:
                last_success = False
                last_message = "最近压缩失败或无压缩记录"

            return {
                "status": "healthy",
                "message": "记忆压缩器运行正常",
                "strategy": self.strategy_name,
                "strategy_status": strategy_status,
                "is_compressing": self._is_compressing,
                "total_compressions": stats.get("total_compressions", 0),
                "total_reduction": stats.get("total_reduction", 0),
                "last_compression_success": last_success,
                "last_compression_message": last_message,
                "config": self.config,
            }

        except Exception as e:
            logger.error(f"记忆压缩器健康检查失败: {e}")
            return {
                "status": "unhealthy",
                "message": f"记忆压缩器检查失败: {str(e)}",
                "strategy": self.strategy_name,
                "is_compressing": self._is_compressing,
            }


# 全局记忆压缩器实例
_global_compressor: Optional[MemoryCompressor] = None


async def get_global_compressor(
    memory_store: Optional[MemoryStore] = None,
) -> MemoryCompressor:
    """
    获取全局记忆压缩器实例

    Args:
        memory_store: 记忆存储实例（如果为None，则需要后续设置）

    Returns:
        MemoryCompressor: 全局压缩器实例
    """
    global _global_compressor

    if _global_compressor is None:
        if memory_store is None:
            raise ValueError("首次调用需要提供memory_store参数")

        _global_compressor = MemoryCompressor(memory_store)
        await _global_compressor.initialize()

    return _global_compressor


async def compress_memory(
    memory_store: MemoryStore,
    memory_items: Optional[List[MemoryItem]] = None,
    strategy_name: str = "hybrid",
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    快速压缩记忆（便捷函数）

    Args:
        memory_store: 记忆存储实例
        memory_items: 要压缩的记忆项列表
        strategy_name: 压缩策略名称
        config: 压缩配置

    Returns:
        Dict[str, Any]: 压缩结果
    """
    compressor = MemoryCompressor(memory_store, strategy_name, config)
    await compressor.initialize()
    result = await compressor.compress_memory(memory_items)
    await compressor.stop()
    return result