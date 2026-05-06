"""
BERT意图分类器
使用预训练的BERT模型进行意图分类
"""
import logging
from typing import Dict, List, Optional, Any

from .classifier import BaseIntentClassifier, IntentResult

logger = logging.getLogger(__name__)


class BERTIntentClassifier(BaseIntentClassifier):
    """
    BERT意图分类器
    委托给 BERTModel 进行模型加载和推理
    """

    def __init__(self):
        super().__init__()
        self.bert_model = None

    async def initialize(self):
        if self._initialized:
            return

        try:
            from .models.bert_model import BERTModel

            self.bert_model = BERTModel()
            loaded = await self.bert_model.load()
            if not loaded:
                logger.warning("BERT模型加载失败，将使用规则兜底")

            self._initialized = True
            logger.info("BERT意图分类器初始化完成")

        except Exception as e:
            logger.error(f"BERT意图分类器初始化失败: {e}", exc_info=True)
            raise

    async def classify(
        self, text: str, context: Optional[Dict[str, Any]] = None
    ) -> IntentResult:
        try:
            if not self._initialized:
                await self.initialize()

            results = await self.bert_model.predict([text])
            if results and len(results) > 0:
                result = results[0]
                intent = result.get("intent", "general_chat")
                confidence = float(result.get("confidence", 0.5))
                all_predictions = result.get("all_predictions", [])

                return IntentResult(
                    intent=intent,
                    confidence=confidence,
                    metadata={
                        "classifier": "bert",
                        "model_name": self.bert_model.model_name,
                        "all_predictions": all_predictions,
                    },
                )

            return IntentResult(intent="general_chat", confidence=0.5)

        except Exception as e:
            logger.error(f"BERT意图分类失败: {e}", exc_info=True)
            return IntentResult(
                intent="unknown",
                confidence=0.0,
                metadata={"error": str(e)},
            )

    async def batch_classify(
        self,
        texts: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[IntentResult]:
        try:
            if not self._initialized:
                await self.initialize()

            results = await self.bert_model.predict(texts)
            return [
                IntentResult(
                    intent=r.get("intent", "general_chat"),
                    confidence=float(r.get("confidence", 0.5)),
                    metadata={
                        "classifier": "bert",
                        "all_predictions": r.get("all_predictions", []),
                    },
                )
                for r in results
            ]

        except Exception as e:
            logger.error(f"BERT批量分类失败: {e}", exc_info=True)
            return [
                IntentResult(intent="unknown", confidence=0.0, metadata={"error": str(e)})
                for _ in texts
            ]

    async def health_check(self) -> Dict[str, Any]:
        try:
            if self.bert_model:
                return await self.bert_model.health_check()
            return {"status": "unhealthy", "reason": "bert_model not initialized"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    async def cleanup(self):
        try:
            if self.bert_model:
                self.bert_model.unload()
            self._initialized = False
            logger.info("BERT意图分类器资源清理完成")
        except Exception as e:
            logger.error(f"清理BERT意图分类器资源失败: {e}")
