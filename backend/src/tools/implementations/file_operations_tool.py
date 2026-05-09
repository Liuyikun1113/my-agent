"""
文件操作工具示例
演示文件读写和系统操作
"""
import logging
import os
import shutil
import json
import yaml
import csv
from typing import Any, Dict, List, Optional, Union, BinaryIO
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import aiofiles
import asyncio

from tools.base_tool import (
    BaseTool, ToolMetadata, ToolCategory, ToolPermission, ToolError, ToolOutput
)
from tools.tool_result import ToolResultBuilder
from tools.decorators.retry_decorator import retry_with_config
from tools.decorators.circuit_breaker import circuit_breaker_with_config
from tools.decorators.fallback_decorator import fallback_default_value

logger = logging.getLogger(__name__)


@dataclass
class FileReadRequest:
    """文件读取请求"""
    file_path: str                    # 文件路径
    encoding: str = "utf-8"          # 文件编码
    read_mode: str = "text"          # 读取模式：text, binary, lines
    max_size: Optional[int] = None   # 最大文件大小（字节）


@dataclass
class FileWriteRequest:
    """文件写入请求"""
    file_path: str                    # 文件路径
    content: Any                      # 写入内容
    encoding: str = "utf-8"          # 文件编码
    write_mode: str = "text"         # 写入模式：text, binary
    create_dirs: bool = True         # 是否创建目录
    overwrite: bool = True           # 是否覆盖现有文件


@dataclass
class FileInfo:
    """文件信息"""
    path: str
    name: str
    size: int
    is_file: bool
    is_dir: bool
    created_time: Optional[datetime] = None
    modified_time: Optional[datetime] = None
    accessed_time: Optional[datetime] = None
    permissions: Optional[str] = None


