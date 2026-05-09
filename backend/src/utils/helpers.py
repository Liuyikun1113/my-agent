"""
通用辅助函数
提供项目范围内通用的工具函数
"""
import uuid
import hashlib
import logging
from typing import Dict, Any, Optional, List, TypeVar
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

T = TypeVar("T")


def generate_id(prefix: str = "", length: int = 12) -> str:
    """
    生成唯一ID

    Args:
        prefix: ID前缀
        length: 随机部分长度

    Returns:
        唯一ID
    """
    random_part = uuid.uuid4().hex[:length]
    if prefix:
        return f"{prefix}_{random_part}"
    return random_part


def truncate_text(text: str, max_length: int = 200, suffix: str = "...") -> str:
    """
    截断文本

    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 截断后缀

    Returns:
        截断后的文本
    """
    if not text or len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def format_timestamp(
    ts: Optional[Any] = None,
    fmt: str = "%Y-%m-%d %H:%M:%S",
    use_local: bool = True,
) -> str:
    """
    格式化时间戳

    Args:
        ts: 时间戳（datetime对象、ISO字符串或None=当前时间）
        fmt: 格式字符串
        use_local: 是否使用本地时间

    Returns:
        格式化的时间字符串
    """
    if ts is None:
        dt = datetime.now()
    elif isinstance(ts, datetime):
        dt = ts
    elif isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return ts
    elif isinstance(ts, (int, float)):
        dt = datetime.fromtimestamp(ts)
    else:
        return str(ts)

    if use_local:
        dt = dt.astimezone()

    return dt.strftime(fmt)


def safe_get(
    data: Dict[str, Any],
    key: str,
    default: T = None,
    valid_types: Optional[tuple] = None,
) -> T:
    """
    安全获取字典值

    Args:
        data: 字典
        key: 键名，支持点号分隔的嵌套键 (a.b.c)
        default: 默认值
        valid_types: 有效的类型

    Returns:
        获取到的值或默认值
    """
    if not data or not isinstance(data, dict):
        return default

    keys = key.split(".")
    current = data

    for k in keys:
        if isinstance(current, dict):
            current = current.get(k)
        else:
            return default

    if current is None:
        return default

    if valid_types and not isinstance(current, valid_types):
        return default

    return current


def chunk_list(data: List[T], chunk_size: int) -> List[List[T]]:
    """
    将列表分块

    Args:
        data: 原始列表
        chunk_size: 块大小

    Returns:
        分块后的列表
    """
    if not data:
        return []
    return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]


def merge_dicts(*dicts: Dict[str, Any], deep: bool = True) -> Dict[str, Any]:
    """
    合并多个字典

    Args:
        *dicts: 要合并的字典
        deep: 是否深度合并

    Returns:
        合并后的字典
    """
    result: Dict[str, Any] = {}

    for d in dicts:
        if not d:
            continue
        for key, value in d.items():
            if deep and key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = merge_dicts(result[key], value, deep=True)
            else:
                result[key] = value

    return result


def extract_keywords(
    text: str,
    max_keywords: int = 10,
    min_length: int = 2,
) -> List[str]:
    """
    提取文本关键词

    Args:
        text: 文本
        max_keywords: 最大关键词数
        min_length: 最小词长度

    Returns:
        关键词列表
    """
    if not text:
        return []

    # 简单的TF-based关键词提取
    import re
    words = re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z]+", text.lower())

    # 过滤短词
    words = [w for w in words if len(w) >= min_length]

    # 停用词
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
        "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你",
        "会", "着", "没有", "看", "好", "自己", "这",
    }

    # 词频统计
    word_freq: Dict[str, int] = {}
    for word in words:
        if word not in stop_words:
            word_freq[word] = word_freq.get(word, 0) + 1

    # 按频率排序
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)

    return [word for word, _ in sorted_words[:max_keywords]]


def hash_string(text: str, algorithm: str = "sha256") -> str:
    """
    计算字符串哈希

    Args:
        text: 文本
        algorithm: 哈希算法

    Returns:
        哈希值
    """
    h = hashlib.new(algorithm)
    h.update(text.encode("utf-8"))
    return h.hexdigest()


def parse_bool(value: Any) -> bool:
    """
    解析布尔值

    Args:
        value: 要解析的值

    Returns:
        布尔值
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on", "y")
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def ensure_list(value: Any) -> List[Any]:
    """
    确保值为列表

    Args:
        value: 任意值

    Returns:
        列表
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    return [value]
