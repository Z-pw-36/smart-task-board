from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "Smart Task Board API"
    app_env: str = "development"
    app_debug: bool = False
    app_timezone: str = "Asia/Shanghai"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: str = Field(repr=False)
    database_connect_timeout_seconds: int = Field(default=5, ge=1, le=60)
    auth_mode: Literal["disabled", "prototype", "test_header"] = "test_header"
    prototype_auth_enabled: bool = False
    prototype_user_employee_nos: str = ""
    jwt_secret_key: SecretStr | None = Field(default=None, repr=False)
    jwt_issuer: str = "smart-task-board"
    jwt_audience: str = "smart-task-board-web"
    jwt_expire_minutes: int = Field(default=30, ge=1, le=1440)
    allow_test_employee_header: bool = True
    cors_allowed_origins: str = ""
    ai_provider: Literal["fake", "openai_compatible"] = "fake"
    ai_api_key: SecretStr | None = Field(default=None, repr=False)
    ai_base_url: str | None = Field(default=None, repr=False)
    ai_model: str | None = Field(default=None, repr=False)
    ai_request_timeout_seconds: int = Field(default=30, ge=1, le=120)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def prototype_employee_nos(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                value.strip()
                for value in self.prototype_user_employee_nos.split(",")
                if value.strip()
            )
        )

    @property
    def cors_origins(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                value.strip()
                for value in self.cors_allowed_origins.split(",")
                if value.strip()
            )
        )

    @model_validator(mode="after")
    def validate_authentication_settings(self) -> "Settings":
        if "*" in self.cors_origins:
            raise ValueError("CORS_ALLOWED_ORIGINS must not contain '*'")
        if self.app_env.casefold() == "production" and (
            self.auth_mode in {"prototype", "test_header"}
            or self.prototype_auth_enabled
            or self.allow_test_employee_header
        ):
            raise ValueError("prototype and test-header authentication are forbidden in production")
        if self.auth_mode == "prototype":
            if not self.prototype_auth_enabled:
                raise ValueError("PROTOTYPE_AUTH_ENABLED must be true in prototype auth mode")
            if not self.prototype_employee_nos:
                raise ValueError("PROTOTYPE_USER_EMPLOYEE_NOS must not be empty")
            if self.jwt_secret_key is None or len(self.jwt_secret_key.get_secret_value()) < 32:
                raise ValueError("JWT_SECRET_KEY must contain at least 32 characters")
            if self.allow_test_employee_header:
                raise ValueError("ALLOW_TEST_EMPLOYEE_HEADER must be false in prototype auth mode")
        if self.auth_mode == "test_header" and not self.allow_test_employee_header:
            raise ValueError("test_header auth mode requires ALLOW_TEST_EMPLOYEE_HEADER=true")
        if self.ai_provider == "openai_compatible":
            if self.ai_api_key is None or not self.ai_api_key.get_secret_value().strip():
                raise ValueError("AI_API_KEY is required when AI_PROVIDER=openai_compatible")
            if not self.ai_base_url or not self.ai_base_url.strip():
                raise ValueError("AI_BASE_URL is required when AI_PROVIDER=openai_compatible")
            if not self.ai_model or not self.ai_model.strip():
                raise ValueError("AI_MODEL is required when AI_PROVIDER=openai_compatible")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
