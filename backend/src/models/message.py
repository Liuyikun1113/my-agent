"""
消息数据模型
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import String, Text, DateTime, Enum, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.models.database import Base


class Message(Base):
    """
    消息模型
    表示会话中的一条消息
    """
    __tablename__ = "messages"

    # 主键
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="消息ID"
    )

    # 外键：会话ID
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="会话ID"
    )

    # 消息角色
    role: Mapped[str] = mapped_column(
        Enum("user", "assistant", "system", "tool", name="message_role"),
        nullable=False,
        comment="消息角色"
    )

    # 消息内容
    content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="消息内容"
    )

    # 工具调用（JSON格式）
    tool_calls: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON,
        nullable=True,
        comment="工具调用"
    )

    # 工具调用结果（JSON格式）
    tool_results: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON,
        nullable=True,
        comment="工具调用结果"
    )

    # 创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        comment="创建时间"
    )

    # 父消息ID（用于消息链）
    parent_message_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        comment="父消息ID"
    )

    # 消息元数据（JSON格式）
    metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="消息元数据"
    )

    # 意图分类结果
    intent: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="意图分类"
    )

    # 意图置信度
    intent_confidence: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        comment="意图置信度"
    )

    # 处理状态
    processing_status: Mapped[str] = mapped_column(
        Enum("pending", "processing", "completed", "failed", name="processing_status"),
        default="pending",
        nullable=False,
        comment="处理状态"
    )

    # 错误信息
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="错误信息"
    )

    # 关系
    session: Mapped["Session"] = relationship(
        "Session",
        back_populates="messages",
        lazy="joined"
    )

    # 自引用关系：父消息和子消息
    parent_message: Mapped[Optional["Message"]] = relationship(
        "Message",
        remote_side=[id],
        backref="child_messages",
        foreign_keys=[parent_message_id],
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Message(id='{self.id}', role='{self.role}', session='{self.session_id}')>"

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典
        """
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "tool_calls": self.tool_calls,
            "tool_results": self.tool_results,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "parent_message_id": self.parent_message_id,
            "metadata": self.metadata,
            "intent": self.intent,
            "intent_confidence": self.intent_confidence,
            "processing_status": self.processing_status,
            "error_message": self.error_message,
        }

    @property
    def is_user_message(self) -> bool:
        """
        是否用户消息
        """
        return self.role == "user"

    @property
    def is_assistant_message(self) -> bool:
        """
        是否助手消息
        """
        return self.role == "assistant"

    @property
    def is_system_message(self) -> bool:
        """
        是否系统消息
        """
        return self.role == "system"

    @property
    def is_tool_message(self) -> bool:
        """
        是否工具消息
        """
        return self.role == "tool"

    @property
    def has_tool_calls(self) -> bool:
        """
        是否有工具调用
        """
        return bool(self.tool_calls)

    @property
    def has_tool_results(self) -> bool:
        """
        是否有工具调用结果
        """
        return bool(self.tool_results)

    def add_tool_call(self, tool_name: str, tool_input: Dict[str, Any], call_id: str = None) -> None:
        """
        添加工具调用
        """
        if self.tool_calls is None:
            self.tool_calls = []

        call_id = call_id or str(uuid.uuid4())
        tool_call = {
            "id": call_id,
            "type": "function",
            "function": {
                "name": tool_name,
                "arguments": tool_input,
            }
        }

        self.tool_calls.append(tool_call)

    def add_tool_result(self, tool_call_id: str, result: Any, is_error: bool = False) -> None:
        """
        添加工具调用结果
        """
        if self.tool_results is None:
            self.tool_results = []

        tool_result = {
            "tool_call_id": tool_call_id,
            "content": str(result),
            "is_error": is_error,
            "timestamp": datetime.utcnow().isoformat()
        }

        self.tool_results.append(tool_result)

    def mark_as_processing(self) -> None:
        """
        标记为处理中
        """
        self.processing_status = "processing"

    def mark_as_completed(self) -> None:
        """
        标记为已完成
        """
        self.processing_status = "completed"

    def mark_as_failed(self, error_message: str) -> None:
        """
        标记为失败
        """
        self.processing_status = "failed"
        self.error_message = error_message

    def set_intent(self, intent: str, confidence: float) -> None:
        """
        设置意图分类结果
        """
        self.intent = intent
        self.intent_confidence = confidence