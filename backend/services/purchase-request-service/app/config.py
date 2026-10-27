from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    database_url: str | None = None  # or DB_HOST, DB_NAME, DB_USER, DB_PASSWORD
    jwt_secret: SecretStr  # same value the auth service signs with
    jwt_issuer: str = "procurehub-auth"
    jwt_audience: str = "procurehub"
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
