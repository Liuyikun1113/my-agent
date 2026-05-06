"""
LLM意图分类器
使用大语言模型进行高精度意图分类
"""
import logging
from typing import Dict, List, Optional, Any

from .classifier import BaseIntentClassifier, IntentResult
from backend.src.config.settings import settings

logger = logging.getLogger(__name__)


class LLMIntentClassifier(BaseIntentClassifier):
    """
    LLM意图分类器
    使用大语言模型进行精确的意图分类，作为BERT分类器的补充
    """

    INTENT_PROMPT_TEMPLATE = """分析以下用户消息的意图，从以下类别中选择最匹配的一个:
类别: {categories}

用户消息: {text}

请以JSON格式返回结果:
{{"intent": "<选中的类别>", "confidence": <0.0到1.0的置信度>, "reasoning": "<简短理由>"}}"""

    def __init__(self):
        super().__init__()
        self.llm_client = None
        self.provider = settings.DEFAULT_LLM_PROVIDER

    async def initialize(self):
        """初始化LLM分类器"""
        if self._initialized:
            return

        try:
            self._setup_llm_client()
            self._initialized = True
            logger.info(f"LLM意图分类器初始化完成 (provider={self.provider})")

        except Exception as e:
            logger.error(f"LLM意图分类器初始化失败: {e}", exc_info=True)
            raise

    def _setup_llm_client(self):
        """设置LLM客户端"""
        try:
            if self.provider == "openai" and settings.OPENAI_API_KEY:
                import openai
                self.llm_client = openai.AsyncOpenAI(
                    api_key=settings.OPENAI_API_KEY,
                    base_url=settings.OPENAI_BASE_URL,
                )
                logger.info("使用OpenAI作为LLM分类器")
            elif self.provider == "anthropic" and settings.ANTHROPIC_API_KEY:
                import anthropic
                self.llm_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
                logger.info("使用Anthropic作为LLM分类器")
            else:
                logger.warning(f"LLM供应商 {self.provider} 未配置或不可用，使用规则分类")
                self.llm_client = None
        except ImportError as e:
            logger.warning(f"导入LLM客户端失败: {e}，使用规则分类")
            self.llm_client = None

    async def classify(
        self, text: str, context: Optional[Dict[str, Any]] = None
    ) -> IntentResult:
        """
        使用LLM进行意图分类

        Args:
            text: 要分类的文本
            context: 上下文信息

        Returns:
            IntentResult: 意图识别结果
        """
        try:
            if not self._initialized:
                await self.initialize()

            if self.llm_client:
                result = await self._classify_with_llm(text, context)
            else:
                result = await self._classify_with_rules(text)

            return result

        except Exception as e:
            logger.error(f"LLM意图分类失败: {e}", exc_info=True)
            return IntentResult(
                intent="general_chat",
                confidence=0.5,
                metadata={"error": str(e), "classifier": "llm_fallback"},
            )

    async def _classify_with_llm(
        self, text: str, context: Optional[Dict[str, Any]] = None
    ) -> IntentResult:
        """使用LLM API进行分类"""
        import json

        categories = list(self.categories.keys()) if self.categories else [
            "general_chat", "research", "coding", "tool_usage", "planning"
        ]
        categories_str = ", ".join(categories)

        prompt = self.INTENT_PROMPT_TEMPLATE.format(
            categories=categories_str,
            text=text,
        )

        try:
            if self.provider == "openai":
                response = await self.llm_client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": "你是一个意图分类助手，只返回JSON格式结果。"},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=200,
                )
                content = response.choices[0].message.content
            elif self.provider == "anthropic":
                response = await self.llm_client.messages.create(
                    model=settings.ANTHROPIC_MODEL,
                    max_tokens=200,
                    temperature=0.1,
                    messages=[{"role": "user", "content": prompt}],
                )
                content = response.content[0].text
            else:
                return await self._classify_with_rules(text)

            # 解析JSON响应
            content = content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content)

            intent = data.get("intent", "general_chat")
            confidence = float(data.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))

            return IntentResult(
                intent=intent,
                confidence=confidence,
                metadata={
                    "classifier": "llm",
                    "provider": self.provider,
                    "reasoning": data.get("reasoning", ""),
                },
            )

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.warning(f"LLM响应解析失败: {e}，使用规则分类")
            return await self._classify_with_rules(text)

    async def _classify_with_rules(self, text: str) -> IntentResult:
        """基于规则的意图分类（LLM不可用时的降级方案）"""
        text_lower = text.lower()

        rules = [
            (["研究", "调查", "查询", "搜索", "find", "research", "search", "look up"], "research", 0.80),
            (["代码", "编程", "程序", "开发", "code", "program", "write", "implement"], "coding", 0.85),
            (["工具", "使用", "调用", "执行", "tool", "use", "run", "execute"], "tool_usage", 0.75),
            (["计划", "任务", "待办", "todo", "plan", "task", "schedule"], "planning", 0.70),
            (["分析", "计算", "统计", "analyze", "calculate", "compute"], "analysis", 0.78),
        ]

        for keywords, intent, base_confidence in rules:
            if any(kw in text_lower for kw in keywords):
                return IntentResult(
                    intent=intent,
                    confidence=base_confidence,
                    metadata={"classifier": "rule_based", "matched_keywords": keywords},
                )

        return IntentResult(
            intent="general_chat",
            confidence=0.55,
            metadata={"classifier": "rule_based", "reason": "no_specific_match"},
        )

    async def batch_classify(
        self, texts: List[str], context: Optional[Dict[str, Any]] = None
    ) -> List[IntentResult]:
        """批量意图分类"""
        results = []
        for text in texts:
            result = await self.classify(text, context)
            results.append(result)
        return results

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "status": "healthy" if self._initialized else "unhealthy",
            "llm_client_available": self.llm_client is not None,
            "provider": self.provider,
        }

    async def cleanup(self):
        """清理资源"""
        self.llm_client = None
        self._initialized = False
