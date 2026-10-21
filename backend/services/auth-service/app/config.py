"""Runtime configuration. Everything comes from environment variables; there are no usable defaults for secrets."""
from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    database_url: str | None = None  # or DB_HOST, DB_NAME, DB_USER, DB_PASSWORD (see app/dburl.py)
    jwt_secret: SecretStr
    jwt_issuer: str = "procurehub-auth"
    jwt_audience: str = "procurehub"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7
    refresh_reuse_grace_seconds: int = 10
    cookie_name: str = "ph_refresh"
    cookie_secure: bool = True  # set COOKIE_SECURE=false only for plain-http local development
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    docs_enabled: bool = True
    log_level: str = "INFO"

    @field_validator("jwt_secret")
    @classmethod
    def _secret_is_long_enough(cls, v: SecretStr) -> SecretStr:
        if len(v.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
