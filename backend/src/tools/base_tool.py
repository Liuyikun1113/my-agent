"""
工具基类
定义所有工具的统一接口和基础功能
"""
import logging
import asyncio
from typing import Any, Dict, List, Optional, Type, Union, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ToolCategory(Enum):
    """工具类别"""
    GENERAL = auto()        # 通用工具
    SEARCH = auto()         # 搜索工具
    CALCULATION = auto()    # 计算工具
    FILE_OPERATION = auto() # 文件操作
    NETWORK = auto()        # 网络工具
    DATABASE = auto()       # 数据库工具
    API_CALL = auto()       # API调用
    SYSTEM = auto()         # 系统工具
    CUSTOM = auto()         # 自定义工具


class ToolPermission(Enum):
    """工具权限级别"""
    PUBLIC = auto()         # 公开，无需认证
    USER = auto()           # 用户级别
    ADMIN = auto()          # 管理员级别
    SYSTEM = auto()         # 系统内部使用


@dataclass
class ToolMetadata:
    """工具元数据"""
    name: str                      # 工具名称
    description: str               # 工具描述
    version: str = "1.0.0"         # 工具版本
    category: ToolCategory = ToolCategory.GENERAL  # 工具类别
    permissions: List[ToolPermission] = field(default_factory=lambda: [ToolPermission.PUBLIC])  # 权限要求
    tags: List[str] = field(default_factory=list)  # 标签
    author: str = "Unknown"        # 作者
    created_at: datetime = field(default_factory=datetime.now)  # 创建时间
    updated_at: datetime = field(default_factory=datetime.now)  # 更新时间

    # 执行限制
    rate_limit: Optional[int] = None  # 每秒请求限制
    timeout: Optional[float] = None   # 超时时间（秒）
    max_input_length: Optional[int] = None  # 最大输入长度

    # 依赖关系
    dependencies: List[str] = field(default_factory=list)  # 依赖的工具名称
    required_services: List[str] = field(default_factory=list)  # 需要的服务

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "category": self.category.name,
            "permissions": [p.name for p in self.permissions],
            "tags": self.tags,
            "author": self.author,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "rate_limit": self.rate_limit,
            "timeout": self.timeout,
            "max_input_length": self.max_input_length,
            "dependencies": self.dependencies,
            "required_services": self.required_services,
        }


class ToolInput(BaseModel):
    """工具输入模型"""
    pass


