"""
工具实现模块
包含具体的工具实现示例
"""
try:
    from .calculator_tool import CalculatorTool, CalculatorInput
    HAS_CALCULATOR = True
except ImportError:
    HAS_CALCULATOR = False

try:
    from .web_search_tool import WebSearchTool, SearchQuery, SearchResult
    HAS_WEB_SEARCH = True
except ImportError:
    HAS_WEB_SEARCH = False

try:
    from .file_operations_tool import (
        FileOperationsTool, FileReadRequest, FileWriteRequest, FileInfo
    )
    HAS_FILE_OPS = True
except ImportError:
    HAS_FILE_OPS = False

__all__ = []

if HAS_CALCULATOR:
    __all__.extend(["CalculatorTool", "CalculatorInput"])

if HAS_WEB_SEARCH:
    __all__.extend(["WebSearchTool", "SearchQuery", "SearchResult"])

if HAS_FILE_OPS:
    __all__.extend(["FileOperationsTool", "FileReadRequest", "FileWriteRequest", "FileInfo"])