class FileOperationsTool(BaseTool):
    """文件操作工具"""

    def __init__(self, base_path: Optional[str] = None):
        metadata = ToolMetadata(
            name="file_operations",
            description="执行文件操作：读取、写入、列表、删除等",
            version="1.0.0",
            category=ToolCategory.FILE_OPERATION,
            permissions=[ToolPermission.USER],  # 文件操作需要用户权限
            tags=["file", "system", "io"],
            author="Multi-Agent Framework",
            rate_limit=50,  # 每秒50次调用
            timeout=60.0,   # 60秒超时（文件操作可能较慢）
            max_input_length=1000,
        )
        super().__init__(metadata)
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self._allowed_extensions = {".txt", ".json", ".yaml", ".yml", ".csv", ".md", ".log"}
        self._max_file_size = 10 * 1024 * 1024  # 10MB

    async def _execute_async(self, input_data: Any, **kwargs) -> ToolOutput:
        """
        执行文件操作

        Args:
            input_data: 文件操作请求
            **kwargs: 额外参数

        Returns:
            ToolOutput: 操作结果
        """
        operation = kwargs.get("operation", "read")

        if operation == "read":
            return await self._read_file(input_data, **kwargs)
        elif operation == "write":
            return await self._write_file(input_data, **kwargs)
        elif operation == "list":
            return await self._list_files(input_data, **kwargs)
        elif operation == "delete":
            return await self._delete_file(input_data, **kwargs)
        elif operation == "info":
            return await self._file_info(input_data, **kwargs)
        elif operation == "copy":
            return await self._copy_file(input_data, **kwargs)
        elif operation == "move":
            return await self._move_file(input_data, **kwargs)
        else:
            return self._error_result(
                f"未知操作: {operation}",
                "UNKNOWN_OPERATION",
                {"operation": operation}
            )

    async def _read_file(self, input_data: Any, **kwargs) -> ToolOutput:
        """读取文件"""
        builder = ToolResultBuilder(
            tool_name=self.metadata.name,
            execution_id=kwargs.get("execution_id", f"read_{datetime.now().timestamp()}")
        )
        builder.start()

        try:
            # 解析输入
            if isinstance(input_data, dict):
                request = FileReadRequest(**input_data)
            elif isinstance(input_data, FileReadRequest):
                request = input_data
            elif isinstance(input_data, str):
                request = FileReadRequest(file_path=input_data)
            else:
                return builder.failure(
                    message="输入格式错误",
                    error_code="INVALID_INPUT",
                )

            # 验证和安全检查
            file_path = self._validate_and_resolve_path(request.file_path)
            self._check_file_safety(file_path, read=True)

            # 检查文件大小
            file_size = file_path.stat().st_size
            if request.max_size and file_size > request.max_size:
                return builder.failure(
                    message=f"文件过大: {file_size}字节，限制: {request.max_size}字节",
                    error_code="FILE_TOO_LARGE",
                    error_details={"file_size": file_size, "max_size": request.max_size},
                )

            if file_size > self._max_file_size:
                return builder.failure(
                    message=f"文件超过系统限制: {file_size}字节，系统限制: {self._max_file_size}字节",
                    error_code="FILE_TOO_LARGE",
                    error_details={"file_size": file_size, "system_limit": self._max_file_size},
                )

            # 读取文件
            content = await self._read_file_content(file_path, request)

            return builder.success(
                message="文件读取成功",
                data={
                    "content": content,
                    "file_path": str(file_path),
                    "file_size": file_size,
                    "encoding": request.encoding,
                    "read_mode": request.read_mode,
                },
            )

        except ToolError as e:
            return builder.failure(
                message=e.message,
                error_code=e.error_code,
                error_details=e.details,
            )

        except Exception as e:
            logger.exception(f"文件读取异常: {str(e)}")
            return builder.failure(
                message=f"文件读取失败: {str(e)}",
                error_code="READ_ERROR",
            )

    async def _write_file(self, input_data: Any, **kwargs) -> ToolOutput:
        """写入文件"""
        builder = ToolResultBuilder(
            tool_name=self.metadata.name,
            execution_id=kwargs.get("execution_id", f"write_{datetime.now().timestamp()}")
        )
        builder.start()

        try:
            # 解析输入
            if isinstance(input_data, dict):
                request = FileWriteRequest(**input_data)
            elif isinstance(input_data, FileWriteRequest):
                request = input_data
            else:
                return builder.failure(
                    message="输入格式错误",
                    error_code="INVALID_INPUT",
                )

            # 验证和安全检查
            file_path = self._validate_and_resolve_path(request.file_path)
            self._check_file_safety(file_path, write=True)

            # 检查目录是否存在
            if request.create_dirs:
                file_path.parent.mkdir(parents=True, exist_ok=True)

            # 检查文件是否已存在
            if file_path.exists() and not request.overwrite:
                return builder.failure(
                    message="文件已存在且不允许覆盖",
                    error_code="FILE_EXISTS",
                    error_details={"file_path": str(file_path)},
                )

            # 写入文件
            await self._write_file_content(file_path, request)

            # 获取文件信息
            file_info = self._get_file_info(file_path)

            return builder.success(
                message="文件写入成功",
                data={
                    "file_path": str(file_path),
                    "file_size": file_info.size,
                    "created": file_info.created_time.isoformat() if file_info.created_time else None,
                    "encoding": request.encoding,
                    "write_mode": request.write_mode,
                },
            )

        except ToolError as e:
            return builder.failure(
                message=e.message,
                error_code=e.error_code,
                error_details=e.details,
            )

        except Exception as e:
            logger.exception(f"文件写入异常: {str(e)}")
            return builder.failure(
                message=f"文件写入失败: {str(e)}",
                error_code="WRITE_ERROR",
            )

    async def _list_files(self, input_data: Any, **kwargs) -> ToolOutput:
        """列出文件"""
        builder = ToolResultBuilder(
            tool_name=self.metadata.name,
            execution_id=kwargs.get("execution_id", f"list_{datetime.now().timestamp()}")
        )
        builder.start()

        try:
            # 解析目录路径
            if isinstance(input_data, dict):
                dir_path = input_data.get("directory", ".")
                recursive = input_data.get("recursive", False)
                pattern = input_data.get("pattern", "*")
            elif isinstance(input_data, str):
                dir_path = input_data
                recursive = False
                pattern = "*"
            else:
                dir_path = "."
                recursive = False
                pattern = "*"

            # 验证目录
            dir_path_obj = self._validate_and_resolve_path(dir_path)
            if not dir_path_obj.is_dir():
                return builder.failure(
                    message="路径不是目录",
                    error_code="NOT_A_DIRECTORY",
                    error_details={"path": str(dir_path_obj)},
                )

            # 列出文件
            files = []
            if recursive:
                iterator = dir_path_obj.rglob(pattern)
            else:
                iterator = dir_path_obj.glob(pattern)

            for file_path in iterator:
                if file_path.is_file():
                    try:
                        file_info = self._get_file_info(file_path)
                        files.append(self._file_info_to_dict(file_info))
                    except (OSError, PermissionError):
                        # 跳过无法访问的文件
                        continue

            return builder.success(
                message="文件列表获取成功",
                data={
                    "directory": str(dir_path_obj),
                    "total_files": len(files),
                    "files": files,
                    "recursive": recursive,
                    "pattern": pattern,
                },
            )

        except Exception as e:
            logger.exception(f"文件列表异常: {str(e)}")
            return builder.failure(
                message=f"文件列表获取失败: {str(e)}",
                error_code="LIST_ERROR",
            )

    async def _delete_file(self, input_data: Any, **kwargs) -> ToolOutput:
        """删除文件"""
        builder = ToolResultBuilder(
            tool_name=self.metadata.name,
            execution_id=kwargs.get("execution_id", f"delete_{datetime.now().timestamp()}")
        )
        builder.start()

        try:
            # 解析文件路径
            if isinstance(input_data, dict):
                file_path = input_data.get("file_path")
                recursive = input_data.get("recursive", False)
            elif isinstance(input_data, str):
                file_path = input_data
                recursive = False
            else:
                return builder.failure(
                    message="输入格式错误",
                    error_code="INVALID_INPUT",
                )

            if not file_path:
                return builder.failure(
                    message="文件路径不能为空",
                    error_code="EMPTY_PATH",
                )

            # 验证和安全检查
            path_obj = self._validate_and_resolve_path(file_path)
            self._check_file_safety(path_obj, delete=True)

            # 检查路径是否存在
            if not path_obj.exists():
                return builder.failure(
                    message="文件或目录不存在",
                    error_code="NOT_FOUND",
                    error_details={"path": str(path_obj)},
                )

            # 执行删除
            if path_obj.is_file():
                path_obj.unlink()
                message = "文件删除成功"
            elif path_obj.is_dir():
                if recursive:
                    shutil.rmtree(path_obj)
                    message = "目录删除成功（递归）"
                else:
                    # 检查目录是否为空
                    if any(path_obj.iterdir()):
                        return builder.failure(
                            message="目录非空，请使用recursive=True或手动清空目录",
                            error_code="DIRECTORY_NOT_EMPTY",
                        )
                    path_obj.rmdir()
                    message = "目录删除成功"

            return builder.success(
                message=message,
                data={
                    "path": str(path_obj),
                    "type": "file" if path_obj.is_file() else "directory",
                    "recursive": recursive if path_obj.is_dir() else None,
                },
            )

        except ToolError as e:
            return builder.failure(
                message=e.message,
                error_code=e.error_code,
                error_details=e.details,
            )

        except Exception as e:
            logger.exception(f"文件删除异常: {str(e)}")
            return builder.failure(
                message=f"文件删除失败: {str(e)}",
                error_code="DELETE_ERROR",
            )

    async def _file_info(self, input_data: Any, **kwargs) -> ToolOutput:
        """获取文件信息"""
        builder = ToolResultBuilder(
            tool_name=self.metadata.name,
            execution_id=kwargs.get("execution_id", f"info_{datetime.now().timestamp()}")
        )
        builder.start()

        try:
            # 解析文件路径
            if isinstance(input_data, dict):
                file_path = input_data.get("file_path")
            elif isinstance(input_data, str):
                file_path = input_data
            else:
                return builder.failure(
                    message="输入格式错误",
                    error_code="INVALID_INPUT",
                )

            if not file_path:
                return builder.failure(
                    message="文件路径不能为空",
                    error_code="EMPTY_PATH",
                )

            # 验证路径
            path_obj = self._validate_and_resolve_path(file_path)
            self._check_file_safety(path_obj, read=True)

            # 检查路径是否存在
            if not path_obj.exists():
                return builder.failure(
                    message="文件或目录不存在",
                    error_code="NOT_FOUND",
                    error_details={"path": str(path_obj)},
                )

            # 获取文件信息
            file_info = self._get_file_info(path_obj)

            return builder.success(
                message="文件信息获取成功",
                data=self._file_info_to_dict(file_info),
            )

        except Exception as e:
            logger.exception(f"文件信息获取异常: {str(e)}")
            return builder.failure(
                message=f"文件信息获取失败: {str(e)}",
                error_code="INFO_ERROR",
            )

    async def _copy_file(self, input_data: Any, **kwargs) -> ToolOutput:
        """复制文件"""
        builder = ToolResultBuilder(
            tool_name=self.metadata.name,
            execution_id=kwargs.get("execution_id", f"copy_{datetime.now().timestamp()}")
        )
        builder.start()

        try:
            # 解析输入
            if isinstance(input_data, dict):
                source = input_data.get("source")
                destination = input_data.get("destination")
                overwrite = input_data.get("overwrite", False)
            else:
                return builder.failure(
                    message="输入格式错误，需要包含source和destination",
                    error_code="INVALID_INPUT",
                )

            if not source or not destination:
                return builder.failure(
                    message="源路径和目标路径不能为空",
                    error_code="EMPTY_PATHS",
                )

            # 验证路径
            source_path = self._validate_and_resolve_path(source)
            dest_path = self._validate_and_resolve_path(destination)

            self._check_file_safety(source_path, read=True)
            self._check_file_safety(dest_path, write=True)

            # 检查源文件是否存在
            if not source_path.exists():
                return builder.failure(
                    message="源文件不存在",
                    error_code="SOURCE_NOT_FOUND",
                    error_details={"source": str(source_path)},
                )

            # 检查目标文件是否已存在
            if dest_path.exists() and not overwrite:
                return builder.failure(
                    message="目标文件已存在且不允许覆盖",
                    error_code="DESTINATION_EXISTS",
                    error_details={"destination": str(dest_path)},
                )

            # 确保目标目录存在
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # 执行复制
            if source_path.is_file():
                shutil.copy2(source_path, dest_path)
                operation = "file_copy"
            elif source_path.is_dir():
                if dest_path.exists():
                    shutil.rmtree(dest_path)
                shutil.copytree(source_path, dest_path)
                operation = "directory_copy"
            else:
                return builder.failure(
                    message="源路径不是文件或目录",
                    error_code="INVALID_SOURCE_TYPE",
                )

            # 获取目标文件信息
            dest_info = self._get_file_info(dest_path)

            return builder.success(
                message="复制操作成功",
                data={
                    "operation": operation,
                    "source": str(source_path),
                    "destination": str(dest_path),
                    "destination_info": self._file_info_to_dict(dest_info),
                },
            )

        except ToolError as e:
            return builder.failure(
                message=e.message,
                error_code=e.error_code,
                error_details=e.details,
            )

        except Exception as e:
            logger.exception(f"文件复制异常: {str(e)}")
            return builder.failure(
                message=f"文件复制失败: {str(e)}",
                error_code="COPY_ERROR",
            )

    async def _move_file(self, input_data: Any, **kwargs) -> ToolOutput:
        """移动文件"""
        builder = ToolResultBuilder(
            tool_name=self.metadata.name,
            execution_id=kwargs.get("execution_id", f"move_{datetime.now().timestamp()}")
        )
        builder.start()

        try:
            # 解析输入
            if isinstance(input_data, dict):
                source = input_data.get("source")
                destination = input_data.get("destination")
                overwrite = input_data.get("overwrite", False)
            else:
                return builder.failure(
                    message="输入格式错误，需要包含source和destination",
                    error_code="INVALID_INPUT",
                )

            if not source or not destination:
                return builder.failure(
                    message="源路径和目标路径不能为空",
                    error_code="EMPTY_PATHS",
                )

            # 验证路径
            source_path = self._validate_and_resolve_path(source)
            dest_path = self._validate_and_resolve_path(destination)

            self._check_file_safety(source_path, read=True, delete=True)
            self._check_file_safety(dest_path, write=True)

            # 检查源文件是否存在
            if not source_path.exists():
                return builder.failure(
                    message="源文件不存在",
                    error_code="SOURCE_NOT_FOUND",
                    error_details={"source": str(source_path)},
                )

            # 检查目标文件是否已存在
            if dest_path.exists() and not overwrite:
                return builder.failure(
                    message="目标文件已存在且不允许覆盖",
                    error_code="DESTINATION_EXISTS",
                    error_details={"destination": str(dest_path)},
                )

            # 确保目标目录存在
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # 如果目标存在且允许覆盖，先删除
            if dest_path.exists() and overwrite:
                if dest_path.is_file():
                    dest_path.unlink()
                elif dest_path.is_dir():
                    shutil.rmtree(dest_path)

            # 执行移动
            shutil.move(str(source_path), str(dest_path))

            # 获取目标文件信息
            dest_info = self._get_file_info(dest_path)

            return builder.success(
                message="移动操作成功",
                data={
                    "operation": "move",
                    "source": str(source_path),
                    "destination": str(dest_path),
                    "destination_info": self._file_info_to_dict(dest_info),
                },
            )

        except ToolError as e:
            return builder.failure(
                message=e.message,
                error_code=e.error_code,
                error_details=e.details,
            )

        except Exception as e:
            logger.exception(f"文件移动异常: {str(e)}")
            return builder.failure(
                message=f"文件移动失败: {str(e)}",
                error_code="MOVE_ERROR",
            )

    def _validate_and_resolve_path(self, path: str) -> Path:
        """验证并解析路径"""
        try:
            path_obj = Path(path)

            # 如果路径是相对的，则相对于base_path
            if not path_obj.is_absolute():
                path_obj = self.base_path / path_obj

            # 规范化路径
            path_obj = path_obj.resolve()

            # 检查路径是否在base_path内（安全限制）
            try:
                path_obj.relative_to(self.base_path)
            except ValueError:
                raise ToolError(
                    message="路径超出允许范围",
                    error_code="PATH_OUT_OF_BOUNDS",
                    details={"base_path": str(self.base_path), "requested_path": str(path_obj)},
                    tool_name=self.metadata.name,
                )

            return path_obj

        except (ValueError, OSError) as e:
            raise ToolError(
                message=f"路径无效: {str(e)}",
                error_code="INVALID_PATH",
                details={"path": path},
                tool_name=self.metadata.name,
            )

    def _check_file_safety(self, path: Path, read: bool = False, write: bool = False, delete: bool = False):
        """检查文件安全性"""
        # 检查文件扩展名
        if read and path.is_file():
            if path.suffix.lower() not in self._allowed_extensions:
                raise ToolError(
                    message=f"文件类型不允许: {path.suffix}",
                    error_code="UNSUPPORTED_FILE_TYPE",
                    details={"file_extension": path.suffix, "allowed_extensions": list(self._allowed_extensions)},
                    tool_name=self.metadata.name,
                )

        # 检查系统文件（简化实现）
        system_dirs = ["/etc", "/bin", "/sbin", "/usr/bin", "/usr/sbin", "/var", "/proc", "/sys"]
        path_str = str(path)
        for sys_dir in system_dirs:
            if path_str.startswith(sys_dir):
                raise ToolError(
                    message="不允许访问系统目录",
                    error_code="SYSTEM_DIRECTORY",
                    details={"path": path_str, "system_dir": sys_dir},
                    tool_name=self.metadata.name,
                )

    async def _read_file_content(self, path: Path, request: FileReadRequest) -> Any:
        """读取文件内容"""
        if request.read_mode == "binary":
            async with aiofiles.open(path, "rb") as f:
                return await f.read()
        elif request.read_mode == "lines":
            async with aiofiles.open(path, "r", encoding=request.encoding) as f:
                lines = await f.readlines()
                return [line.rstrip("\n") for line in lines]
        else:  # text mode
            async with aiofiles.open(path, "r", encoding=request.encoding) as f:
                return await f.read()

    async def _write_file_content(self, path: Path, request: FileWriteRequest):
        """写入文件内容"""
        if request.write_mode == "binary":
            if isinstance(request.content, (bytes, bytearray)):
                content = request.content
            else:
                content = str(request.content).encode(request.encoding)
            async with aiofiles.open(path, "wb") as f:
                await f.write(content)
        else:  # text mode
            content = str(request.content)
            async with aiofiles.open(path, "w", encoding=request.encoding) as f:
                await f.write(content)

    def _get_file_info(self, path: Path) -> FileInfo:
        """获取文件信息"""
        stat = path.stat()
        return FileInfo(
            path=str(path),
            name=path.name,
            size=stat.st_size,
            is_file=path.is_file(),
            is_dir=path.is_dir(),
            created_time=datetime.fromtimestamp(stat.st_ctime),
            modified_time=datetime.fromtimestamp(stat.st_mtime),
            accessed_time=datetime.fromtimestamp(stat.st_atime),
            permissions=oct(stat.st_mode)[-3:],
        )

    def _file_info_to_dict(self, info: FileInfo) -> Dict[str, Any]:
        """转换文件信息为字典"""
        return {
            "path": info.path,
            "name": info.name,
            "size": info.size,
            "is_file": info.is_file,
            "is_dir": info.is_dir,
            "created_time": info.created_time.isoformat() if info.created_time else None,
            "modified_time": info.modified_time.isoformat() if info.modified_time else None,
            "accessed_time": info.accessed_time.isoformat() if info.accessed_time else None,
            "permissions": info.permissions,
        }

    def _error_result(self, message: str, error_code: str, details: Optional[Dict[str, Any]] = None) -> ToolOutput:
        """创建错误结果"""
        from tools.tool_result import ToolResultBuilder
        builder = ToolResultBuilder(
            tool_name=self.metadata.name,
            execution_id=f"error_{datetime.now().timestamp()}"
        )
        builder.start()
        return builder.failure(
            message=message,
            error_code=error_code,
            error_details=details,
        )


