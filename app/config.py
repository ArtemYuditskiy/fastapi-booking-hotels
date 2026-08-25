from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    MODE: Literal["DEV", "TEST", "PROD"] = "DEV"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/hotel_booking"
    )
    TEST_DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/hotel_booking_test"
    )

    JWT_SECRET: str = "development-only-secret-change-me-now"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    REDIS_CACHE_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_BEAT_INTERVAL_SECONDS: int = Field(default=60, gt=0)
    CELERY_TASK_ALWAYS_EAGER: bool = False
    NOTIFICATION_DISPATCH_INTERVAL_SECONDS: int = Field(default=10, gt=0)
    NOTIFICATION_BATCH_SIZE: int = Field(default=100, gt=0, le=1000)
    NOTIFICATION_MAX_ATTEMPTS: int = Field(default=5, gt=0)
    NOTIFICATION_RETRY_BASE_SECONDS: int = Field(default=30, gt=0)
    NOTIFICATION_CLAIM_TIMEOUT_SECONDS: int = Field(default=300, gt=0)
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = Field(default=1025, ge=1, le=65535)
    SMTP_FROM_EMAIL: str = "bookings@example.test"
    SMTP_TIMEOUT_SECONDS: float = Field(default=10.0, gt=0)
    REDIS_SOCKET_TIMEOUT_SECONDS: float = Field(default=0.2, gt=0)
    CATALOG_CACHE_TTL_SECONDS: int = Field(default=300, gt=0)

    @property
    def active_database_url(self) -> str:
        if self.MODE == "TEST":
            return self.TEST_DATABASE_URL
        return self.DATABASE_URL

    @model_validator(mode="after")
    def validate_production_secret(self) -> "Settings":
        if (
            self.MODE == "PROD"
            and self.JWT_SECRET == "development-only-secret-change-me-now"
        ):
            raise ValueError("JWT_SECRET must be changed in production")
        return self

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
