"""
记忆压缩策略
定义不同的记忆压缩算法和策略
"""
import logging
from typing import List, Dict, Any, Optional, Callable
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import statistics

from memory.interfaces.memory_item import MemoryItem
from .summarizer import Summarizer

logger = logging.getLogger(__name__)


class CompressionStrategy(ABC):
    """
    压缩策略抽象基类
    """

    def __init__(self, name: str, description: str = ""):
        """
        初始化压缩策略

        Args:
            name: 策略名称
            description: 策略描述
        """
        self.name = name
        self.description = description

    @abstractmethod
    async def compress(
        self,
        memory_items: List[MemoryItem],
        config: Optional[Dict[str, Any]] = None,
    ) -> List[MemoryItem]:
        """
        压缩记忆项列表

        Args:
            memory_items: 原始记忆项列表
            config: 压缩配置

        Returns:
            List[MemoryItem]: 压缩后的记忆项列表
        """
        pass

    def should_compress(
        self,
        memory_items: List[MemoryItem],
        config: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        判断是否应该进行压缩

        Args:
            memory_items: 记忆项列表
            config: 压缩配置

        Returns:
            bool: 是否应该压缩
        """
        return len(memory_items) > 0


class TimeBasedStrategy(CompressionStrategy):
    """
    基于时间的压缩策略
    按时间窗口分组并压缩
    """

    def __init__(self):
        super().__init__(
            name="time_based",
            description="基于时间窗口的压缩策略，将相同时段内的记忆合并"
        )
        self.summarizer = Summarizer()

    async def compress(
        self,
        memory_items: List[MemoryItem],
        config: Optional[Dict[str, Any]] = None,
    ) -> List[MemoryItem]:
        """
        基于时间窗口压缩

        Args:
            memory_items: 原始记忆项列表
            config: 压缩配置，可包含：
                   - time_window_hours: 时间窗口（小时）
                   - max_items_per_window: 每个窗口最大项数
                   - compression_ratio: 压缩比例

        Returns:
            List[MemoryItem]: 压缩后的记忆项列表
        """
        if not memory_items:
            return []

        # 默认配置
        default_config = {
            "time_window_hours": 24,  # 24小时窗口
            "max_items_per_window": 10,
            "compression_ratio": 0.3,
        }
        config = {**default_config, **(config or {})}

        try:
            # 按时间排序
            sorted_items = sorted(memory_items, key=lambda x: x.created_at)

            # 按时间窗口分组
            time_window = timedelta(hours=config["time_window_hours"])
            groups = self._group_by_time_window(sorted_items, time_window)

            # 压缩每个组
            compressed_items = []
            for group in groups:
                compressed_group = await self._compress_group(group, config)
                compressed_items.extend(compressed_group)

            logger.info(f"时间压缩完成: {len(memory_items)} -> {len(compressed_items)} 项")

            return compressed_items

        except Exception as e:
            logger.error(f"时间压缩策略失败: {e}")
            return memory_items

    def _group_by_time_window(
        self,
        items: List[MemoryItem],
        time_window: timedelta,
    ) -> List[List[MemoryItem]]:
        """按时间窗口分组"""
        if not items:
            return []

        groups = []
        current_group = []
        current_window_start = items[0].created_at

        for item in items:
            if item.created_at - current_window_start <= time_window:
                current_group.append(item)
            else:
                if current_group:
                    groups.append(current_group)
                current_group = [item]
                current_window_start = item.created_at

        if current_group:
            groups.append(current_group)

        return groups

    async def _compress_group(
        self,
        group: List[MemoryItem],
        config: Dict[str, Any],
    ) -> List[MemoryItem]:
        """压缩一个组"""
        if len(group) <= config["max_items_per_window"]:
            return group

        # 使用摘要生成器压缩
        await self.summarizer.initialize()
        return await self.summarizer.summarize_memory_items(
            group,
            compression_ratio=config["compression_ratio"],
        )


class CountBasedStrategy(CompressionStrategy):
    """
    基于数量的压缩策略
    当记忆项数量超过阈值时进行压缩
    """

    def __init__(self):
        super().__init__(
            name="count_based",
            description="基于数量的压缩策略，当记忆项超过阈值时触发压缩"
        )
        self.summarizer = Summarizer()

    def should_compress(
        self,
        memory_items: List[MemoryItem],
        config: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """判断是否应该压缩（数量超过阈值）"""
        default_config = {
            "compression_threshold": 50,
        }
        config = {**default_config, **(config or {})}

        return len(memory_items) >= config["compression_threshold"]

    async def compress(
        self,
        memory_items: List[MemoryItem],
        config: Optional[Dict[str, Any]] = None,
    ) -> List[MemoryItem]:
        """
        基于数量压缩

        Args:
            memory_items: 原始记忆项列表
            config: 压缩配置，可包含：
                   - compression_threshold: 压缩阈值
                   - target_count: 目标数量
                   - compression_ratio: 压缩比例

        Returns:
            List[MemoryItem]: 压缩后的记忆项列表
        """
        if not memory_items:
            return []

        # 默认配置
        default_config = {
            "compression_threshold": 50,
            "target_count": 20,
            "compression_ratio": 0.4,
        }
        config = {**default_config, **(config or {})}

        try:
            # 检查是否达到压缩阈值
            if not self.should_compress(memory_items, config):
                return memory_items

            # 计算压缩比例
            current_count = len(memory_items)
            target_count = config["target_count"]
            compression_ratio = min(
                config["compression_ratio"],
                target_count / current_count if current_count > 0 else 1.0
            )

            # 使用摘要生成器压缩
            await self.summarizer.initialize()
            compressed_items = await self.summarizer.summarize_memory_items(
                memory_items,
                compression_ratio=compression_ratio,
            )

            logger.info(f"数量压缩完成: {current_count} -> {len(compressed_items)} 项")

            return compressed_items

        except Exception as e:
            logger.error(f"数量压缩策略失败: {e}")
            return memory_items


class ImportanceBasedStrategy(CompressionStrategy):
    """
    基于重要性的压缩策略
    根据记忆项的重要性评分进行选择性保留
    """

    def __init__(self):
        super().__init__(
            name="importance_based",
            description="基于重要性的压缩策略，保留重要的记忆项"
        )
        self.summarizer = Summarizer()

    async def compress(
        self,
        memory_items: List[MemoryItem],
        config: Optional[Dict[str, Any]] = None,
    ) -> List[MemoryItem]:
        """
        基于重要性压缩

        Args:
            memory_items: 原始记忆项列表
            config: 压缩配置，可包含：
                   - importance_threshold: 重要性阈值
                   - min_importance_score: 最小重要性分数
                   - compression_ratio: 压缩比例

        Returns:
            List[MemoryItem]: 压缩后的记忆项列表
        """
        if not memory_items:
            return []

        # 默认配置
        default_config = {
            "importance_threshold": 0.5,
            "min_importance_score": 0.3,
            "compression_ratio": 0.5,
        }
        config = {**default_config, **(config or {})}

        try:
            # 计算每个记忆项的重要性分数
            scored_items = []
            for item in memory_items:
                score = self._calculate_importance_score(item)
                scored_items.append((item, score))

            # 按重要性排序
            scored_items.sort(key=lambda x: x[1], reverse=True)

            # 筛选重要项
            important_items = [
                item for item, score in scored_items
                if score >= config["importance_threshold"]
            ]

            # 如果重要项太少，保留分数较高的项
            if len(important_items) < len(memory_items) * config["compression_ratio"]:
                keep_count = int(len(memory_items) * config["compression_ratio"])
                important_items = [item for item, _ in scored_items[:keep_count]]

            # 压缩非重要项
            unimportant_items = [item for item, _ in scored_items if item not in important_items]

            if unimportant_items:
                await self.summarizer.initialize()
                compressed_unimportant = await self.summarizer.summarize_memory_items(
                    unimportant_items,
                    compression_ratio=0.2,  # 高度压缩非重要项
                )
                result = important_items + compressed_unimportant
            else:
                result = important_items

            logger.info(f"重要性压缩完成: {len(memory_items)} -> {len(result)} 项")

            return result

        except Exception as e:
            logger.error(f"重要性压缩策略失败: {e}")
            return memory_items

    def _calculate_importance_score(self, item: MemoryItem) -> float:
        """计算记忆项的重要性分数"""
        score = 0.0

        # 根据类型调整基础分数
        type_scores = {
            "summary": 0.9,
            "decision": 0.8,
            "action": 0.7,
            "message": 0.5,
            "document": 0.6,
        }
        score += type_scores.get(item.type, 0.5)

        # 根据元数据调整
        metadata = item.metadata or {}
        if metadata.get("important", False):
            score += 0.2
        if metadata.get("pinned", False):
            score += 0.3

        # 根据数据内容调整
        data = item.data or {}
        if isinstance(data, dict):
            # 检查是否包含关键字段
            key_fields = ["summary", "decision", "action", "result", "conclusion"]
            for field in key_fields:
                if field in data and data[field]:
                    score += 0.1
                    break

        # 根据长度调整（较长的内容可能更重要）
        if isinstance(data, dict) and "content" in data:
            content_len = len(str(data["content"]))
            if content_len > 100:
                score += min(0.2, content_len / 1000)

        # 限制在0.0-1.0之间
        return max(0.0, min(1.0, score))


class HybridStrategy(CompressionStrategy):
    """
    混合压缩策略
    结合多种策略进行压缩
    """

    def __init__(self):
        super().__init__(
            name="hybrid",
            description="混合压缩策略，结合时间、数量和重要性"
        )
        self.strategies = [
            TimeBasedStrategy(),
            CountBasedStrategy(),
            ImportanceBasedStrategy(),
        ]
        self.summarizer = Summarizer()

    async def compress(
        self,
        memory_items: List[MemoryItem],
        config: Optional[Dict[str, Any]] = None,
    ) -> List[MemoryItem]:
        """
        混合策略压缩

        Args:
            memory_items: 原始记忆项列表
            config: 压缩配置

        Returns:
            List[MemoryItem]: 压缩后的记忆项列表
        """
        if not memory_items:
            return []

        try:
            # 应用多个策略
            current_items = memory_items.copy()

            for strategy in self.strategies:
                if strategy.should_compress(current_items, config):
                    current_items = await strategy.compress(current_items, config)

                    # 如果已经压缩到目标大小，提前结束
                    target_ratio = (config or {}).get("compression_ratio", 0.5)
                    target_count = int(len(memory_items) * target_ratio)
                    if len(current_items) <= target_count:
                        break

            logger.info(f"混合压缩完成: {len(memory_items)} -> {len(current_items)} 项")

            return current_items

        except Exception as e:
            logger.error(f"混合压缩策略失败: {e}")
            return memory_items


# 策略注册表
STRATEGY_REGISTRY = {
    "time_based": TimeBasedStrategy,
    "count_based": CountBasedStrategy,
    "importance_based": ImportanceBasedStrategy,
    "hybrid": HybridStrategy,
}


def get_strategy(strategy_name: str) -> CompressionStrategy:
    """
    获取压缩策略实例

    Args:
        strategy_name: 策略名称

    Returns:
        CompressionStrategy: 策略实例

    Raises:
        ValueError: 如果策略名称无效
    """
    if strategy_name not in STRATEGY_REGISTRY:
        raise ValueError(f"未知的压缩策略: {strategy_name}")

    return STRATEGY_REGISTRY[strategy_name]()