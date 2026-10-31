from decimal import Decimal
from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# total >= first value: 2 levels; total >= second value: 3 levels. Per currency; amounts are never converted between currencies.
DEFAULT_THRESHOLDS = {
    "INR": [Decimal("100000"), Decimal("1000000")],
    "USD": [Decimal("1500"), Decimal("15000")],
    "EUR": [Decimal("1400"), Decimal("14000")],
    "GBP": [Decimal("1200"), Decimal("12000")],
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    database_url: str | None = None  # or DB_HOST, DB_NAME, DB_USER, DB_PASSWORD
    jwt_secret: SecretStr  # same value the auth service signs with
    jwt_issuer: str = "procurehub-auth"
    jwt_audience: str = "procurehub"
    internal_jwt_secret: SecretStr  # signs and verifies service-to-service calls
    purchase_request_service_url: str | None = None  # e.g. http://purchase-request-service:8002
    auth_service_url: str | None = None  # e.g. http://auth-service:8001
    approval_thresholds: dict[str, list[Decimal]] = DEFAULT_THRESHOLDS  # override with a JSON object in APPROVAL_THRESHOLDS
    escalation_hours: int = 48  # a pending step older than this is flagged overdue
    background_jobs: bool = True  # retry loop for decisions and the overdue check
    reconcile_interval_seconds: int = 20
    docs_enabled: bool = True
    log_level: str = "INFO"

    @field_validator("jwt_secret", "internal_jwt_secret")
    @classmethod
    def _secret_is_long_enough(cls, v: SecretStr) -> SecretStr:
        if len(v.get_secret_value()) < 32:
            raise ValueError("JWT secrets must be at least 32 characters")
        return v

    @field_validator("approval_thresholds")
    @classmethod
    def _thresholds_make_sense(cls, v: dict[str, list[Decimal]]) -> dict[str, list[Decimal]]:
        for cur, t in v.items():
            if len(t) != 2 or not (0 < t[0] < t[1]):
                raise ValueError(f"Thresholds for {cur} must be two increasing positive amounts")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
