"""
会话数据模型
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import String, Text, DateTime, Enum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.models.database import Base


class Session(Base):
    """
    会话模型
    表示一个用户与智能体的对话会话
    """
    __tablename__ = "sessions"

    # 主键
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="会话ID"
    )

    # 用户标识（可为空，支持匿名会话）
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        index=True,
        comment="用户ID"
    )

    # 会话标题
    title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="会话标题"
    )

    # 创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        comment="创建时间"
    )

    # 更新时间
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment="更新时间"
    )

    # 会话状态
    status: Mapped[str] = mapped_column(
        Enum("active", "paused", "completed", name="session_status"),
        default="active",
        nullable=False,
        comment="会话状态"
    )

    # 当前活跃智能体
    active_agent: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="当前活跃智能体"
    )

    # 会话元数据（JSON格式）
    metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="会话元数据"
    )

    # 关系
    messages = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Message.created_at.asc()"
    )

    todo_lists = relationship(
        "TodoList",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Session(id='{self.id}', title='{self.title}', status='{self.status}')>"

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典
        """
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "status": self.status,
            "active_agent": self.active_agent,
            "metadata": self.metadata,
            "message_count": len(self.messages) if self.messages else 0,
        }

    @property
    def is_active(self) -> bool:
        """
        是否活跃会话
        """
        return self.status == "active"

    @property
    def is_paused(self) -> bool:
        """
        是否暂停会话
        """
        return self.status == "paused"

    @property
    def is_completed(self) -> bool:
        """
        是否已完成会话
        """
        return self.status == "completed"

    def update_title_from_messages(self, max_messages: int = 5) -> None:
        """
        根据消息内容更新会话标题
        """
        if not self.messages or len(self.messages) == 0:
            return

        # 获取前几条用户消息
        user_messages = [
            msg for msg in self.messages[:max_messages]
            if msg.role == "user"
        ]

        if user_messages:
            first_message = user_messages[0]
            content = first_message.content
            if content and len(content) > 50:
                self.title = content[:47] + "..."
            elif content:
                self.title = content
            else:
                self.title = "新会话"

    def get_last_message(self) -> Optional["Message"]:
        """
        获取最后一条消息
        """
        if not self.messages:
            return None
        return self.messages[-1]

    def get_message_count_by_role(self, role: str) -> int:
        """
        按角色统计消息数量
        """
        if not self.messages:
            return 0
        return len([msg for msg in self.messages if msg.role == role])