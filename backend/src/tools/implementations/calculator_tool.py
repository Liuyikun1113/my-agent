"""
计算器工具示例
演示如何使用工具基类和装饰器
"""
import logging
import math
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from datetime import datetime

from tools.base_tool import (
    BaseTool, ToolMetadata, ToolCategory, ToolPermission, ToolError, ToolOutput
)
from tools.tool_result import ToolResult, ToolResultBuilder, ResultStatus
from tools.decorators.retry_decorator import retry_with_config
from tools.decorators.circuit_breaker import circuit_breaker_with_config
from tools.decorators.fallback_decorator import fallback_default_value

logger = logging.getLogger(__name__)


@dataclass
class CalculatorInput:
    """计算器输入"""
    operation: str  # 操作类型：add, subtract, multiply, divide, power, sqrt
    a: float  # 第一个操作数
    b: Optional[float] = None  # 第二个操作数（某些操作不需要）
    precision: int = 2  # 结果精度（小数位数）


class CalculatorTool(BaseTool):
    """计算器工具"""

    def __init__(self):
        metadata = ToolMetadata(
            name="calculator",
            description="执行基本数学运算：加、减、乘、除、幂、平方根",
            version="1.0.0",
            category=ToolCategory.CALCULATION,
            permissions=[ToolPermission.PUBLIC],
            tags=["math", "calculation", "utility"],
            author="Multi-Agent Framework",
            rate_limit=100,  # 每秒100次调用
            timeout=10.0,  # 10秒超时
            max_input_length=1000,
        )
        super().__init__(metadata)

    async def _execute_async(self, input_data: Any, **kwargs) -> ToolOutput:
        """
        执行计算

        Args:
            input_data: 计算器输入
            **kwargs: 额外参数

        Returns:
            ToolOutput: 计算结果
        """
        # 构建结果
        builder = ToolResultBuilder(
            tool_name=self.metadata.name,
            execution_id=kwargs.get("execution_id", f"calc_{datetime.now().timestamp()}")
        )
        builder.start()

        try:
            # 解析输入
            if isinstance(input_data, dict):
                calc_input = CalculatorInput(**input_data)
            elif isinstance(input_data, CalculatorInput):
                calc_input = input_data
            else:
                raise ToolError(
                    message="输入格式错误，应为字典或CalculatorInput对象",
                    error_code="INVALID_INPUT",
                    tool_name=self.metadata.name,
                )

            # 验证输入
            self._validate_calculator_input(calc_input)

            # 执行计算
            result = self._perform_calculation(calc_input)

            # 构建成功结果
            return builder.success(
                message=f"计算成功：{calc_input.operation}",
                data={
                    "result": result,
                    "operation": calc_input.operation,
                    "operands": {
                        "a": calc_input.a,
                        "b": calc_input.b,
                    },
                    "precision": calc_input.precision,
                    "formatted_result": f"{result:.{calc_input.precision}f}",
                },
            )

        except ToolError as e:
            # 已知工具错误
            return builder.failure(
                message=e.message,
                error_code=e.error_code,
                error_details=e.details,
            )

        except Exception as e:
            # 未知错误
            logger.exception(f"计算器工具异常: {str(e)}")
            return builder.failure(
                message=f"计算过程中发生错误: {str(e)}",
                error_code="CALCULATION_ERROR",
            )

    def _validate_calculator_input(self, calc_input: CalculatorInput):
        """验证计算器输入"""
        # 检查操作类型
        valid_operations = ["add", "subtract", "multiply", "divide", "power", "sqrt"]
        if calc_input.operation not in valid_operations:
            raise ToolError(
                message=f"无效的操作类型: {calc_input.operation}，有效操作: {valid_operations}",
                error_code="INVALID_OPERATION",
                tool_name=self.metadata.name,
            )

        # 检查第二个操作数是否为空（对于需要两个操作数的操作）
        if calc_input.operation in ["add", "subtract", "multiply", "divide", "power"]:
            if calc_input.b is None:
                raise ToolError(
                    message=f"操作 {calc_input.operation} 需要第二个操作数 b",
                    error_code="MISSING_OPERAND",
                    tool_name=self.metadata.name,
                )

        # 检查除零错误
        if calc_input.operation == "divide" and calc_input.b == 0:
            raise ToolError(
                message="除数不能为零",
                error_code="DIVISION_BY_ZERO",
                tool_name=self.metadata.name,
            )

        # 检查平方根的负数输入
        if calc_input.operation == "sqrt" and calc_input.a < 0:
            raise ToolError(
                message="平方根操作数不能为负数",
                error_code="NEGATIVE_SQRT",
                tool_name=self.metadata.name,
            )

        # 检查精度
        if calc_input.precision < 0 or calc_input.precision > 10:
            raise ToolError(
                message=f"精度必须在0到10之间，当前: {calc_input.precision}",
                error_code="INVALID_PRECISION",
                tool_name=self.metadata.name,
            )

    def _perform_calculation(self, calc_input: CalculatorInput) -> float:
        """执行计算"""
        operation = calc_input.operation
        a = calc_input.a
        b = calc_input.b

        if operation == "add":
            result = a + b
        elif operation == "subtract":
            result = a - b
        elif operation == "multiply":
            result = a * b
        elif operation == "divide":
            result = a / b
        elif operation == "power":
            result = math.pow(a, b)
        elif operation == "sqrt":
            result = math.sqrt(a)
        else:
            raise ToolError(
                message=f"未知操作: {operation}",
                error_code="UNKNOWN_OPERATION",
                tool_name=self.metadata.name,
            )

        # 四舍五入到指定精度
        return round(result, calc_input.precision)

    def _custom_validate_input(self, input_data: Any):
        """自定义输入验证"""
        # 这里可以添加额外的验证逻辑
        pass


