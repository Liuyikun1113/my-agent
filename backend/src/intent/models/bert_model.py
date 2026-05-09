"""
BERT模型封装
提供BERT模型的加载、推理和管理功能
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
import numpy as np

from backend.src.config.settings import settings

logger = logging.getLogger(__name__)


class BERTModel:
    """
    BERT模型封装类
    管理BERT模型的加载、推理和资源释放
    """

    def __init__(self, model_name: Optional[str] = None):
        """
        初始化BERT模型

        Args:
            model_name: 模型名称，默认使用settings中的配置
        """
        self.model_name = model_name or settings.BERT_MODEL_NAME
        self.model_path = settings.BERT_MODEL_PATH
        self.model = None
        self.tokenizer = None
        self._loaded = False
        self._device = "cpu"

    async def load(self) -> bool:
        """
        加载BERT模型

        Returns:
            是否加载成功
        """
        if self._loaded:
            return True

        try:
            # 检测设备
            self._detect_device()

            logger.info(f"加载BERT模型: {self.model_name} (device={self._device})")

            # 占位实现 - 实际项目中需要取消注释以下代码
            # from transformers import AutoModelForSequenceClassification, AutoTokenizer
            # self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            # self.model = AutoModelForSequenceClassification.from_pretrained(
            #     self.model_name, num_labels=len(self._get_labels())
            # )
            # self.model.to(self._device)
            # self.model.eval()

            self._loaded = True
            logger.info(f"BERT模型加载完成: {self.model_name}")

            return True

        except Exception as e:
            logger.error(f"BERT模型加载失败: {e}", exc_info=True)
            return False

    def _detect_device(self):
        """检测可用设备"""
        try:
            import torch
            if torch.cuda.is_available():
                self._device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                self._device = "mps"
            else:
                self._device = "cpu"
        except ImportError:
            self._device = "cpu"

    def _get_labels(self) -> List[str]:
        """获取分类标签"""
        return [
            "general_chat",
            "research",
            "coding",
            "tool_usage",
            "planning",
            "analysis",
        ]

    async def predict(
        self, texts: List[str], return_probs: bool = True
    ) -> List[Dict[str, Any]]:
        """
        批量预测

        Args:
            texts: 文本列表
            return_probs: 是否返回概率分布

        Returns:
            预测结果列表
        """
        if not self._loaded:
            await self.load()

        if not self._loaded:
            return [{"intent": "general_chat", "confidence": 0.5} for _ in texts]

        results = []

        for text in texts:
            try:
                # 占位实现 - 实际项目中需要取消注释以下代码
                # inputs = self.tokenizer(
                #     text, return_tensors="pt", truncation=True,
                #     max_length=512, padding=True,
                # ).to(self._device)
                #
                # with torch.no_grad():
                #     outputs = self.model(**inputs)
                #     probs = torch.softmax(outputs.logits, dim=-1)
                #
                # if return_probs:
                #     pred_idx = torch.argmax(probs, dim=-1).item()
                #     confidence = probs[0][pred_idx].item()
                # else:
                #     pred_idx = torch.argmax(outputs.logits, dim=-1).item()
                #     confidence = 0.0
                #
                # labels = self._get_labels()
                # intent = labels[pred_idx] if pred_idx < len(labels) else "unknown"

                # 临时占位返回
                intent, confidence = self._placeholder_predict(text)

                result = {"intent": intent, "confidence": confidence}

                if return_probs:
                    result["all_predictions"] = [
                        {"intent": label, "confidence": confidence * (0.9 ** i)}
                        for i, label in enumerate(self._get_labels())
                    ]

                results.append(result)

            except Exception as e:
                logger.error(f"预测失败: {e}")
                results.append({"intent": "general_chat", "confidence": 0.5})

        return results

    def _placeholder_predict(self, text: str) -> Tuple[str, float]:
        """占位预测逻辑 — 使用 extract_keywords 提取关键词后匹配意图"""
        from backend.src.utils.helpers import extract_keywords

        keywords = set(extract_keywords(text, max_keywords=10, min_length=2))

        intent_rules = [
            ("research", {"研究", "搜索", "查询", "find", "research", "search", "调查", "资料", "文献", "论文", "数据"}),
            ("coding", {"代码", "编程", "开发", "code", "program", "write", "implement", "函数", "bug", "调试", "算法", "类", "接口"}),
            ("tool_usage", {"工具", "执行", "运行", "tool", "execute", "run", "调用", "使用", "计算"}),
            ("planning", {"计划", "任务", "规划", "plan", "task", "todo", "安排", "日程", "待办"}),
            ("analysis", {"分析", "计算", "统计", "analyze", "calculate", "评估", "比较", "总结", "报告"}),
        ]

        best_intent = "general_chat"
        best_score = 0.0

        for intent, intent_keywords in intent_rules:
            overlap = keywords & intent_keywords
            if overlap:
                score = len(overlap) / len(intent_keywords)
                if score > best_score:
                    best_score = score
                    best_intent = intent

        if best_intent != "general_chat":
            confidence = min(0.95, 0.65 + best_score * 0.3 + np.random.uniform(-0.05, 0.05))
        else:
            confidence = min(0.65, 0.50 + np.random.uniform(-0.05, 0.05))

        return best_intent, confidence

    async def encode(
        self, texts: List[str], pooling: str = "mean"
    ) -> np.ndarray:
        """
        文本编码为向量

        Args:
            texts: 文本列表
            pooling: 池化策略 (mean/cls/max)

        Returns:
            向量数组 (n_texts, hidden_size)
        """
        if not self._loaded:
            await self.load()

        if not self._loaded:
            # 返回随机向量作为占位
            return np.random.randn(len(texts), 768).astype(np.float32)

        # 占位实现
        logger.warning("BERT编码使用占位实现，返回随机向量")
        return np.random.randn(len(texts), 768).astype(np.float32)

    @property
    def is_loaded(self) -> bool:
        """模型是否已加载"""
        return self._loaded

    @property
    def device(self) -> str:
        """当前设备"""
        return self._device

    def unload(self):
        """卸载模型释放内存"""
        self.model = None
        self.tokenizer = None
        self._loaded = False
        logger.info(f"BERT模型已卸载: {self.model_name}")

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "model_name": self.model_name,
            "loaded": self._loaded,
            "device": self._device,
            "labels": self._get_labels(),
        }


# 全局BERT模型实例
bert_model = BERTModel()
