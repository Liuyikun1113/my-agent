"""
研究智能体
专门用于信息检索、知识查询、数据分析和报告生成
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from agents.base_agent import BaseAgent, AgentCapabilities, AgentStatus
from tools.registry import tool_registry

logger = logging.getLogger(__name__)


class ResearchAgent(BaseAgent):
    """
    研究智能体

    能力:
    - 网络搜索和信息收集
    - 多源数据综合和分析
    - 研究报告生成
    - 引用管理和来源追踪
    """

    def __init__(
        self,
        agent_id: str = "research_agent",
        name: str = "Research Agent",
        description: str = "研究智能体，擅长信息检索、知识查询和数据分析",
    ):
        super().__init__(agent_id=agent_id, name=name, description=description)
        self.capabilities = AgentCapabilities(
            can_chat=True,
            can_tool_call=True,
            can_plan_execute=False,
            can_react=True,
            can_research=True,
            supported_intents=["research", "analysis", "general_chat"],
        )
        self._research_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._sources: List[Dict[str, Any]] = []

    async def initialize(self):
        """初始化研究智能体"""
        if self._initialized:
            return
        self._initialized = True
        self.status = AgentStatus(status="idle")
        logger.info(f"研究智能体初始化完成: {self.agent_id}")

    async def process_message(
        self,
        session_id: str,
        message_id: str,
        message_content: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        处理消息 - 研究流程

        Args:
            session_id: 会话ID
            message_id: 消息ID
            message_content: 消息内容
            context: 上下文信息

        Returns:
            研究结果
        """
        try:
            self.update_status("busy", task=message_id)
            context = context or {}
            self._sources.clear()

            # 第一阶段：信息收集
            search_results = await self._collect_information(message_content)

            # 第二阶段：信息分析
            analysis = self._analyze_information(message_content, search_results)

            # 第三阶段：生成研究报告
            report = self._generate_report(message_content, search_results, analysis)

            return {
                "response": report,
                "message_id": f"resp_{message_id}",
                "sources": self._sources,
                "search_results": search_results,
                "analysis": analysis,
                "metadata": {
                    "sources_count": len(self._sources),
                    "search_queries": len(search_results),
                    "research_mode": "comprehensive",
                },
            }

        except Exception as e:
            logger.error(f"研究智能体处理消息失败: {e}")
            return {
                "response": f"研究过程中遇到问题: {str(e)}",
                "message_id": f"error_{message_id}",
                "is_error": True,
            }
        finally:
            self.update_status("idle")

    async def _collect_information(self, query: str) -> List[Dict[str, Any]]:
        """
        收集信息 - 使用搜索工具等多个来源

        Args:
            query: 搜索查询

        Returns:
            搜索结果列表
        """
        results = []

        # 主搜索
        try:
            search_result = await tool_registry.call_tool("web_search", {"query": query})
            if search_result.success:
                results.append({
                    "source": "web_search",
                    "query": query,
                    "data": search_result.data,
                    "timestamp": datetime.now().isoformat(),
                })
                self._sources.append({"type": "web_search", "query": query, "result": search_result.data})
        except Exception as e:
            logger.warning(f"网络搜索失败: {e}")

        # 相关查询扩展
        expanded_queries = self._expand_query(query)
        for expanded_query in expanded_queries[:2]:
            try:
                result = await tool_registry.call_tool("web_search", {"query": expanded_query})
                if result.success:
                    results.append({
                        "source": "web_search",
                        "query": expanded_query,
                        "data": result.data,
                        "timestamp": datetime.now().isoformat(),
                    })
                    self._sources.append({"type": "web_search", "query": expanded_query, "result": result.data})
            except Exception as e:
                logger.warning(f"扩展搜索失败 '{expanded_query}': {e}")

        return results

    def _expand_query(self, query: str) -> List[str]:
        """扩展搜索查询"""
        expansions = []
        if "?" in query or "？" in query:
            expansions.append(query.replace("?", "").replace("？", "") + " 详解")
            expansions.append(query.replace("?", "").replace("？", "") + " 最新")
        else:
            expansions.append(query + " 是什么")
            expansions.append(query + " 如何")
        return expansions

    def _analyze_information(
        self, original_query: str, search_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        分析收集到的信息

        Args:
            original_query: 原始查询
            search_results: 搜索结果

        Returns:
            分析结果
        """
        if not search_results:
            return {"summary": "未找到相关信息", "confidence": 0.0, "key_findings": []}

        total_sources = len(search_results)
        key_findings = []

        for result in search_results:
            data = result.get("data", "")
            if data:
                key_findings.append({
                    "source": result.get("source"),
                    "query": result.get("query"),
                    "relevance": "high" if original_query.lower() in str(data).lower() else "medium",
                })

        return {
            "summary": f"从 {total_sources} 个来源收集到信息",
            "confidence": min(0.9, 0.3 + total_sources * 0.2),
            "key_findings": key_findings,
        }

    def _generate_report(
        self,
        query: str,
        search_results: List[Dict[str, Any]],
        analysis: Dict[str, Any],
    ) -> str:
        """
        生成研究报告

        Args:
            query: 原始查询
            search_results: 搜索结果
            analysis: 分析结果

        Returns:
            格式化的研究报告
        """
        lines = [
            f"## 研究报告: {query}",
            "",
            f"**分析摘要**: {analysis.get('summary', '无')}",
            f"**置信度**: {analysis.get('confidence', 0):.0%}",
            "",
            "### 信息来源",
        ]

        for i, source in enumerate(self._sources):
            source_type = source.get("type", "unknown")
            source_query = source.get("query", "")
            lines.append(f"{i + 1}. [{source_type}] {source_query}")

        lines.append("")
        lines.append("### 主要发现")

        findings = analysis.get("key_findings", [])
        for i, finding in enumerate(findings):
            lines.append(f"{i + 1}. [{finding.get('relevance', 'unknown')}] {finding.get('query', '')}")

        if not findings:
            lines.append("暂无具体发现，建议扩大搜索范围")

        return "\n".join(lines)

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "agent_id": self.agent_id,
            "status": "healthy" if self._initialized else "not_initialized",
            "cached_queries": len(self._research_cache),
        }
