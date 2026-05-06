"""
意图识别系统模块
"""
from .classifier import (
    BaseIntentClassifier,
    HybridIntentClassifier,
    IntentResult,
    IntentCategory,
    intent_classifier,
)
from .llm_classifier import LLMIntentClassifier
from .bert_classifier import BERTIntentClassifier
from .router import IntentRouter, RouteDecision, intent_router
from .models import IntentModel, IntentPrediction, BERTModel
from .utils import TextPreprocessor, preprocess_text, tokenize_text, IntentEvaluator, compute_metrics

__all__ = [
    # 分类器
    "BaseIntentClassifier",
    "HybridIntentClassifier",
    "LLMIntentClassifier",
    "BERTIntentClassifier",
    "IntentResult",
    "IntentCategory",
    # 路由器
    "IntentRouter",
    "RouteDecision",
    # 模型
    "IntentModel",
    "IntentPrediction",
    "BERTModel",
    # 工具
    "TextPreprocessor",
    "preprocess_text",
    "tokenize_text",
    "IntentEvaluator",
    "compute_metrics",
    # 全局实例
    "intent_classifier",
    "intent_router",
]
