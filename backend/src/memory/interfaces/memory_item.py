"""
记忆项数据模型
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional
import uuid


@dataclass
class MemoryItem:
    """
    记忆项数据类
    表示存储在记忆系统中的单个记忆单元
    """

    id: str
    """记忆项唯一标识符"""

    type: str
    """记忆项类型（如：session, message, intent等）"""

    data: Dict[str, Any]
    """记忆项核心数据"""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """记忆项元数据"""

    created_at: datetime = field(default_factory=datetime.now)
    """创建时间"""

    updated_at: datetime = field(default_factory=datetime.now)
    """更新时间"""

    embedding: Optional[list] = None
    """向量嵌入（用于向量搜索）"""

    def __post_init__(self):
        """
        后初始化处理
        """
        # 确保ID为字符串
        self.id = str(self.id)

        # 确保类型为小写
        self.type = self.type.lower()

        # 确保数据为字典
        if not isinstance(self.data, dict):
            raise ValueError(f"data必须是字典类型，实际类型: {type(self.data)}")

        # 确保元数据为字典
        if not isinstance(self.metadata, dict):
            raise ValueError(f"metadata必须是字典类型，实际类型: {type(self.metadata)}")

        # 确保时间戳为datetime类型
        if not isinstance(self.created_at, datetime):
            raise ValueError(f"created_at必须是datetime类型，实际类型: {type(self.created_at)}")

        if not isinstance(self.updated_at, datetime):
            raise ValueError(f"updated_at必须是datetime类型，实际类型: {type(self.updated_at)}")

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典

        Returns:
            Dict[str, Any]: 字典表示
        """
        return {
            "id": self.id,
            "type": self.type,
            "data": self.data,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "embedding": self.embedding,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryItem":
        """
        从字典创建MemoryItem

        Args:
            data: 字典数据

        Returns:
            MemoryItem: 创建的MemoryItem实例
        """
        # 处理时间戳
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            type=data.get("type", "unknown"),
            data=data.get("data", {}),
            metadata=data.get("metadata", {}),
            created_at=created_at or datetime.now(),
            updated_at=updated_at or datetime.now(),
            embedding=data.get("embedding"),
        )

    def update(self, **kwargs):
        """
        更新记忆项属性

        Args:
            **kwargs: 要更新的属性
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        # 自动更新更新时间
        self.updated_at = datetime.now()

    def get_data_field(self, field_name: str, default: Any = None) -> Any:
        """
        获取数据字段的值

        Args:
            field_name: 字段名
            default: 默认值

        Returns:
            Any: 字段值
        """
        return self.data.get(field_name, default)

    def set_data_field(self, field_name: str, value: Any):
        """
        设置数据字段的值

        Args:
            field_name: 字段名
            value: 字段值
        """
        self.data[field_name] = value
        self.updated_at = datetime.now()

    def get_metadata_field(self, field_name: str, default: Any = None) -> Any:
        """
        获取元数据字段的值

        Args:
            field_name: 字段名
            default: 默认值

        Returns:
            Any: 字段值
        """
        return self.metadata.get(field_name, default)

    def set_metadata_field(self, field_name: str, value: Any):
        """
        设置元数据字段的值

        Args:
            field_name: 字段名
            value: 字段值
        """
        self.metadata[field_name] = value
        self.updated_at = datetime.now()

    def is_type(self, item_type: str) -> bool:
        """
        检查记忆项类型

        Args:
            item_type: 类型名称

        Returns:
            bool: 是否为指定类型
        """
        return self.type == item_type

    def has_embedding(self) -> bool:
        """
        检查是否有向量嵌入

        Returns:
            bool: 是否有向量嵌入
        """
        return self.embedding is not None and len(self.embedding) > 0