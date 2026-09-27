from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    DATABASE_URL: str = Field(min_length=1)
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Newdigit Smart Oxygen & Energy Intelligence System"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = Field(default=8000, ge=1, le=65535)
    CORS_ORIGINS: str = ""
    REQUIRE_INGEST_AUTH: bool = False
    INGEST_API_KEY: str | None = None

    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    ENABLE_ASYNC_PROCESSING: bool = False

    DB_POOL_SIZE: int = Field(default=10, ge=1, le=100)
    DB_MAX_OVERFLOW: int = Field(default=20, ge=0, le=200)
    DB_POOL_TIMEOUT: int = Field(default=30, ge=1, le=300)

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.startswith(("postgresql://", "postgresql+psycopg2://", "sqlite:///")):
            raise ValueError("DATABASE_URL must use PostgreSQL or SQLite URL syntax")
        return value

    @property
    def cors_origins(self) -> list[str]:
        """Return configured browser origins; an empty value disables CORS."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
