"""Application configuration.

Every setting is read from the environment (see `.env.example`). No secret is
never hardcoded here, and the module is safe to import from tests.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---------------------------------------------------------------
    app_name: str = "NeuraChat"
    environment: str = "development"
    debug: bool = False

    # --- Database ----------------------------------------------------------
    database_url: str = "sqlite:///./neurachat.db"

    # --- Auth --------------------------------------------------------------
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    # --- LLM ---------------------------------------------------------------
    llm_provider: str = "auto"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 60.0

    # --- Security ----------------------------------------------------------
    cors_origins: str = "*"
    rate_limit_per_minute: int = 60

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS origins as a list; `*` means allow any origin."""
        raw = (self.cors_origins or "").strip()
        if raw in {"", "*"}:
            return ["*"]
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    @property
    def has_llm_key(self) -> bool:
        return bool(self.openai_api_key and self.openai_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor (one instance per process)."""
    return Settings()


settings = get_settings()