class ToolOutput(BaseModel):
    """工具输出基类"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="结果消息")
    data: Optional[Any] = Field(None, description="返回数据")
    error_code: Optional[str] = Field(None, description="错误代码")
    execution_time: float = Field(..., description="执行时间（秒）")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ToolError(Exception):
    """工具错误异常"""

    def __init__(
        self,
        message: str,
        error_code: str = "TOOL_ERROR",
        details: Optional[Dict[str, Any]] = None,
        tool_name: Optional[str] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.tool_name = tool_name
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details,
            "tool_name": self.tool_name,
        }


class BaseTool(ABC):
    """工具基类"""

    def __init__(self, metadata: ToolMetadata):
        self.metadata = metadata
        self._execution_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._total_execution_time = 0.0

    @abstractmethod
    async def _execute_async(self, input_data: Any, **kwargs) -> ToolOutput:
        """
        异步执行工具逻辑（子类必须实现）

        Args:
            input_data: 输入数据
            **kwargs: 额外参数

        Returns:
            ToolOutput: 工具输出
        """
        pass

    def _execute_sync(self, input_data: Any, **kwargs) -> ToolOutput:
        """
        同步执行工具逻辑（子类可选实现）

        Args:
            input_data: 输入数据
            **kwargs: 额外参数

        Returns:
            ToolOutput: 工具输出
        """
        # 默认实现：包装异步方法
        async def async_wrapper():
            return await self._execute_async(input_data, **kwargs)

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(async_wrapper())

    async def execute(
        self,
        input_data: Any,
        async_mode: bool = True,
        **kwargs
    ) -> ToolOutput:
        """
        执行工具

        Args:
            input_data: 输入数据
            async_mode: 是否异步执行
            **kwargs: 额外参数

        Returns:
            ToolOutput: 工具输出
        """
        start_time = datetime.now()
        self._execution_count += 1

        try:
            # 验证输入
            self._validate_input(input_data)

            # 检查权限
            self._check_permissions(kwargs.get("user_context"))

            # 执行工具
            if async_mode:
                result = await self._execute_async(input_data, **kwargs)
            else:
                result = self._execute_sync(input_data, **kwargs)

            # 更新统计
            execution_time = (datetime.now() - start_time).total_seconds()
            self._total_execution_time += execution_time
            self._success_count += 1

            # 设置执行时间
            result.execution_time = execution_time

            logger.info(
                f"工具执行成功: {self.metadata.name}, "
                f"执行时间: {execution_time:.3f}秒"
            )

            return result

        except ToolError as e:
            # 工具已知错误
            execution_time = (datetime.now() - start_time).total_seconds()
            self._failure_count += 1

            logger.error(
                f"工具执行失败: {self.metadata.name}, "
                f"错误: {e.error_code}: {e.message}, "
                f"执行时间: {execution_time:.3f}秒"
            )

            return ToolOutput(
                success=False,
                message=e.message,
                error_code=e.error_code,
                execution_time=execution_time,
            )

        except Exception as e:
            # 未知错误
            execution_time = (datetime.now() - start_time).total_seconds()
            self._failure_count += 1

            logger.exception(
                f"工具执行异常: {self.metadata.name}, "
                f"异常: {type(e).__name__}: {str(e)}, "
                f"执行时间: {execution_time:.3f}秒"
            )

            return ToolOutput(
                success=False,
                message=f"工具执行异常: {str(e)}",
                error_code="UNKNOWN_ERROR",
                execution_time=execution_time,
            )

    def _validate_input(self, input_data: Any):
        """
        验证输入数据

        Args:
            input_data: 输入数据

        Raises:
            ToolError: 输入验证失败
        """
        # 检查输入长度
        if self.metadata.max_input_length:
            input_str = str(input_data)
            if len(input_str) > self.metadata.max_input_length:
                raise ToolError(
                    message=f"输入数据过长，最大允许长度: {self.metadata.max_input_length}",
                    error_code="INPUT_TOO_LONG",
                    details={
                        "input_length": len(input_str),
                        "max_length": self.metadata.max_input_length,
                    },
                    tool_name=self.metadata.name,
                )

        # 子类可以重写此方法进行更复杂的验证
        self._custom_validate_input(input_data)

    def _custom_validate_input(self, input_data: Any):
        """
        自定义输入验证（子类可以重写）

        Args:
            input_data: 输入数据
        """
        pass

    def _check_permissions(self, user_context: Optional[Dict[str, Any]] = None):
        """
        检查用户权限

        Args:
            user_context: 用户上下文

        Raises:
            ToolError: 权限不足
        """
        # 如果工具需要权限但未提供用户上下文
        if ToolPermission.PUBLIC not in self.metadata.permissions and not user_context:
            raise ToolError(
                message="此工具需要用户认证",
                error_code="AUTHENTICATION_REQUIRED",
                tool_name=self.metadata.name,
            )

        # 检查具体权限（简化实现）
        # 在实际应用中，这里应该检查用户角色和权限
        if user_context:
            user_permissions = user_context.get("permissions", [])
            for required_perm in self.metadata.permissions:
                if required_perm.name not in user_permissions:
                    raise ToolError(
                        message=f"权限不足，需要: {required_perm.name}",
                        error_code="PERMISSION_DENIED",
                        tool_name=self.metadata.name,
                    )

    def get_stats(self) -> Dict[str, Any]:
        """获取工具统计信息"""
        success_rate = 0.0
        if self._execution_count > 0:
            success_rate = self._success_count / self._execution_count * 100

        avg_execution_time = 0.0
        if self._execution_count > 0:
            avg_execution_time = self._total_execution_time / self._execution_count

        return {
            "name": self.metadata.name,
            "execution_count": self._execution_count,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "success_rate": round(success_rate, 2),
            "total_execution_time": round(self._total_execution_time, 3),
            "average_execution_time": round(avg_execution_time, 3),
            "last_updated": self.metadata.updated_at.isoformat(),
        }

    def reset_stats(self):
        """重置统计信息"""
        self._execution_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._total_execution_time = 0.0

    def update_metadata(self, **kwargs):
        """更新工具元数据"""
        for key, value in kwargs.items():
            if hasattr(self.metadata, key):
                setattr(self.metadata, key, value)
            else:
                logger.warning(f"尝试更新不存在的元数据字段: {key}")

        self.metadata.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示"""
        return {
            "metadata": self.metadata.to_dict(),
            "stats": self.get_stats(),
        }

    def __str__(self) -> str:
        return f"Tool(name={self.metadata.name}, category={self.metadata.category.name})"

    def __repr__(self) -> str:
        return self.__str__()


