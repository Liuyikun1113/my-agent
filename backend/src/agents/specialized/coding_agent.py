"""
编程智能体
专门用于代码生成、调试、重构和代码审查
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from agents.base_agent import BaseAgent, AgentCapabilities, AgentStatus
from tools.registry import tool_registry

logger = logging.getLogger(__name__)


class CodingAgent(BaseAgent):
    """
    编程智能体

    能力:
    - 代码生成（Python, JavaScript, TypeScript, Go 等）
    - 代码调试和错误修复
    - 代码重构和优化
    - 代码审查和建议
    - 项目结构分析和设计
    """

    SUPPORTED_LANGUAGES = {
        "python": [".py"],
        "javascript": [".js", ".jsx"],
        "typescript": [".ts", ".tsx"],
        "go": [".go"],
        "java": [".java"],
        "rust": [".rs"],
    }

    def __init__(
        self,
        agent_id: str = "coding_agent",
        name: str = "Coding Agent",
        description: str = "编程智能体，擅长代码生成、调试、重构和代码审查",
    ):
        super().__init__(agent_id=agent_id, name=name, description=description)
        self.capabilities = AgentCapabilities(
            can_chat=True,
            can_tool_call=True,
            can_plan_execute=True,
            can_react=True,
            can_code=True,
            supported_intents=["coding", "analysis"],
        )
        self._active_sessions: Dict[str, Dict[str, Any]] = {}

    async def initialize(self):
        """初始化编程智能体"""
        if self._initialized:
            return
        self._initialized = True
        self.status = AgentStatus(status="idle")
        logger.info(f"编程智能体初始化完成: {self.agent_id}")

    async def process_message(
        self,
        session_id: str,
        message_id: str,
        message_content: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        处理消息 - 编程工作流

        Args:
            session_id: 会话ID
            message_id: 消息ID
            message_content: 消息内容
            context: 上下文信息

        Returns:
            处理结果
        """
        try:
            self.update_status("busy", task=message_id)
            context = context or {}

            # 初始化会话上下文
            if session_id not in self._active_sessions:
                self._active_sessions[session_id] = {
                    "files_modified": [],
                    "language": None,
                    "project_context": {},
                }

            session_ctx = self._active_sessions[session_id]

            # 检测编程语言
            detected_lang = self._detect_language(message_content)
            if detected_lang:
                session_ctx["language"] = detected_lang

            # 分析任务类型
            task_type = self._analyze_task_type(message_content)

            if task_type == "generate":
                response = await self._handle_generation(message_content, session_ctx)
            elif task_type == "debug":
                response = await self._handle_debugging(message_content, session_ctx)
            elif task_type == "refactor":
                response = await self._handle_refactoring(message_content, session_ctx)
            elif task_type == "review":
                response = await self._handle_review(message_content, session_ctx)
            else:
                response = await self._handle_general(message_content, session_ctx)

            return {
                "response": response,
                "message_id": f"resp_{message_id}",
                "task_type": task_type,
                "language": session_ctx.get("language"),
                "metadata": {
                    "task_type": task_type,
                    "language": session_ctx.get("language"),
                    "files_modified": len(session_ctx.get("files_modified", [])),
                },
            }

        except Exception as e:
            logger.error(f"编程智能体处理消息失败: {e}")
            return {
                "response": f"代码处理过程中遇到问题: {str(e)}",
                "message_id": f"error_{message_id}",
                "is_error": True,
            }
        finally:
            self.update_status("idle")

    def _detect_language(self, content: str) -> Optional[str]:
        """从内容中检测编程语言"""
        content_lower = content.lower()

        lang_keywords = {
            "python": ["python", ".py", "def ", "import ", "class ", "pytest"],
            "javascript": ["javascript", "js", ".js", "const ", "let ", "function", "console.log"],
            "typescript": ["typescript", "ts", ".ts", "interface", "type ", "enum"],
            "go": ["golang", "go", ".go", "func ", "package ", "go mod"],
            "rust": ["rust", ".rs", "fn ", "impl ", "cargo"],
            "java": ["java", ".java", "public class", "spring", "maven"],
        }

        scores = {}
        for lang, keywords in lang_keywords.items():
            score = sum(1 for kw in keywords if kw in content_lower)
            if score > 0:
                scores[lang] = score

        if scores:
            return max(scores, key=scores.get)
        return None

    def _analyze_task_type(self, content: str) -> str:
        """分析编程任务类型"""
        content_lower = content.lower()

        generate_kw = ["创建", "生成", "写一个", "实现", "create", "generate", "write", "implement", "build"]
        debug_kw = ["修复", "调试", "bug", "错误", "fix", "debug", "error", "issue", "不工作"]
        refactor_kw = ["重构", "优化", "改进", "refactor", "optimize", "improve", "clean"]
        review_kw = ["审查", "review", "检查", "check", "audit"]

        if any(kw in content_lower for kw in generate_kw):
            return "generate"
        elif any(kw in content_lower for kw in debug_kw):
            return "debug"
        elif any(kw in content_lower for kw in refactor_kw):
            return "refactor"
        elif any(kw in content_lower for kw in review_kw):
            return "review"

        return "general"

    async def _handle_generation(
        self, content: str, session_ctx: Dict[str, Any]
    ) -> str:
        """处理代码生成任务"""
        lang = session_ctx.get("language", "python")

        response_parts = [
            f"## 代码生成",
            f"**语言**: {lang}",
            "",
            f"根据您的需求生成的代码框架:",
            "",
        ]

        # 尝试读取相关文件
        try:
            file_result = await tool_registry.call_tool("file_operations", {"action": "list", "path": "."})
            if file_result.success:
                response_parts.append("**当前项目文件**:")
                response_parts.append(str(file_result.data)[:500])
                response_parts.append("")
        except Exception:
            pass

        response_parts.append(f"```{lang}")
        response_parts.append(f"# TODO: 根据需求生成 {lang} 代码")
        response_parts.append(f"# 原始需求: {content[:200]}")
        response_parts.append("```")

        return "\n".join(response_parts)

    async def _handle_debugging(
        self, content: str, session_ctx: Dict[str, Any]
    ) -> str:
        """处理代码调试任务"""
        response_parts = [
            "## 代码调试",
            "",
            "### 调试步骤:",
            "1. 复现问题",
            "2. 定位根本原因",
            "3. 制定修复方案",
            "4. 实施修复",
            "5. 验证修复",
            "",
        ]

        # 尝试读取文件以辅助调试
        try:
            file_result = await tool_registry.call_tool("file_operations", {"action": "read", "content": content})
            if file_result.success:
                response_parts.append("### 文件内容分析:")
                response_parts.append(str(file_result.data)[:1000])
                response_parts.append("")
        except Exception:
            pass

        response_parts.append("### 建议:")
        response_parts.append("请提供具体的错误信息和相关代码以便进一步分析")

        return "\n".join(response_parts)

    async def _handle_refactoring(
        self, content: str, session_ctx: Dict[str, Any]
    ) -> str:
        """处理代码重构任务"""
        return "\n".join([
            "## 代码重构",
            "",
            "### 重构建议:",
            "- 提取重复代码为函数",
            "- 改善变量命名",
            "- 添加类型注解",
            "- 优化数据结构",
            "- 添加错误处理",
            "",
            "请提供需要重构的代码以获取具体建议",
        ])

    async def _handle_review(
        self, content: str, session_ctx: Dict[str, Any]
    ) -> str:
        """处理代码审查任务"""
        return "\n".join([
            "## 代码审查",
            "",
            "### 审查维度:",
            "- **正确性**: 逻辑是否正确",
            "- **可读性**: 代码是否清晰易懂",
            "- **性能**: 是否存在性能瓶颈",
            "- **安全性**: 是否存在安全漏洞",
            "- **可维护性**: 代码结构是否合理",
            "",
            "请提供需要审查的代码",
        ])

    async def _handle_general(
        self, content: str, session_ctx: Dict[str, Any]
    ) -> str:
        """处理一般编程查询"""
        return f"编程智能体已收到您的请求: {content[:200]}。请提供更多细节以便更好地帮助您。"

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "agent_id": self.agent_id,
            "status": "healthy" if self._initialized else "not_initialized",
            "active_sessions": len(self._active_sessions),
        }

    async def cleanup(self):
        """清理资源"""
        self._active_sessions.clear()
