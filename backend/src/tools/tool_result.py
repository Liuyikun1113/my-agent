"""
工具结果封装
统一工具执行结果的格式和结构
"""
import logging
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ResultStatus(Enum):
    """结果状态"""
    SUCCESS = auto()        # 成功
    FAILURE = auto()        # 失败
    PARTIAL_SUCCESS = auto()  # 部分成功
    TIMEOUT = auto()        # 超时
    CANCELLED = auto()      # 已取消
    PENDING = auto()        # 等待中


class ExecutionContext(BaseModel):
    """执行上下文"""
    tool_name: str = Field(..., description="工具名称")
    tool_version: str = Field(..., description="工具版本")
    execution_id: str = Field(..., description="执行ID")
    user_id: Optional[str] = Field(None, description="用户ID")
    session_id: Optional[str] = Field(None, description="会话ID")
    agent_id: Optional[str] = Field(None, description="智能体ID")
    request_id: Optional[str] = Field(None, description="请求ID")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


@dataclass
class ToolResult:
    """工具结果封装"""

    # 基础信息
    status: ResultStatus                    # 结果状态
    message: str                            # 结果消息
    data: Optional[Any] = None              # 返回数据

    # 上下文信息
    context: Optional[ExecutionContext] = None  # 执行上下文

    # 执行信息
    execution_time: float = 0.0             # 执行时间（秒）
    start_time: Optional[datetime] = None   # 开始时间
    end_time: Optional[datetime] = None     # 结束时间

    # 错误信息
    error_code: Optional[str] = None        # 错误代码
    error_details: Optional[Dict[str, Any]] = None  # 错误详情
    stack_trace: Optional[str] = None       # 堆栈跟踪

    # 统计信息
    retry_count: int = 0                    # 重试次数
    cache_hit: bool = False                 # 是否缓存命中
    fallback_used: bool = False             # 是否使用了降级

    # 性能指标
    memory_usage: Optional[float] = None    # 内存使用量（MB）
    cpu_usage: Optional[float] = None       # CPU使用率（%）

    # 审计信息
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)  # 审计追踪

    def __post_init__(self):
        """初始化后处理"""
        if self.start_time and self.end_time:
            self.execution_time = (self.end_time - self.start_time).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "status": self.status.name,
            "message": self.message,
            "data": self.data,
            "execution_time": self.execution_time,
            "retry_count": self.retry_count,
            "cache_hit": self.cache_hit,
            "fallback_used": self.fallback_used,
        }

        if self.context:
            result["context"] = self.context.dict()

        if self.start_time:
            result["start_time"] = self.start_time.isoformat()

        if self.end_time:
            result["end_time"] = self.end_time.isoformat()

        if self.error_code:
            result["error_code"] = self.error_code

        if self.error_details:
            result["error_details"] = self.error_details

        if self.stack_trace:
            result["stack_trace"] = self.stack_trace

        if self.memory_usage is not None:
            result["memory_usage"] = self.memory_usage

        if self.cpu_usage is not None:
            result["cpu_usage"] = self.cpu_usage

        if self.audit_trail:
            result["audit_trail"] = self.audit_trail

        return result

    def is_success(self) -> bool:
        """是否成功"""
        return self.status == ResultStatus.SUCCESS

    def is_failure(self) -> bool:
        """是否失败"""
        return self.status in [ResultStatus.FAILURE, ResultStatus.TIMEOUT, ResultStatus.CANCELLED]

    def add_audit_entry(
        self,
        action: str,
        details: Dict[str, Any],
        timestamp: Optional[datetime] = None,
    ):
        """添加审计条目"""
        entry = {
            "action": action,
            "details": details,
            "timestamp": timestamp or datetime.now(),
        }
        self.audit_trail.append(entry)

    def merge(self, other: "ToolResult") -> "ToolResult":
        """
        合并两个结果

        Args:
            other: 另一个结果

        Returns:
            ToolResult: 合并后的结果
        """
        # 确定合并后的状态
        if self.status == ResultStatus.SUCCESS and other.status == ResultStatus.SUCCESS:
            merged_status = ResultStatus.SUCCESS
        elif self.status == ResultStatus.FAILURE or other.status == ResultStatus.FAILURE:
            merged_status = ResultStatus.FAILURE
        else:
            merged_status = ResultStatus.PARTIAL_SUCCESS

        # 合并消息
        merged_message = f"{self.message}; {other.message}"

        # 合并数据
        merged_data = None
        if self.data is not None and other.data is not None:
            if isinstance(self.data, dict) and isinstance(other.data, dict):
                merged_data = {**self.data, **other.data}
            elif isinstance(self.data, list) and isinstance(other.data, list):
                merged_data = self.data + other.data
            else:
                merged_data = [self.data, other.data]
        elif self.data is not None:
            merged_data = self.data
        elif other.data is not None:
            merged_data = other.data

        # 创建合并结果
        merged_result = ToolResult(
            status=merged_status,
            message=merged_message,
            data=merged_data,
            context=self.context or other.context,
            execution_time=self.execution_time + other.execution_time,
            retry_count=self.retry_count + other.retry_count,
            cache_hit=self.cache_hit or other.cache_hit,
            fallback_used=self.fallback_used or other.fallback_used,
        )

        # 合并审计追踪
        merged_result.audit_trail = self.audit_trail + other.audit_trail

        return merged_result