# 装饰器：将普通函数转换为工具

def tool(
    name: str,
    description: str,
    category: ToolCategory = ToolCategory.GENERAL,
    permissions: Optional[List[ToolPermission]] = None,
    **metadata_kwargs,
):
    """
    工具装饰器：将普通函数转换为工具

    Args:
        name: 工具名称
        description: 工具描述
        category: 工具类别
        permissions: 权限要求
        **metadata_kwargs: 其他元数据参数

    Returns:
        装饰器函数
    """
    def decorator(func: Callable):
        # 创建元数据
        metadata = ToolMetadata(
            name=name,
            description=description,
            category=category,
            permissions=permissions or [ToolPermission.PUBLIC],
            **metadata_kwargs,
        )

        # 创建工具类
        class FunctionTool(BaseTool):
            def __init__(self):
                super().__init__(metadata)

            async def _execute_async(self, input_data: Any, **kwargs) -> ToolOutput:
                try:
                    # 调用原始函数
                    if asyncio.iscoroutinefunction(func):
                        result = await func(input_data, **kwargs)
                    else:
                        result = func(input_data, **kwargs)

                    return ToolOutput(
                        success=True,
                        message="执行成功",
                        data=result,
                        execution_time=0.0,  # 会在execute方法中设置
                    )

                except ToolError as e:
                    # 重新抛出ToolError
                    raise
                except Exception as e:
                    # 包装其他异常
                    raise ToolError(
                        message=f"函数执行失败: {str(e)}",
                        error_code="FUNCTION_ERROR",
                        tool_name=name,
                    )

        # 创建工具实例
        tool_instance = FunctionTool()

        # 添加工具实例作为函数的属性
        func.tool_instance = tool_instance
        func.metadata = metadata

        # 返回原始函数（现在有了工具属性）
        return func

    return decorator


# 工具工厂

class ToolFactory:
    """工具工厂"""

    @staticmethod
    def create_tool(
        tool_class: Type[BaseTool],
        *args,
        **kwargs
    ) -> BaseTool:
        """
        创建工具实例

        Args:
            tool_class: 工具类
            *args: 构造函数参数
            **kwargs: 构造函数关键字参数

        Returns:
            BaseTool: 工具实例
        """
        try:
            tool_instance = tool_class(*args, **kwargs)
            logger.info(f"工具创建成功: {tool_instance.metadata.name}")
            return tool_instance
        except Exception as e:
            logger.error(f"工具创建失败: {tool_class.__name__}, 错误: {str(e)}")
            raise

    @staticmethod
    def create_from_function(
        func: Callable,
        name: str,
        description: str,
        **metadata_kwargs,
    ) -> BaseTool:
        """
        从函数创建工具

        Args:
            func: 函数
            name: 工具名称
            description: 工具描述
            **metadata_kwargs: 元数据参数

        Returns:
            BaseTool: 工具实例
        """
        # 使用装饰器创建工具
        decorated_func = tool(
            name=name,
            description=description,
            **metadata_kwargs,
        )(func)

        # 返回工具实例
        return decorated_func.tool_instance

    @staticmethod
    def validate_tool(tool_instance: BaseTool) -> bool:
        """
        验证工具是否有效

        Args:
            tool_instance: 工具实例

        Returns:
            bool: 是否有效
        """
        try:
            # 检查元数据
            if not tool_instance.metadata.name:
                return False

            if not tool_instance.metadata.description:
                return False

            # 检查工具方法是否存在
            if not hasattr(tool_instance, "_execute_async"):
                return False

            # 检查工具类别
            if not isinstance(tool_instance.metadata.category, ToolCategory):
                return False

            return True

        except Exception:
            return False