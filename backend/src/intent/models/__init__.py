"""
意图模型模块
"""
from .intent_model import IntentModel, IntentPrediction
from .bert_model import BERTModel

__all__ = [
    "IntentModel",
    "IntentPrediction",
    "BERTModel",
]
