"""
数据验证工具
提供输入验证和数据清洗功能
"""
import re
import logging
from typing import Dict, Any, Optional, Tuple, List

logger = logging.getLogger(__name__)

# 邮箱正则
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# URL正则
URL_PATTERN = re.compile(
    r"^https?://"
    r"([a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+"
    r"[a-zA-Z]{2,}"
    r"(:[0-9]+)?"
    r"(/[^\s]*)?$"
)

# 会话ID正则 (UUID或自定义格式)
SESSION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{8,64}$")

# SQL注入危险关键词
SQL_DANGEROUS_KEYWORDS = [
    "DROP", "DELETE", "TRUNCATE", "ALTER",
    "INSERT", "UPDATE", "SELECT", "UNION",
    "EXEC", "EXECUTE", "SCRIPT",
]

# XSS危险标签
XSS_DANGEROUS_TAGS = [
    "<script", "</script>", "javascript:",
    "onerror=", "onload=", "onclick=",
    "<iframe", "<img", "<svg", "<embed",
]


def validate_email(email: str) -> bool:
    """
    验证邮箱格式

    Args:
        email: 邮箱地址

    Returns:
        是否有效
    """
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_PATTERN.match(email))


def validate_url(url: str) -> bool:
    """
    验证URL格式

    Args:
        url: URL地址

    Returns:
        是否有效
    """
    if not url or not isinstance(url, str):
        return False
    return bool(URL_PATTERN.match(url))


def validate_session_id(session_id: str) -> bool:
    """
    验证会话ID格式

    Args:
        session_id: 会话ID

    Returns:
        是否有效
    """
    if not session_id or not isinstance(session_id, str):
        return False
    return bool(SESSION_ID_PATTERN.match(session_id))


def sanitize_input(
    text: str,
    max_length: int = 10000,
    strip_html: bool = True,
    strip_sql: bool = False,
) -> Tuple[str, List[str]]:
    """
    输入清洗

    Args:
        text: 原始输入
        max_length: 最大长度
        strip_html: 是否移除HTML
        strip_sql: 是否移除SQL注入模式

    Returns:
        (清洗后的文本, 警告列表)
    """
    warnings = []

    if not text or not isinstance(text, str):
        return "", ["输入为空或类型无效"]

    # 长度检查
    if len(text) > max_length:
        warnings.append(f"输入被截断: {len(text)} -> {max_length}")
        text = text[:max_length]

    # HTML/XSS清理
    if strip_html:
        original_len = len(text)
        for tag in XSS_DANGEROUS_TAGS:
            if tag.lower() in text.lower():
                text = text.replace(tag, f"[{tag.upper().strip('<').strip('>')}]")
                warnings.append(f"移除了潜在危险标签: {tag}")

    # SQL注入检测
    if strip_sql:
        text_upper = text.upper()
        for keyword in SQL_DANGEROUS_KEYWORDS:
            if keyword in text_upper:
                warnings.append(f"检测到SQL关键词: {keyword}")

    return text, warnings


def validate_json_schema(
    data: Dict[str, Any],
    schema: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """
    验证JSON数据是否符合schema

    Args:
        data: 要验证的数据
        schema: JSON schema定义

    Returns:
        (是否有效, 错误列表)
    """
    errors = []

    if not isinstance(data, dict):
        return False, ["数据不是字典类型"]

    required_fields = schema.get("required", [])
    for field in required_fields:
        if field not in data:
            errors.append(f"缺少必填字段: {field}")

    properties = schema.get("properties", {})
    for field, field_schema in properties.items():
        if field not in data:
            continue

        value = data[field]
        expected_type = field_schema.get("type")

        if expected_type:
            type_map = {
                "string": str,
                "integer": int,
                "number": (int, float),
                "boolean": bool,
                "array": list,
                "object": dict,
            }
            expected_python_type = type_map.get(expected_type)
            if expected_python_type and not isinstance(value, expected_python_type):
                errors.append(f"字段 '{field}' 类型错误: 期望 {expected_type}, 实际 {type(value).__name__}")

        # 字符串长度验证
        if expected_type == "string" and isinstance(value, str):
            min_len = field_schema.get("minLength")
            max_len = field_schema.get("maxLength")
            if min_len and len(value) < min_len:
                errors.append(f"字段 '{field}' 长度不足: {len(value)} < {min_len}")
            if max_len and len(value) > max_len:
                errors.append(f"字段 '{field}' 长度超限: {len(value)} > {max_len}")

        # 数值范围验证
        if expected_type in ("integer", "number") and isinstance(value, (int, float)):
            minimum = field_schema.get("minimum")
            maximum = field_schema.get("maximum")
            if minimum is not None and value < minimum:
                errors.append(f"字段 '{field}' 值过小: {value} < {minimum}")
            if maximum is not None and value > maximum:
                errors.append(f"字段 '{field}' 值过大: {value} > {maximum}")

        # 枚举验证
        enum_values = field_schema.get("enum")
        if enum_values and value not in enum_values:
            errors.append(f"字段 '{field}' 不在允许的值中: {enum_values}")

    return len(errors) == 0, errors
