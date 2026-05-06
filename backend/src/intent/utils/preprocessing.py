"""
文本预处理工具
用于意图分类前的文本清洗和标准化
"""
import re
import logging
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)


class TextPreprocessor:
    """
    文本预处理器
    提供文本清洗、标准化、分词等功能
    """

    # URL正则
    URL_PATTERN = re.compile(r"https?://\S+|www\.\S+")

    # 邮箱正则
    EMAIL_PATTERN = re.compile(r"\S+@\S+\.\S+")

    # 数字正则
    NUMBER_PATTERN = re.compile(r"\d+")

    # 多余空白字符
    WHITESPACE_PATTERN = re.compile(r"\s+")

    # 标点符号（中英文）
    PUNCTUATION_PATTERN = re.compile(r"[^\w\s\u4e00-\u9fff]")

    def __init__(
        self,
        lowercase: bool = True,
        remove_urls: bool = True,
        remove_emails: bool = True,
        normalize_numbers: bool = True,
        normalize_whitespace: bool = True,
        remove_punctuation: bool = False,
        max_length: int = 512,
        min_length: int = 2,
    ):
        """
        初始化预处理器

        Args:
            lowercase: 是否转小写
            remove_urls: 是否移除URL
            remove_emails: 是否移除邮箱
            normalize_numbers: 是否规范化数字
            normalize_whitespace: 是否规范化空白
            remove_punctuation: 是否移除标点
            max_length: 最大文本长度
            min_length: 最小文本长度
        """
        self.lowercase = lowercase
        self.remove_urls = remove_urls
        self.remove_emails = remove_emails
        self.normalize_numbers = normalize_numbers
        self.normalize_whitespace = normalize_whitespace
        self.remove_punctuation = remove_punctuation
        self.max_length = max_length
        self.min_length = min_length

    def preprocess(self, text: str) -> str:
        """
        预处理文本

        Args:
            text: 原始文本

        Returns:
            处理后的文本
        """
        if not text:
            return ""

        # 移除URL
        if self.remove_urls:
            text = self.URL_PATTERN.sub("[URL]", text)

        # 移除邮箱
        if self.remove_emails:
            text = self.EMAIL_PATTERN.sub("[EMAIL]", text)

        # 规范化数字
        if self.normalize_numbers:
            text = self.NUMBER_PATTERN.sub("[NUM]", text)

        # 转小写
        if self.lowercase:
            text = text.lower()

        # 移除标点
        if self.remove_punctuation:
            text = self.PUNCTUATION_PATTERN.sub(" ", text)

        # 规范化空白
        if self.normalize_whitespace:
            text = self.WHITESPACE_PATTERN.sub(" ", text).strip()

        # 截断长度
        if len(text) > self.max_length:
            text = text[:self.max_length]

        return text

    def preprocess_batch(self, texts: List[str]) -> List[str]:
        """
        批量预处理

        Args:
            texts: 文本列表

        Returns:
            处理后的文本列表
        """
        return [self.preprocess(text) for text in texts]

    def validate(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        验证文本是否适合分类

        Args:
            text: 文本

        Returns:
            (是否有效, 错误信息)
        """
        processed = self.preprocess(text)

        if not processed:
            return False, "文本为空"

        if len(processed) < self.min_length:
            return False, f"文本过短: {len(processed)} < {self.min_length}"

        if len(processed) > self.max_length * 2:
            return False, f"文本过长: {len(processed)} > {self.max_length * 2}"

        return True, None

    def extract_features(self, text: str) -> Dict[str, Any]:
        """
        提取文本特征

        Args:
            text: 文本

        Returns:
            特征字典
        """
        processed = self.preprocess(text)

        # 中文检测
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", processed))

        # 英文检测
        english_words = len(re.findall(r"[a-zA-Z]+", processed))

        # 数字检测
        numbers = len(re.findall(r"\[NUM\]", processed))

        # 特殊标记
        url_count = len(re.findall(r"\[URL\]", processed))
        email_count = len(re.findall(r"\[EMAIL\]", processed))

        return {
            "text_length": len(processed),
            "word_count": len(processed.split()),
            "chinese_chars": chinese_chars,
            "english_words": english_words,
            "numbers": numbers,
            "urls": url_count,
            "emails": email_count,
            "is_chinese_dominant": chinese_chars > english_words,
            "is_empty": len(processed) == 0,
        }


# 全局预处理器实例
_default_preprocessor = TextPreprocessor()


def preprocess_text(text: str, **kwargs) -> str:
    """
    便捷函数：预处理文本

    Args:
        text: 原始文本
        **kwargs: 预处理器参数

    Returns:
        处理后的文本
    """
    if kwargs:
        preprocessor = TextPreprocessor(**kwargs)
        return preprocessor.preprocess(text)
    return _default_preprocessor.preprocess(text)


def tokenize_text(text: str, mode: str = "char") -> List[str]:
    """
    便捷函数：分词

    Args:
        text: 文本
        mode: 分词模式 (char/word/mixed)

    Returns:
        Token列表
    """
    text = _default_preprocessor.preprocess(text)

    if mode == "char":
        return list(text)
    elif mode == "word":
        return text.split()
    elif mode == "mixed":
        tokens = []
        for char in text:
            if "\u4e00" <= char <= "\u9fff":
                tokens.append(char)
            elif char.isalpha():
                if tokens and tokens[-1].isalpha():
                    tokens[-1] += char
                else:
                    tokens.append(char)
            else:
                if char.strip():
                    tokens.append(char)
        return tokens
    else:
        raise ValueError(f"不支持的分词模式: {mode}")
