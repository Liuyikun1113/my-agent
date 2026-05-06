"""
记忆存储接口定义
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from .memory_item import MemoryItem


class MemoryStore(ABC):
    """
    记忆存储抽象基类
    所有记忆存储实现必须继承此基类
    """

    @abstractmethod
    async def initialize(self):
        """
        初始化存储连接
        """
        pass

    @abstractmethod
    async def save(self, item: MemoryItem):
        """
        保存记忆项

        Args:
            item: 记忆项
        """
        pass

    @abstractmethod
    async def get(self, item_id: str) -> Optional[MemoryItem]:
        """
        获取记忆项

        Args:
            item_id: 记忆项ID

        Returns:
            Optional[MemoryItem]: 记忆项，如果不存在则返回None
        """
        pass

    @abstractmethod
    async def list(
        self,
        type: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20,
        order_by: Optional[str] = None,
    ) -> Tuple[List[MemoryItem], int]:
        """
        列出记忆项

        Args:
            type: 记忆项类型过滤
            filters: 过滤条件
            page: 页码
            page_size: 每页数量
            order_by: 排序字段（前缀"-"表示降序）

        Returns:
            Tuple[List[MemoryItem], int]: 记忆项列表和总数
        """
        pass

    @abstractmethod
    async def delete(self, item_id: str):
        """
        删除记忆项

        Args:
            item_id: 记忆项ID
        """
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
    ) -> List[MemoryItem]:
        """
        搜索记忆项

        Args:
            query: 搜索查询
            filters: 过滤条件
            limit: 返回结果数量限制

        Returns:
            List[MemoryItem]: 搜索结果
        """
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            Dict[str, Any]: 健康状态信息
        """
        pass

    @abstractmethod
    async def close(self):
        """
        关闭存储连接
        """
        pass