# 结果构建器

class ToolResultBuilder:
    """工具结果构建器"""

    def __init__(self, tool_name: str, execution_id: str):
        self._result = ToolResult(
            status=ResultStatus.PENDING,
            message="执行尚未开始",
            context=ExecutionContext(
                tool_name=tool_name,
                tool_version="1.0.0",
                execution_id=execution_id,
            ),
        )
        self._start_time = None

    def start(self):
        """开始执行"""
        self._start_time = datetime.now()
        self._result.start_time = self._start_time
        self._result.status = ResultStatus.PENDING
        self._result.message = "执行中"
        self.add_audit_entry("execution_started", {"timestamp": self._start_time})

    def success(
        self,
        message: str,
        data: Optional[Any] = None,
        **kwargs,
    ) -> ToolResult:
        """
        标记为成功

        Args:
            message: 成功消息
            data: 返回数据
            **kwargs: 其他结果字段

        Returns:
            ToolResult: 完成的结果
        """
        self._complete(ResultStatus.SUCCESS, message, data, **kwargs)
        logger.info(f"工具执行成功: {self._result.context.tool_name}, 消息: {message}")
        return self._result

    def failure(
        self,
        message: str,
        error_code: str = "TOOL_ERROR",
        error_details: Optional[Dict[str, Any]] = None,
        stack_trace: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        """
        标记为失败

        Args:
            message: 失败消息
            error_code: 错误代码
            error_details: 错误详情
            stack_trace: 堆栈跟踪
            **kwargs: 其他结果字段

        Returns:
            ToolResult: 完成的结果
        """
        self._complete(
            ResultStatus.FAILURE,
            message,
            error_code=error_code,
            error_details=error_details,
            stack_trace=stack_trace,
            **kwargs,
        )
        logger.error(
            f"工具执行失败: {self._result.context.tool_name}, "
            f"错误代码: {error_code}, 消息: {message}"
        )
        return self._result

    def timeout(
        self,
        message: str = "执行超时",
        timeout_seconds: Optional[float] = None,
        **kwargs,
    ) -> ToolResult:
        """
        标记为超时

        Args:
            message: 超时消息
            timeout_seconds: 超时时间（秒）
            **kwargs: 其他结果字段

        Returns:
            ToolResult: 完成的结果
        """
        details = {}
        if timeout_seconds:
            details["timeout_seconds"] = timeout_seconds

        self._complete(
            ResultStatus.TIMEOUT,
            message,
            error_code="TIMEOUT",
            error_details=details,
            **kwargs,
        )
        logger.warning(f"工具执行超时: {self._result.context.tool_name}")
        return self._result

    def cancelled(
        self,
        message: str = "执行已取消",
        reason: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        """
        标记为已取消

        Args:
            message: 取消消息
            reason: 取消原因
            **kwargs: 其他结果字段

        Returns:
            ToolResult: 完成的结果
        """
        details = {}
        if reason:
            details["reason"] = reason

        self._complete(
            ResultStatus.CANCELLED,
            message,
            error_code="CANCELLED",
            error_details=details,
            **kwargs,
        )
        logger.info(f"工具执行取消: {self._result.context.tool_name}")
        return self._result

    def partial_success(
        self,
        message: str,
        data: Optional[Any] = None,
        successful_parts: Optional[List[str]] = None,
        failed_parts: Optional[List[str]] = None,
        **kwargs,
    ) -> ToolResult:
        """
        标记为部分成功

        Args:
            message: 部分成功消息
            data: 返回数据
            successful_parts: 成功的部分
            failed_parts: 失败的部分
            **kwargs: 其他结果字段

        Returns:
            ToolResult: 完成的结果
        """
        details = {}
        if successful_parts:
            details["successful_parts"] = successful_parts
        if failed_parts:
            details["failed_parts"] = failed_parts

        self._complete(
            ResultStatus.PARTIAL_SUCCESS,
            message,
            data=data,
            error_details=details if details else None,
            **kwargs,
        )
        logger.warning(
            f"工具执行部分成功: {self._result.context.tool_name}, "
            f"成功部分: {successful_parts}, 失败部分: {failed_parts}"
        )
        return self._result

    def _complete(
        self,
        status: ResultStatus,
        message: str,
        data: Optional[Any] = None,
        **kwargs,
    ):
        """完成结果构建"""
        self._result.end_time = datetime.now()
        self._result.status = status
        self._result.message = message
        self._result.data = data

        # 计算执行时间
        if self._start_time and self._result.end_time:
            self._result.execution_time = (
                self._result.end_time - self._start_time
            ).total_seconds()

        # 设置其他字段
        for key, value in kwargs.items():
            if hasattr(self._result, key):
                setattr(self._result, key, value)
            else:
                logger.warning(f"尝试设置不存在的字段: {key}")

        # 添加完成审计条目
        self.add_audit_entry("execution_completed", {
            "status": status.name,
            "execution_time": self._result.execution_time,
            "timestamp": self._result.end_time,
        })

    def set_context_field(self, field_name: str, value: Any):
        """设置上下文字段"""
        if self._result.context:
            if hasattr(self._result.context, field_name):
                setattr(self._result.context, field_name, value)
            else:
                # 添加到元数据
                self._result.context.metadata[field_name] = value

    def add_audit_entry(
        self,
        action: str,
        details: Dict[str, Any],
        timestamp: Optional[datetime] = None,
    ):
        """添加审计条目"""
        self._result.add_audit_entry(action, details, timestamp)

    def update_field(self, field_name: str, value: Any):
        """更新结果字段"""
        if hasattr(self._result, field_name):
            setattr(self._result, field_name, value)
        else:
            logger.warning(f"尝试更新不存在的字段: {field_name}")

    def get_result(self) -> ToolResult:
        """获取当前结果"""
        return self._result


# 结果处理器

class ToolResultProcessor:
    """工具结果处理器"""

    @staticmethod
    def validate_result(result: ToolResult) -> bool:
        """
        验证结果是否有效

        Args:
            result: 工具结果

        Returns:
            bool: 是否有效
        """
        try:
            # 检查必需字段
            if not result.status:
                return False

            if not result.message:
                return False

            if result.execution_time < 0:
                return False

            # 检查上下文
            if result.context:
                if not result.context.tool_name:
                    return False

                if not result.context.execution_id:
                    return False

            return True

        except Exception:
            return False

    @staticmethod
    def extract_data(result: ToolResult, path: str = None) -> Any:
        """
        从结果中提取数据

        Args:
            result: 工具结果
            path: 数据路径（例如 "data.items"）

        Returns:
            Any: 提取的数据
        """
        if not result.data:
            return None

        if not path:
            return result.data

        # 简化实现：只支持一层路径
        if "." in path:
            parts = path.split(".", 1)
            current = result.data
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                elif isinstance(current, list):
                    try:
                        index = int(part)
                        if 0 <= index < len(current):
                            current = current[index]
                        else:
                            return None
                    except ValueError:
                        return None
                else:
                    return None
            return current

        # 直接访问
        if isinstance(result.data, dict) and path in result.data:
            return result.data[path]

        return None

    @staticmethod
    def format_for_display(result: ToolResult) -> Dict[str, Any]:
        """
        格式化结果用于显示

        Args:
            result: 工具结果

        Returns:
            Dict[str, Any]: 格式化结果
        """
        formatted = result.to_dict()

        # 简化显示版本
        display = {
            "tool": result.context.tool_name if result.context else "Unknown",
            "status": result.status.name,
            "message": result.message,
            "execution_time": f"{result.execution_time:.3f}s",
        }

        if result.data is not None:
            display["has_data"] = True
            if isinstance(result.data, (str, int, float, bool)):
                display["data"] = result.data
            else:
                display["data_type"] = type(result.data).__name__

        if result.error_code:
            display["error_code"] = result.error_code

        return display

    @staticmethod
    def create_summary(results: List[ToolResult]) -> Dict[str, Any]:
        """
        创建结果摘要

        Args:
            results: 结果列表

        Returns:
            Dict[str, Any]: 摘要信息
        """
        if not results:
            return {"total": 0}

        total = len(results)
        success_count = sum(1 for r in results if r.is_success())
        failure_count = sum(1 for r in results if r.is_failure())
        total_time = sum(r.execution_time for r in results)
        avg_time = total_time / total if total > 0 else 0

        return {
            "total": total,
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": round(success_count / total * 100, 2) if total > 0 else 0,
            "total_execution_time": round(total_time, 3),
            "average_execution_time": round(avg_time, 3),
            "results_by_status": {
                status.name: sum(1 for r in results if r.status == status)
                for status in ResultStatus
            },
        }