# 使用装饰器的版本
@circuit_breaker_with_config(
    failure_threshold=3,
    failure_window=30,
    reset_timeout=60,
    name="calculator_decorated"
)
@retry_with_config(
    max_attempts=2,
    backoff_factor=1.0,
)
@fallback_default_value(
    default_value={"result": 0, "error": "计算失败，使用默认值"},
    exceptions=(Exception,)
)
async def decorated_calculator(
    operation: str,
    a: float,
    b: Optional[float] = None,
    precision: int = 2,
) -> Dict[str, Any]:
    """
    使用装饰器的计算器函数

    Args:
        operation: 操作类型
        a: 第一个操作数
        b: 第二个操作数
        precision: 精度

    Returns:
        Dict[str, Any]: 计算结果
    """
    # 模拟可能的失败
    if operation == "divide" and b == 0:
        raise ValueError("除数不能为零")

    # 执行计算
    calc_input = CalculatorInput(
        operation=operation,
        a=a,
        b=b,
        precision=precision,
    )

    # 创建工具实例
    tool = CalculatorTool()
    result = await tool.execute(calc_input)

    if result.success:
        return result.data
    else:
        raise ToolError(
            message=result.message,
            error_code=result.error_code or "CALCULATION_ERROR",
            tool_name="decorated_calculator",
        )


# 使用工具装饰器的版本
from tools.base_tool import tool


@tool(
    name="simple_calculator",
    description="简单计算器，支持加、减、乘、除",
    category=ToolCategory.CALCULATION,
    permissions=[ToolPermission.PUBLIC],
    rate_limit=50,
    timeout=5.0,
)
async def simple_calculator(
    operation: str,
    a: float,
    b: float,
) -> float:
    """
    简单计算器函数（使用@tool装饰器）

    Args:
        operation: 操作类型 (add, subtract, multiply, divide)
        a: 第一个操作数
        b: 第二个操作数

    Returns:
        float: 计算结果
    """
    operations = {
        "add": lambda x, y: x + y,
        "subtract": lambda x, y: x - y,
        "multiply": lambda x, y: x * y,
        "divide": lambda x, y: x / y if y != 0 else 0,
    }

    if operation not in operations:
        raise ValueError(f"无效的操作: {operation}")

    if operation == "divide" and b == 0:
        raise ValueError("除数不能为零")

    return operations[operation](a, b)


# 同步工具示例
class SynchronousCalculatorTool(BaseTool):
    """同步计算器工具"""

    def __init__(self):
        metadata = ToolMetadata(
            name="sync_calculator",
            description="同步计算器工具",
            version="1.0.0",
            category=ToolCategory.CALCULATION,
            permissions=[ToolPermission.PUBLIC],
        )
        super().__init__(metadata)

    async def _execute_async(self, input_data: Any, **kwargs) -> ToolOutput:
        # 对于同步工具，我们可以调用同步版本
        return self._execute_sync(input_data, **kwargs)

    def _execute_sync(self, input_data: Any, **kwargs) -> ToolOutput:
        """同步执行"""
        builder = ToolResultBuilder(
            tool_name=self.metadata.name,
            execution_id=kwargs.get("execution_id", f"sync_calc_{datetime.now().timestamp()}")
        )
        builder.start()

        try:
            if isinstance(input_data, dict):
                a = input_data.get("a", 0)
                b = input_data.get("b", 0)
                operation = input_data.get("operation", "add")
            else:
                raise ToolError(
                    message="输入必须是字典",
                    error_code="INVALID_INPUT",
                    tool_name=self.metadata.name,
                )

            # 执行计算
            if operation == "add":
                result = a + b
            elif operation == "subtract":
                result = a - b
            elif operation == "multiply":
                result = a * b
            elif operation == "divide":
                if b == 0:
                    raise ToolError(
                        message="除数不能为零",
                        error_code="DIVISION_BY_ZERO",
                        tool_name=self.metadata.name,
                    )
                result = a / b
            else:
                raise ToolError(
                    message=f"无效的操作: {operation}",
                    error_code="INVALID_OPERATION",
                    tool_name=self.metadata.name,
                )

            return builder.success(
                message="同步计算成功",
                data={
                    "result": result,
                    "operation": operation,
                    "a": a,
                    "b": b,
                }
            )

        except ToolError as e:
            return builder.failure(
                message=e.message,
                error_code=e.error_code,
            )

        except Exception as e:
            return builder.failure(
                message=f"同步计算错误: {str(e)}",
                error_code="SYNC_CALC_ERROR",
            )


# 导出工具
__all__ = [
    "CalculatorTool",
    "SynchronousCalculatorTool",
    "decorated_calculator",
    "simple_calculator",
    "CalculatorInput",
]