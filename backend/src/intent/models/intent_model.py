"""
意图数据模型
定义意图相关的数据结构和预测结果
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class IntentPrediction:
    """单条意图预测结果"""
    intent: str
    confidence: float
    rank: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.confidence = max(0.0, min(1.0, self.confidence))

    @property
    def is_high_confidence(self, threshold: float = 0.7) -> bool:
        return self.confidence >= threshold

    @property
    def is_low_confidence(self, threshold: float = 0.3) -> bool:
        return self.confidence < threshold


@dataclass
class IntentModel:
    """
    意图识别模型数据类
    封装单次分类的所有预测结果
    """
    predictions: List[IntentPrediction] = field(default_factory=list)
    text: str = ""
    text_length: int = 0
    processing_time_ms: float = 0.0
    model_name: str = "unknown"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def top_intent(self) -> Optional[IntentPrediction]:
        """获取最高置信度的意图"""
        if not self.predictions:
            return None
        return sorted(self.predictions, key=lambda p: p.confidence, reverse=True)[0]

    @property
    def top_intent_label(self) -> str:
        """获取最高置信度的意图标签"""
        top = self.top_intent
        return top.intent if top else "unknown"

    @property
    def top_confidence(self) -> float:
        """获取最高置信度"""
        top = self.top_intent
        return top.confidence if top else 0.0

    @property
    def all_intents(self) -> List[str]:
        """获取所有预测的意图标签"""
        return [p.intent for p in self.predictions]

    @property
    def confident_predictions(self, threshold: float = 0.7) -> List[IntentPrediction]:
        """获取高置信度预测"""
        return [p for p in self.predictions if p.is_high_confidence(threshold)]

    def get_alternatives(self, exclude_top: bool = True) -> List[IntentPrediction]:
        """获取备选意图"""
        if not self.predictions:
            return []
        sorted_preds = sorted(self.predictions, key=lambda p: p.confidence, reverse=True)
        return sorted_preds[1:] if exclude_top else sorted_preds

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "predictions": [
                {
                    "intent": p.intent,
                    "confidence": p.confidence,
                    "rank": p.rank,
                }
                for p in self.predictions
            ],
            "text": self.text[:200],
            "text_length": self.text_length,
            "processing_time_ms": self.processing_time_ms,
            "model_name": self.model_name,
            "timestamp": self.timestamp,
            "top_intent": self.top_intent_label,
            "top_confidence": self.top_confidence,
        }

    @classmethod
    def from_predictions(
        cls,
        predictions: List[Dict[str, Any]],
        text: str = "",
        model_name: str = "unknown",
        processing_time_ms: float = 0.0,
    ) -> "IntentModel":
        """从预测列表创建模型"""
        intent_predictions = [
            IntentPrediction(
                intent=p.get("intent", "unknown"),
                confidence=p.get("confidence", 0.0),
                rank=i + 1,
                metadata=p.get("metadata", {}),
            )
            for i, p in enumerate(predictions)
        ]
        return cls(
            predictions=intent_predictions,
            text=text,
            text_length=len(text),
            processing_time_ms=processing_time_ms,
            model_name=model_name,
        )