# 使用装饰器的版本
@circuit_breaker_with_config(
    failure_threshold=5,
    failure_window=120,
    reset_timeout=300,
    name="file_operations_decorated"
)
@retry_with_config(
    max_attempts=3,
    backoff_factor=2.0,
)
@fallback_default_value(
    default_value={"success": False, "error": "文件操作失败"},
    exceptions=(Exception,)
)
async def decorated_file_read(file_path: str, **kwargs) -> Dict[str, Any]:
    """
    使用装饰器的文件读取函数

    Args:
        file_path: 文件路径
        **kwargs: 其他参数

    Returns:
        Dict[str, Any]: 读取结果
    """
    tool = FileOperationsTool(base_path=kwargs.get("base_path"))
    request = FileReadRequest(
        file_path=file_path,
        encoding=kwargs.get("encoding", "utf-8"),
        read_mode=kwargs.get("read_mode", "text"),
        max_size=kwargs.get("max_size"),
    )

    result = await tool.execute(request, operation="read")

    if result.success:
        return result.data
    else:
        raise ToolError(
            message=result.message,
            error_code=result.error_code or "FILE_READ_ERROR",
            tool_name="decorated_file_read",
        )


# 导出工具
__all__ = [
    "FileOperationsTool",
    "FileReadRequest",
    "FileWriteRequest",
    "FileInfo",
    "decorated_file_read",
]