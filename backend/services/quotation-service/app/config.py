from functools import lru_cache

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    database_url: str | None = None  # or DB_HOST, DB_NAME, DB_USER, DB_PASSWORD
    jwt_secret: SecretStr  # same value the auth service signs with
    internal_jwt_secret: SecretStr | None = None  # signs calls to other services and verifies calls from them
    vendor_service_url: str | None = None  # e.g. http://vendor-service:8004
    purchase_request_service_url: str | None = None  # e.g. http://purchase-request-service:8002
    jwt_issuer: str = "procurehub-auth"
    jwt_audience: str = "procurehub"
    min_deadline_hours: int = 1  # an RFQ deadline must be at least this far ahead when it is set or issued
    max_deadline_days: int = 365
    docs_enabled: bool = True
    log_level: str = "INFO"

    @field_validator("jwt_secret", "internal_jwt_secret")
    @classmethod
    def _secret_is_long_enough(cls, v: SecretStr | None) -> SecretStr | None:
        if v is not None and len(v.get_secret_value()) < 32:
            raise ValueError("JWT secrets must be at least 32 characters")
        return v

    @model_validator(mode="after")
    def _calls_need_a_secret(self) -> "Settings":
        if (self.vendor_service_url or self.purchase_request_service_url) and self.internal_jwt_secret is None:
            raise ValueError("INTERNAL_JWT_SECRET is required when VENDOR_SERVICE_URL or PURCHASE_REQUEST_SERVICE_URL is set")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
