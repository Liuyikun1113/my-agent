"""
网络搜索工具示例
演示需要外部API调用的工具
"""
import logging
import asyncio
import aiohttp
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import quote_plus

from tools.base_tool import (
    BaseTool, ToolMetadata, ToolCategory, ToolPermission, ToolError, ToolOutput
)
from tools.tool_result import ToolResultBuilder
from tools.decorators.retry_decorator import retry_with_config
from tools.decorators.circuit_breaker import circuit_breaker_with_config
from tools.decorators.fallback_decorator import fallback_default_value

logger = logging.getLogger(__name__)


@dataclass
class SearchQuery:
    """搜索查询"""
    query: str                    # 搜索查询
    num_results: int = 10         # 结果数量
    language: str = "zh-CN"       # 语言
    safe_search: bool = True      # 安全搜索
    time_range: Optional[str] = None  # 时间范围：d（天）、w（周）、m（月）、y（年）


@dataclass
class SearchResult:
    """搜索结果"""
    title: str
    url: str
    snippet: str
    source: str
    published_date: Optional[str] = None
    relevance_score: float = 0.0


class WebSearchTool(BaseTool):
    """网络搜索工具"""

    def __init__(self, api_key: Optional[str] = None):
        metadata = ToolMetadata(
            name="web_search",
            description="执行网络搜索，返回相关网页结果",
            version="1.0.0",
            category=ToolCategory.SEARCH,
            permissions=[ToolPermission.USER],
            tags=["search", "web", "research"],
            author="Multi-Agent Framework",
            rate_limit=10,  # 每秒10次调用
            timeout=30.0,   # 30秒超时
            max_input_length=500,
            required_services=["search_api"],
        )
        super().__init__(metadata)
        self.api_key = api_key
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, tuple[List[SearchResult], datetime]] = {}
        self._cache_ttl = timedelta(minutes=5)

    async def _ensure_session(self):
        """确保HTTP会话存在"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    "User-Agent": "Multi-Agent-Framework/1.0",
                }
            )

    async def _execute_async(self, input_data: Any, **kwargs) -> ToolOutput:
        """
        执行网络搜索

        Args:
            input_data: 搜索查询
            **kwargs: 额外参数

        Returns:
            ToolOutput: 搜索结果
        """
        builder = ToolResultBuilder(
            tool_name=self.metadata.name,
            execution_id=kwargs.get("execution_id", f"search_{datetime.now().timestamp()}")
        )
        builder.start()

        try:
            # 解析输入
            if isinstance(input_data, dict):
                search_query = SearchQuery(**input_data)
            elif isinstance(input_data, SearchQuery):
                search_query = input_data
            elif isinstance(input_data, str):
                search_query = SearchQuery(query=input_data)
            else:
                raise ToolError(
                    message="输入格式错误，应为字符串、字典或SearchQuery对象",
                    error_code="INVALID_INPUT",
                    tool_name=self.metadata.name,
                )

            # 验证输入
            self._validate_search_query(search_query)

            # 检查缓存
            cache_key = self._create_cache_key(search_query)
            cached_results, cached_time = self._cache.get(cache_key, (None, None))

            if cached_results and cached_time:
                age = datetime.now() - cached_time
                if age < self._cache_ttl:
                    logger.info(f"使用缓存结果: {search_query.query}, 年龄: {age}")
                    builder.update_field("cache_hit", True)
                    return builder.success(
                        message="搜索成功（缓存）",
                        data={
                            "results": [self._result_to_dict(r) for r in cached_results],
                            "total": len(cached_results),
                            "query": search_query.query,
                            "cached": True,
                            "cache_age_seconds": age.total_seconds(),
                        },
                    )

            # 执行搜索
            results = await self._perform_search(search_query)

            # 更新缓存
            self._cache[cache_key] = (results, datetime.now())

            # 构建成功结果
            return builder.success(
                message="搜索成功",
                data={
                    "results": [self._result_to_dict(r) for r in results],
                    "total": len(results),
                    "query": search_query.query,
                    "cached": False,
                },
            )

        except ToolError as e:
            return builder.failure(
                message=e.message,
                error_code=e.error_code,
                error_details=e.details,
            )

        except asyncio.TimeoutError:
            return builder.timeout(
                message="搜索请求超时",
                timeout_seconds=self.metadata.timeout,
            )

        except Exception as e:
            logger.exception(f"网络搜索工具异常: {str(e)}")
            return builder.failure(
                message=f"搜索过程中发生错误: {str(e)}",
                error_code="SEARCH_ERROR",
            )

        finally:
            # 清理资源
            await self._cleanup()

    def _validate_search_query(self, query: SearchQuery):
        """验证搜索查询"""
        if not query.query or not query.query.strip():
            raise ToolError(
                message="搜索查询不能为空",
                error_code="EMPTY_QUERY",
                tool_name=self.metadata.name,
            )

        if len(query.query) > 300:
            raise ToolError(
                message="搜索查询过长，最大300个字符",
                error_code="QUERY_TOO_LONG",
                details={"query_length": len(query.query)},
                tool_name=self.metadata.name,
            )

        if query.num_results < 1 or query.num_results > 50:
            raise ToolError(
                message="结果数量必须在1到50之间",
                error_code="INVALID_NUM_RESULTS",
                details={"num_results": query.num_results},
                tool_name=self.metadata.name,
            )

        # 检查时间范围
        if query.time_range and query.time_range not in ["d", "w", "m", "y"]:
            raise ToolError(
                message="时间范围必须是 d(天)、w(周)、m(月)、y(年) 之一",
                error_code="INVALID_TIME_RANGE",
                details={"time_range": query.time_range},
                tool_name=self.metadata.name,
            )

    def _create_cache_key(self, query: SearchQuery) -> str:
        """创建缓存键"""
        return f"{query.query}:{query.num_results}:{query.language}:{query.time_range}"

    async def _perform_search(self, query: SearchQuery) -> List[SearchResult]:
        """执行搜索"""
        # 注意：这是一个示例实现
        # 实际应用中应该调用真正的搜索API（如Google Custom Search、Bing API等）

        await self._ensure_session()

        if not self.api_key:
            logger.warning("WebSearchTool 使用 mock 数据，未配置真实搜索 API")
            logger.info(f"模拟搜索: {query.query}")
            await asyncio.sleep(0.5)
            return self._generate_mock_results(query)

        # 实际API调用（示例）
        try:
            # 这里应该是实际的API调用代码
            # 例如：response = await self._session.get(f"https://api.example.com/search?q={quote_plus(query.query)}")
            # 为了示例，我们返回模拟结果
            await asyncio.sleep(1.0)
            return self._generate_mock_results(query)

        except aiohttp.ClientError as e:
            raise ToolError(
                message=f"搜索API请求失败: {str(e)}",
                error_code="API_REQUEST_FAILED",
                details={"error_type": type(e).__name__},
                tool_name=self.metadata.name,
            )

    def _generate_mock_results(self, query: SearchQuery) -> List[SearchResult]:
        """生成模拟搜索结果"""
        results = []
        base_score = 0.9

        for i in range(min(query.num_results, 10)):
            score = base_score - (i * 0.07)
            result = SearchResult(
                title=f"关于'{query.query}'的搜索结果 {i+1}",
                url=f"https://example.com/search/{quote_plus(query.query)}/result{i+1}",
                snippet=f"这是关于'{query.query}'的第{i+1}个搜索结果。这是一个示例片段，用于演示搜索结果的结构。",
                source="Example Search Engine",
                published_date="2024-01-01" if i % 2 == 0 else None,
                relevance_score=score,
            )
            results.append(result)

        return results

    def _result_to_dict(self, result: SearchResult) -> Dict[str, Any]:
        """转换搜索结果为字典"""
        return {
            "title": result.title,
            "url": result.url,
            "snippet": result.snippet,
            "source": result.source,
            "published_date": result.published_date,
            "relevance_score": result.relevance_score,
        }

    async def _cleanup(self):
        """清理资源"""
        if self._session and not self._session.closed:
            # 注意：在实际应用中，可能需要保持会话重用
            # 这里为了简化，关闭会话
            await self._session.close()
            self._session = None

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        logger.info("搜索缓存已清空")

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total_entries = len(self._cache)
        total_results = sum(len(results) for results, _ in self._cache.values())

        return {
            "total_entries": total_entries,
            "total_results": total_results,
            "cache_ttl_seconds": self._cache_ttl.total_seconds(),
        }


# 使用装饰器的版本
@circuit_breaker_with_config(
    failure_threshold=3,
    failure_window=60,
    reset_timeout=120,
    name="web_search_decorated"
)
@retry_with_config(
    max_attempts=2,
    backoff_factor=2.0,
    retry_on_exceptions=(aiohttp.ClientError, asyncio.TimeoutError)
)
@fallback_default_value(
    default_value={"results": [], "error": "搜索失败，返回空结果"},
    exceptions=(Exception,)
)
async def decorated_web_search(
    query: str,
    num_results: int = 10,
    **kwargs,
) -> Dict[str, Any]:
    """
    使用装饰器的网络搜索函数

    Args:
        query: 搜索查询
        num_results: 结果数量
        **kwargs: 其他参数

    Returns:
        Dict[str, Any]: 搜索结果
    """
    search_query = SearchQuery(
        query=query,
        num_results=num_results,
        language=kwargs.get("language", "zh-CN"),
        safe_search=kwargs.get("safe_search", True),
        time_range=kwargs.get("time_range"),
    )

    # 创建工具实例
    tool = WebSearchTool(api_key=kwargs.get("api_key"))
    result = await tool.execute(search_query)

    if result.success:
        return result.data
    else:
        # 装饰器的fallback会处理异常情况
        raise ToolError(
            message=result.message,
            error_code=result.error_code or "SEARCH_ERROR",
            tool_name="decorated_web_search",
        )


# 同步版本（包装异步版本）
class SynchronousWebSearchTool(WebSearchTool):
    """同步网络搜索工具"""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.metadata.name = "sync_web_search"
        self.metadata.description = "同步网络搜索工具"

    def _execute_sync(self, input_data: Any, **kwargs) -> ToolOutput:
        """同步执行"""
        # 包装异步方法
        async def async_wrapper():
            return await self._execute_async(input_data, **kwargs)

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(async_wrapper())


# 导出工具
__all__ = [
    "WebSearchTool",
    "SynchronousWebSearchTool",
    "decorated_web_search",
    "SearchQuery",
    "SearchResult",
]