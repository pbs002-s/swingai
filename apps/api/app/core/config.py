"""Runtime settings, read from environment variables prefixed with SS_."""

from functools import lru_cache

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SS_", extra="ignore")

    env: str = "production"  # production | demo | development | test (fails closed if unset)
    database_url: str = "postgresql+asyncpg://stitchsense:stitchsense@localhost:5432/stitchsense"

    session_ttl_hours: int = 12
    cookie_secure: bool = False
    max_login_attempts: int = 10
    login_rate_per_minute: int = 10
    ingest_rate_per_minute: int = 120  # requests per device; an edge box sends batches, so this is generous
    lockout_minutes: int = 15

    admin_email: str = "admin@stitchsense.local"
    admin_password: SecretStr | None = None

    simulator_enabled: bool = False
    seed_demo: bool = False  # demo factory + demo logins; never in production
    rules_interval_seconds: float = 20.0

    @model_validator(mode="after")
    def _production_guard(self) -> "Settings":
        if self.env == "production":
            if not self.cookie_secure:
                raise ValueError("SS_COOKIE_SECURE must be true in production")
            if self.admin_password is None or len(self.admin_password.get_secret_value()) < 12:
                raise ValueError("SS_ADMIN_PASSWORD (12+ characters) is required in production")
            if ":stitchsense@" in self.database_url:
                raise ValueError("SS_DATABASE_URL still uses the default database password")
            if self.seed_demo:
                raise ValueError("SS_SEED_DEMO must be off in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
