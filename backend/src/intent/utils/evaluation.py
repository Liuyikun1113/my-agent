"""
意图分类评估工具
提供分类性能评估、混淆矩阵和指标计算
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ClassificationMetrics:
    """分类指标"""
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    support: int = 0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    true_negatives: int = 0

    @property
    def is_valid(self) -> bool:
        return self.support > 0


@dataclass
class EvaluationResult:
    """评估结果"""
    overall_accuracy: float = 0.0
    macro_precision: float = 0.0
    macro_recall: float = 0.0
    macro_f1: float = 0.0
    weighted_f1: float = 0.0
    per_class_metrics: Dict[str, ClassificationMetrics] = field(default_factory=dict)
    confusion_matrix: Optional[List[List[int]]] = None
    labels: List[str] = field(default_factory=list)
    total_samples: int = 0
    correct_predictions: int = 0
    evaluation_time_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class IntentEvaluator:
    """
    意图分类评估器
    提供完整的分类性能评估功能
    """

    def __init__(self):
        self._history: List[EvaluationResult] = []

    def evaluate(
        self,
        y_true: List[str],
        y_pred: List[str],
        confidences: Optional[List[float]] = None,
        labels: Optional[List[str]] = None,
    ) -> EvaluationResult:
        """
        评估分类性能

        Args:
            y_true: 真实标签
            y_pred: 预测标签
            confidences: 预测置信度（可选）
            labels: 标签列表（可选，自动从数据提取）

        Returns:
            评估结果
        """
        import time
        start_time = time.time()

        if len(y_true) != len(y_pred):
            raise ValueError(f"标签长度不匹配: {len(y_true)} vs {len(y_pred)}")

        if not labels:
            labels = sorted(set(y_true) | set(y_pred))

        n_samples = len(y_true)
        n_correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)

        # 构建混淆矩阵
        confusion_matrix = self._build_confusion_matrix(y_true, y_pred, labels)

        # 计算每类指标
        per_class_metrics = {}
        for i, label in enumerate(labels):
            tp = confusion_matrix[i][i]
            fp = sum(confusion_matrix[j][i] for j in range(len(labels))) - tp
            fn = sum(confusion_matrix[i][j] for j in range(len(labels))) - tp
            tn = n_samples - tp - fp - fn

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

            per_class_metrics[label] = ClassificationMetrics(
                accuracy=(tp + tn) / n_samples if n_samples > 0 else 0.0,
                precision=precision,
                recall=recall,
                f1_score=f1,
                support=sum(1 for t in y_true if t == label),
                true_positives=tp,
                false_positives=fp,
                false_negatives=fn,
                true_negatives=tn,
            )

        # 计算宏平均
        valid_metrics = [m for m in per_class_metrics.values() if m.is_valid]
        if valid_metrics:
            macro_precision = np.mean([m.precision for m in valid_metrics])
            macro_recall = np.mean([m.recall for m in valid_metrics])
            macro_f1 = np.mean([m.f1_score for m in valid_metrics])
        else:
            macro_precision = macro_recall = macro_f1 = 0.0

        # 计算加权平均
        total_support = sum(m.support for m in valid_metrics)
        if total_support > 0:
            weighted_f1 = sum(m.f1_score * m.support for m in valid_metrics) / total_support
        else:
            weighted_f1 = 0.0

        evaluation_time = (time.time() - start_time) * 1000

        result = EvaluationResult(
            overall_accuracy=n_correct / n_samples if n_samples > 0 else 0.0,
            macro_precision=macro_precision,
            macro_recall=macro_recall,
            macro_f1=macro_f1,
            weighted_f1=weighted_f1,
            per_class_metrics=per_class_metrics,
            confusion_matrix=confusion_matrix,
            labels=labels,
            total_samples=n_samples,
            correct_predictions=n_correct,
            evaluation_time_ms=evaluation_time,
        )

        self._history.append(result)
        return result

    def _build_confusion_matrix(
        self, y_true: List[str], y_pred: List[str], labels: List[str]
    ) -> List[List[int]]:
        """构建混淆矩阵"""
        label_to_idx = {label: i for i, label in enumerate(labels)}
        n_labels = len(labels)

        matrix = [[0] * n_labels for _ in range(n_labels)]

        for true_label, pred_label in zip(y_true, y_pred):
            true_idx = label_to_idx.get(true_label)
            pred_idx = label_to_idx.get(pred_label)
            if true_idx is not None and pred_idx is not None:
                matrix[true_idx][pred_idx] += 1

        return matrix

    def evaluate_with_thresholds(
        self,
        y_true: List[str],
        y_pred: List[str],
        confidences: List[float],
        thresholds: Optional[List[float]] = None,
    ) -> Dict[float, EvaluationResult]:
        """
        在不同阈值下评估性能

        Args:
            y_true: 真实标签
            y_pred: 预测标签
            confidences: 置信度
            thresholds: 阈值列表

        Returns:
            不同阈值下的评估结果
        """
        if thresholds is None:
            thresholds = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

        results = {}
        for threshold in thresholds:
            # 低置信度的预测标记为unknown
            filtered_pred = [
                pred if conf >= threshold else "unknown"
                for pred, conf in zip(y_pred, confidences)
            ]
            results[threshold] = self.evaluate(y_true, filtered_pred)

        return results

    def compare_models(
        self,
        model_results: Dict[str, Tuple[List[str], List[str]]],
        labels: Optional[List[str]] = None,
    ) -> Dict[str, EvaluationResult]:
        """
        比较多个模型的性能

        Args:
            model_results: {model_name: (y_true, y_pred)}
            labels: 标签列表

        Returns:
            各模型的评估结果
        """
        results = {}
        for model_name, (y_true, y_pred) in model_results.items():
            results[model_name] = self.evaluate(y_true, y_pred, labels=labels)

        return results

    def get_best_threshold(
        self,
        y_true: List[str],
        y_pred: List[str],
        confidences: List[float],
        metric: str = "f1",
    ) -> Tuple[float, float]:
        """
        找到最佳阈值

        Args:
            y_true: 真实标签
            y_pred: 预测标签
            confidences: 置信度
            metric: 优化指标

        Returns:
            (最佳阈值, 最佳指标值)
        """
        threshold_results = self.evaluate_with_thresholds(y_true, y_pred, confidences)

        best_threshold = 0.5
        best_value = 0.0

        for threshold, result in threshold_results.items():
            if metric == "accuracy":
                value = result.overall_accuracy
            elif metric == "f1":
                value = result.macro_f1
            elif metric == "precision":
                value = result.macro_precision
            elif metric == "recall":
                value = result.macro_recall
            else:
                value = result.macro_f1

            if value > best_value:
                best_value = value
                best_threshold = threshold

        return best_threshold, best_value

    def get_evaluation_summary(self) -> Dict[str, Any]:
        """获取评估历史摘要"""
        if not self._history:
            return {"total_evaluations": 0}

        latest = self._history[-1]
        return {
            "total_evaluations": len(self._history),
            "latest_accuracy": latest.overall_accuracy,
            "latest_macro_f1": latest.macro_f1,
            "latest_weighted_f1": latest.weighted_f1,
            "best_accuracy": max(r.overall_accuracy for r in self._history),
            "best_macro_f1": max(r.macro_f1 for r in self._history),
        }

    def reset_history(self):
        """清空评估历史"""
        self._history.clear()


# 全局评估器实例
_default_evaluator = IntentEvaluator()


def compute_metrics(
    y_true: List[str],
    y_pred: List[str],
    confidences: Optional[List[float]] = None,
) -> EvaluationResult:
    """
    便捷函数：计算分类指标

    Args:
        y_true: 真实标签
        y_pred: 预测标签
        confidences: 置信度（可选）

    Returns:
        评估结果
    """
    return _default_evaluator.evaluate(y_true, y_pred, confidences)
