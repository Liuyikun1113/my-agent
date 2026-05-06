"""
意图分类器基类和全局实例
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class IntentResult:
    """意图识别结果"""
    intent: str
    confidence: float
    category: Optional[str] = None
    sub_intents: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IntentCategory:
    """意图类别"""
    id: str
    name: str
    description: str
    threshold: float = 0.7
    redirect_threshold: float = 0.3
    handler_agent: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseIntentClassifier(ABC):
    """
    意图分类器基类
    所有意图分类器必须继承此基类
    """

    def __init__(self):
        self.categories: Dict[str, IntentCategory] = {}
        self._initialized = False

    @abstractmethod
    async def initialize(self):
        """
        初始化分类器
        """
        pass

    @abstractmethod
    async def classify(self, text: str, context: Optional[Dict[str, Any]] = None) -> IntentResult:
        """
        对文本进行意图分类

        Args:
            text: 要分类的文本
            context: 上下文信息

        Returns:
            IntentResult: 意图识别结果
        """
        pass

    @abstractmethod
    async def batch_classify(
        self,
        texts: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[IntentResult]:
        """
        批量意图分类

        Args:
            texts: 要分类的文本列表
            context: 上下文信息

        Returns:
            List[IntentResult]: 意图识别结果列表
        """
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            Dict[str, Any]: 健康状态信息
        """
        pass

    def add_category(self, category: IntentCategory):
        """
        添加意图类别

        Args:
            category: 意图类别
        """
        self.categories[category.id] = category
        logger.info(f"意图类别添加成功: {category.id} ({category.name})")

    def remove_category(self, category_id: str):
        """
        移除意图类别

        Args:
            category_id: 意图类别ID
        """
        if category_id in self.categories:
            category = self.categories.pop(category_id)
            logger.info(f"意图类别移除成功: {category_id} ({category.name})")

    def get_category(self, category_id: str) -> Optional[IntentCategory]:
        """
        获取意图类别

        Args:
            category_id: 意图类别ID

        Returns:
            Optional[IntentCategory]: 意图类别
        """
        return self.categories.get(category_id)

    def list_categories(self) -> List[IntentCategory]:
        """
        列出所有意图类别

        Returns:
            List[IntentCategory]: 意图类别列表
        """
        return list(self.categories.values())

    def find_category_by_intent(self, intent: str) -> Optional[IntentCategory]:
        """
        根据意图查找类别

        Args:
            intent: 意图标签

        Returns:
            Optional[IntentCategory]: 意图类别
        """
        for category in self.categories.values():
            if category.name == intent:
                return category
        return None

    def should_redirect(self, confidence: float, category: Optional[IntentCategory] = None) -> bool:
        """
        判断是否需要重定向（低阈值意图）

        Args:
            confidence: 置信度
            category: 意图类别（可选）

        Returns:
            bool: 是否需要重定向
        """
        if category:
            redirect_threshold = category.redirect_threshold
        else:
            # 使用默认重定向阈值
            from backend.src.config.settings import settings
            redirect_threshold = settings.INTENT_REDIRECT_THRESHOLD

        return confidence < redirect_threshold

    def is_confident(self, confidence: float, category: Optional[IntentCategory] = None) -> bool:
        """
        判断是否置信度高

        Args:
            confidence: 置信度
            category: 意图类别（可选）

        Returns:
            bool: 是否置信度高
        """
        if category:
            threshold = category.threshold
        else:
            # 使用默认阈值
            from backend.src.config.settings import settings
            threshold = settings.INTENT_CLASSIFICATION_THRESHOLD

        return confidence >= threshold

    async def cleanup(self):
        """
        清理分类器资源
        """
        pass


