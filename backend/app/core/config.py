"""应用核心配置。"""

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置，从环境变量或 .env 文件读取。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- 基础 ---
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "dev-secret-key-change-in-production-please-use-a-long-random-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- 数据库 ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/smart_invoice"
    DATABASE_SYNC_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/smart_invoice"

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- RabbitMQ ---
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672//"

    # --- MinIO ---
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "smart-invoice"
    MINIO_SECURE: bool = False

    # --- AI ---
    AI_TEXT_API_URL: str = ""
    AI_TEXT_API_KEY: str = ""
    AI_TEXT_MODEL: str = "gpt-4o-mini"
    AI_MULTIMODAL_API_URL: str = ""
    AI_MULTIMODAL_API_KEY: str = ""
    AI_MULTIMODAL_MODEL: str = "gpt-4o"
    AI_USE_MOCK: bool = True  # 默认使用Mock（不依赖外部API）
    AI_MAX_INPUT_LENGTH: int = 10000
    AI_TIMEOUT_SECONDS: int = 30
    AI_CONFIDENCE_THRESHOLD: float = 0.85

    # --- CORS ---
    CORS_ORIGINS: List[str] = ["*"]

    # --- 百望云通道 ---
    BAIWANG_APP_KEY: str = ""
    BAIWANG_APP_SECRET: str = ""
    BAIWANG_API_BASE_URL: str = "https://open.baiwang.com"
    BAIWANG_ACCOUNT_ID: str = ""

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # --- 初始超级管理员 ---
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "admin123456"
    DEFAULT_ADMIN_EMAIL: str = "admin@smart-invoice.local"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
