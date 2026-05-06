"""
记忆摘要生成器
使用LLM生成对话摘要，用于记忆压缩
"""
import logging
from typing import List, Dict, Any, Optional
import json

from config.settings import settings
from memory.interfaces.memory_item import MemoryItem

logger = logging.getLogger(__name__)


class Summarizer:
    """
    摘要生成器
    使用LLM生成对话摘要
    """

    def __init__(self, llm_provider: Optional[str] = None):
        """
        初始化摘要生成器

        Args:
            llm_provider: LLM供应商名称（openai, anthropic, ollama），如果为None则使用默认
        """
        self.llm_provider = llm_provider or settings.DEFAULT_LLM_PROVIDER
        self._llm_client = None

    async def initialize(self):
        """
        初始化LLM客户端
        """
        try:
            if self.llm_provider == "openai":
                await self._init_openai_client()
            elif self.llm_provider == "anthropic":
                await self._init_anthropic_client()
            elif self.llm_provider == "ollama":
                await self._init_ollama_client()
            else:
                logger.warning(f"不支持的LLM供应商: {self.llm_provider}，将使用占位摘要")

            logger.info(f"摘要生成器初始化完成，使用 {self.llm_provider}")

        except Exception as e:
            logger.error(f"摘要生成器初始化失败: {e}")
            # 继续，即使LLM初始化失败，也可以使用占位摘要

    async def _init_openai_client(self):
        """初始化OpenAI客户端"""
        try:
            from openai import AsyncOpenAI

            api_key = settings.OPENAI_API_KEY
            if not api_key:
                logger.warning("OpenAI API密钥未配置，将使用占位摘要")
                return

            self._llm_client = AsyncOpenAI(
                api_key=api_key,
                base_url=settings.OPENAI_BASE_URL,
            )
            logger.info("OpenAI客户端初始化成功")

        except ImportError:
            logger.warning("openai库未安装，将使用占位摘要")
        except Exception as e:
            logger.error(f"OpenAI客户端初始化失败: {e}")

    async def _init_anthropic_client(self):
        """初始化Anthropic客户端"""
        try:
            from anthropic import AsyncAnthropic

            api_key = settings.ANTHROPIC_API_KEY
            if not api_key:
                logger.warning("Anthropic API密钥未配置，将使用占位摘要")
                return

            self._llm_client = AsyncAnthropic(api_key=api_key)
            logger.info("Anthropic客户端初始化成功")

        except ImportError:
            logger.warning("anthropic库未安装，将使用占位摘要")
        except Exception as e:
            logger.error(f"Anthropic客户端初始化失败: {e}")

    async def _init_ollama_client(self):
        """初始化Ollama客户端"""
        try:
            import httpx

            self._llm_client = httpx.AsyncClient(
                base_url=settings.OLLAMA_BASE_URL,
                timeout=30.0,
            )
            logger.info("Ollama客户端初始化成功")

        except ImportError:
            logger.warning("httpx库未安装，将使用占位摘要")
        except Exception as e:
            logger.error(f"Ollama客户端初始化失败: {e}")

    async def summarize_messages(
        self,
        messages: List[MemoryItem],
        max_length: int = 500,
    ) -> str:
        """
        总结一组消息

        Args:
            messages: 消息记忆项列表
            max_length: 摘要最大长度

        Returns:
            str: 生成的摘要
        """
        if not messages:
            return "无内容可总结"

        try:
            # 提取消息文本
            message_texts = []
            for msg in messages:
                if msg.type == "message":
                    content = msg.data.get("content", "")
                    if content:
                        role = msg.data.get("role", "unknown")
                        message_texts.append(f"{role}: {content}")

            if not message_texts:
                return "无文本内容可总结"

            # 构建提示
            prompt = self._build_summary_prompt(message_texts, max_length)

            # 如果有LLM客户端，使用LLM生成摘要
            if self._llm_client:
                summary = await self._generate_with_llm(prompt)
                if summary:
                    return summary

            # 否则使用简单摘要
            return self._generate_simple_summary(message_texts, max_length)

        except Exception as e:
            logger.error(f"生成摘要失败: {e}")
            return self._generate_simple_summary(message_texts, max_length)

    def _build_summary_prompt(
        self,
        messages: List[str],
        max_length: int,
    ) -> str:
        """
        构建摘要生成提示

        Args:
            messages: 消息列表
            max_length: 摘要最大长度

        Returns:
            str: 提示文本
        """
        # 限制消息数量，避免提示过长
        max_messages = 50
        if len(messages) > max_messages:
            messages = messages[:max_messages] + ["...（后续消息省略）"]

        message_text = "\n".join(messages)

        prompt = f"""请总结以下对话内容，生成一个简洁的摘要。

要求：
1. 突出对话的主要话题和关键结论
2. 保留重要的决定、行动项和问题
3. 语言简洁明了，不超过{max_length}字
4. 使用中文总结

对话内容：
{message_text}

摘要："""

        return prompt

    async def _generate_with_llm(self, prompt: str) -> Optional[str]:
        """
        使用LLM生成摘要

        Args:
            prompt: 提示文本

        Returns:
            Optional[str]: 生成的摘要，如果失败则返回None
        """
        try:
            if self.llm_provider == "openai" and self._llm_client:
                response = await self._llm_client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": "你是一个专业的对话总结助手。"},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=min(500, len(prompt) // 2),
                    temperature=0.3,
                )
                return response.choices[0].message.content.strip()

            elif self.llm_provider == "anthropic" and self._llm_client:
                response = await self._llm_client.messages.create(
                    model=settings.ANTHROPIC_MODEL,
                    max_tokens=min(500, len(prompt) // 2),
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    system="你是一个专业的对话总结助手。",
                )
                return response.content[0].text.strip()

            elif self.llm_provider == "ollama" and self._llm_client:
                response = await self._llm_client.post(
                    "/api/generate",
                    json={
                        "model": settings.OLLAMA_MODEL,
                        "prompt": prompt,
                        "system": "你是一个专业的对话总结助手。",
                        "options": {
                            "temperature": 0.3,
                        },
                        "stream": False,
                    },
                )
                response.raise_for_status()
                result = response.json()
                return result.get("response", "").strip()

        except Exception as e:
            logger.error(f"LLM生成摘要失败: {e}")

        return None

    def _generate_simple_summary(
        self,
        messages: List[str],
        max_length: int,
    ) -> str:
        """
        生成简单摘要（后备方案）

        Args:
            messages: 消息列表
            max_length: 摘要最大长度

        Returns:
            str: 简单摘要
        """
        if not messages:
            return "无内容"

        # 取前几条和后几条消息
        preview_count = 3
        if len(messages) <= preview_count * 2:
            selected = messages
        else:
            selected = messages[:preview_count] + ["..."] + messages[-preview_count:]

        summary = f"对话共 {len(messages)} 条消息。主要内容：{'，'.join(selected[:5])}"

        # 截断到最大长度
        if len(summary) > max_length:
            summary = summary[:max_length-3] + "..."

        return summary

    async def summarize_memory_items(
        self,
        memory_items: List[MemoryItem],
        compression_ratio: float = 0.3,
    ) -> List[MemoryItem]:
        """
        总结记忆项列表，减少数量

        Args:
            memory_items: 记忆项列表
            compression_ratio: 压缩比例（保留的比例）

        Returns:
            List[MemoryItem]: 压缩后的记忆项列表
        """
        if not memory_items:
            return []

        try:
            # 按类型分组
            messages = [item for item in memory_items if item.type == "message"]
            other_items = [item for item in memory_items if item.type != "message"]

            if not messages:
                # 如果没有消息，直接返回其他项（按时间排序）
                sorted_items = sorted(other_items, key=lambda x: x.created_at)
                return sorted_items[:int(len(sorted_items) * compression_ratio)]

            # 生成消息摘要
            summary_text = await self.summarize_messages(messages)

            # 创建摘要记忆项
            from datetime import datetime
            import uuid

            summary_item = MemoryItem(
                id=str(uuid.uuid4()),
                type="summary",
                data={
                    "summary": summary_text,
                    "original_count": len(messages),
                    "compressed_count": 1,
                    "compression_ratio": compression_ratio,
                },
                metadata={
                    "compression_method": "llm_summary",
                    "original_ids": [msg.id for msg in messages],
                },
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            # 组合结果：摘要 + 其他项（按时间排序）
            result = [summary_item]
            sorted_other = sorted(other_items, key=lambda x: x.created_at)
            result.extend(sorted_other[:int(len(sorted_other) * compression_ratio)])

            logger.info(f"记忆压缩完成: {len(memory_items)} -> {len(result)} 项，压缩比例: {compression_ratio}")

            return result

        except Exception as e:
            logger.error(f"总结记忆项失败: {e}")
            # 失败时返回原始项（按时间排序，取前一部分）
            sorted_items = sorted(memory_items, key=lambda x: x.created_at)
            return sorted_items[:int(len(sorted_items) * compression_ratio)]

    async def close(self):
        """关闭LLM客户端"""
        try:
            if self._llm_client and hasattr(self._llm_client, 'close'):
                await self._llm_client.close()
                logger.info("摘要生成器客户端已关闭")
        except Exception as e:
            logger.error(f"关闭摘要生成器客户端失败: {e}")


# 全局摘要生成器实例
summarizer = Summarizer()