class HybridIntentClassifier(BaseIntentClassifier):
    """
    混合意图分类器
    结合BERT和LLM进行意图识别
    """

    def __init__(self):
        super().__init__()
        self.bert_classifier = None
        self.llm_classifier = None

    async def initialize(self):
        """
        初始化混合分类器
        """
        if self._initialized:
            return

        try:
            # 初始化BERT分类器
            from .bert_classifier import BERTIntentClassifier
            self.bert_classifier = BERTIntentClassifier()
            await self.bert_classifier.initialize()

            # 初始化LLM分类器
            from .llm_classifier import LLMIntentClassifier
            self.llm_classifier = LLMIntentClassifier()
            await self.llm_classifier.initialize()

            # 加载意图类别
            await self._load_categories()

            self._initialized = True
            logger.info("混合意图分类器初始化完成")

        except Exception as e:
            logger.error(f"混合意图分类器初始化失败: {e}", exc_info=True)
            raise

    async def _load_categories(self):
        """
        加载意图类别
        """
        try:
            # 这里应该从数据库加载意图类别
            # 暂时使用默认类别
            default_categories = [
                IntentCategory(
                    id="general_chat",
                    name="general_chat",
                    description="通用聊天",
                    threshold=0.6,
                    redirect_threshold=0.3,
                    handler_agent="chat_agent",
                ),
                IntentCategory(
                    id="research",
                    name="research",
                    description="研究查询",
                    threshold=0.7,
                    redirect_threshold=0.4,
                    handler_agent="research_agent",
                ),
                IntentCategory(
                    id="coding",
                    name="coding",
                    description="编程相关",
                    threshold=0.8,
                    redirect_threshold=0.5,
                    handler_agent="coding_agent",
                ),
                IntentCategory(
                    id="tool_usage",
                    name="tool_usage",
                    description="工具使用",
                    threshold=0.75,
                    redirect_threshold=0.4,
                    handler_agent="tool_agent",
                ),
                IntentCategory(
                    id="planning",
                    name="planning",
                    description="规划任务",
                    threshold=0.7,
                    redirect_threshold=0.4,
                    handler_agent="plan_execute_agent",
                ),
            ]

            for category in default_categories:
                self.add_category(category)

            logger.info(f"加载了 {len(default_categories)} 个默认意图类别")

        except Exception as e:
            logger.error(f"加载意图类别失败: {e}")
            # 不抛出异常，允许分类器继续运行

    async def classify(self, text: str, context: Optional[Dict[str, Any]] = None) -> IntentResult:
        """
        对文本进行意图分类

        Args:
            text: 要分类的文本
            context: 上下文信息

        Returns:
            IntentResult: 意图识别结果
        """
        try:
            if not self._initialized:
                await self.initialize()

            # 文本预处理（URL、数字、空白规范化）
            from .utils.preprocessing import preprocess_text
            cleaned_text = preprocess_text(text)

            # 首先使用BERT分类器进行快速分类
            bert_result = await self.bert_classifier.classify(cleaned_text, context)

            # 检查置信度
            if self.is_confident(bert_result.confidence):
                # 置信度高，直接返回BERT结果
                return await self._enrich_result(bert_result)

            # 置信度低，使用LLM分类器进行精确分类
            llm_result = await self.llm_classifier.classify(cleaned_text, context)

            # 返回LLM结果（通常更准确）
            return await self._enrich_result(llm_result)

        except Exception as e:
            logger.error(f"意图分类失败: text={text}, error={e}", exc_info=True)
            # 返回默认结果
            return IntentResult(
                intent="unknown",
                confidence=0.0,
                category="unknown",
                metadata={"error": str(e)},
            )

    async def batch_classify(
        self,
        texts: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[IntentResult]:
        """
        批量意图分类

        Args:
            texts: 要分类的文本列表
            context: 上下文信息

        Returns:
            List[IntentResult]: 意图识别结果列表
        """
        try:
            if not self._initialized:
                await self.initialize()

            results = []

            # 批量处理
            for text in texts:
                result = await self.classify(text, context)
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"批量意图分类失败: error={e}", exc_info=True)
            # 返回默认结果列表
            return [
                IntentResult(
                    intent="unknown",
                    confidence=0.0,
                    category="unknown",
                    metadata={"error": str(e)},
                )
                for _ in texts
            ]

    async def _enrich_result(self, result: IntentResult) -> IntentResult:
        """
        丰富结果信息

        Args:
            result: 原始结果

        Returns:
            IntentResult: 丰富后的结果
        """
        # 查找对应的类别
        category = self.find_category_by_intent(result.intent)
        if category:
            result.category = category.id

            # 检查是否需要重定向
            result.metadata["should_redirect"] = self.should_redirect(result.confidence, category)
            result.metadata["is_confident"] = self.is_confident(result.confidence, category)
            result.metadata["handler_agent"] = category.handler_agent

        return result

    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            Dict[str, Any]: 健康状态信息
        """
        try:
            bert_health = await self.bert_classifier.health_check()
            llm_health = await self.llm_classifier.health_check()

            overall_healthy = (
                bert_health.get("status") == "healthy" and
                llm_health.get("status") == "healthy"
            )

            return {
                "status": "healthy" if overall_healthy else "unhealthy",
                "bert_classifier": bert_health,
                "llm_classifier": llm_health,
                "category_count": len(self.categories),
            }

        except Exception as e:
            logger.error(f"混合意图分类器健康检查失败: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    async def cleanup(self):
        """
        清理分类器资源
        """
        try:
            if self.bert_classifier:
                await self.bert_classifier.cleanup()
            if self.llm_classifier:
                await self.llm_classifier.cleanup()

            logger.info("混合意图分类器资源清理完成")

        except Exception as e:
            logger.error(f"清理混合意图分类器资源失败: {e}")


# 全局意图分类器实例
intent_classifier = HybridIntentClassifier()