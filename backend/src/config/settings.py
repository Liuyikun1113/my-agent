"""
应用配置管理
"""
import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, ConfigDict


def _find_env_file() -> str:
    """
    按优先级查找 .env 文件：
    1. 当前工作目录下的 .env
    2. settings.py 同级目录下的 .env
    3. 项目根目录 (backend/../) 下的 .env
    4. 项目根目录下的 .env.example（兜底）
    """
    candidates = []

    # CWD
    cwd_env = Path.cwd() / ".env"
    candidates.append(cwd_env)

    # settings.py 同级目录: backend/src/config/
    config_dir = Path(__file__).resolve().parent / ".env"
    candidates.append(config_dir)

    # backend/ 目录: backend/src/config/../../ = backend/
    backend_dir = (Path(__file__).resolve().parent.parent.parent / ".env")
    candidates.append(backend_dir)

    # 项目根目录: backend/../
    project_root = (Path(__file__).resolve().parent.parent.parent.parent / ".env")
    candidates.append(project_root)

    # .env.example 兜底
    candidates.append(project_root / ".env.example")

    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)

    # 如果都不存在，返回 backend/.env 路径（让 pydantic-settings 静默跳过）
    return str(backend_dir)


class Settings(BaseSettings):
    """
    应用设置

    环境变量加载优先级（后面的覆盖前面的）：
    1. 代码中定义的默认值
    2. .env 文件中的值
    3. 系统环境变量中的值（最高优先级）
    """
    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用配置
    APP_NAME: str = "multi-agent-framework"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # 服务器配置
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    FRONTEND_PORT: int = 5173
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # 数据库配置
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_DATABASE: str = "multi_agent"
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "password"
    MYSQL_ROOT_PASSWORD: str = "rootpassword"

    @property
    def DATABASE_URL(self) -> str:
        """构建数据库连接URL"""
        return (
            f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
        )

    # Redis配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0

    @property
    def REDIS_URL(self) -> str:
        """构建Redis连接URL"""
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # Milvus配置
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_USER: Optional[str] = None
    MILVUS_PASSWORD: Optional[str] = None
    MILVUS_DB_NAME: str = "default"

    # LLM供应商配置
    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4-turbo-preview"

    # Anthropic
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"

    # 本地Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"

    # 默认LLM供应商
    DEFAULT_LLM_PROVIDER: str = "openai"

    # BERT模型配置
    BERT_MODEL_NAME: str = "bert-base-chinese"
    BERT_MODEL_PATH: str = "./models/bert-intent-classifier"

    # 意图识别配置
    INTENT_CLASSIFICATION_THRESHOLD: float = 0.7
    INTENT_REDIRECT_THRESHOLD: float = 0.3

    # 工具调用配置
    TOOL_RETRY_MAX_ATTEMPTS: int = 3
    TOOL_RETRY_BACKOFF_FACTOR: float = 2.0
    TOOL_CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    TOOL_CIRCUIT_BREAKER_RECOVERY_TIMEOUT: int = 60

    # 记忆配置
    SHORT_TERM_MEMORY_TTL: int = 3600  # 1小时
    MEMORY_COMPRESSION_THRESHOLD: int = 20  # 消息数阈值触发压缩
    MEMORY_COMPRESSION_INTERVAL: int = 300  # 5分钟检查一次

    # SSE配置
    SSE_HEARTBEAT_INTERVAL: int = 30  # 秒
    SSE_RECONNECTION_TIMEOUT: int = 5000  # 毫秒

    # 安全配置
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # 限流配置
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60

    # 其他配置
    ENABLE_METRICS: bool = True
    ENABLE_LOGGING: bool = True
    LOG_FILE_PATH: str = "./logs/app.log"

    @property
    def is_production(self) -> bool:
        """是否生产环境"""
        return self.APP_ENV.lower() == "production"

    @property
    def is_development(self) -> bool:
        """是否开发环境"""
        return self.APP_ENV.lower() == "development"

    @property
    def is_testing(self) -> bool:
        """是否测试环境"""
        return self.APP_ENV.lower() == "testing"


# 全局设置实例
settings = Settings()