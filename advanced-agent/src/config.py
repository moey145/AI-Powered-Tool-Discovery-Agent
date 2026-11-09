from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: SecretStr
    openai_model: str = "gpt-6-luna"

    search_provider: Literal["auto", "brave", "google_custom_search", "duckduckgo"] = "auto"
    brave_search_api_key: SecretStr | None = None
    google_custom_search_api_key: SecretStr | None = None
    google_search_engine_id: str | None = None

    max_tools: int = 6
    max_concurrent_research: int = 4
    max_page_chars: int = 6000
    max_page_bytes: int = 2_000_000
    min_page_chars: int = 200

    http_timeout: float = 10.0
    llm_timeout: float = 25.0
    research_timeout: float = 40.0
    total_timeout: float = 90.0
    cache_ttl_seconds: int = 3600

    user_agent: str = "ToolDiscoveryAgent/2.0"

    allowed_origins: str = "http://localhost:5173"
    rate_limit_per_minute: int = 5
    daily_search_budget: int = 200

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
