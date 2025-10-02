from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # API Keys
    openai_api_key: str
    google_custom_search_api_key: Optional[str] = None
    google_search_engine_id: Optional[str] = None
    
    # Search Configuration
    search_provider: str = "auto"  # "google_custom_search", "duckduckgo", "auto"
    max_search_results: int = 6
    search_variants_limit: int = 4
    
    # Scraping Configuration
    max_concurrent_scrapes: int = 5  # Increased concurrency
    scrape_timeout: int = 15  # Reduced timeout for faster failures
    max_content_length: int = 8000
    min_content_length: int = 100
    
    # Retry Configuration
    max_retries: int = 3
    failure_threshold: int = 3
    recovery_timeout: int = 60
    
    # API Timeouts
    google_custom_search_timeout: int = 15
    
    class Config:
        env_file = ".env"
        env_prefix = ""

# Global settings instance
settings = Settings()

# Validate required settings
if not settings.openai_api_key:
    raise ValueError("OPENAI_API_KEY is required")

# Validate Google Custom Search if it's the primary provider
if settings.search_provider == "google_custom_search":
    if not settings.google_custom_search_api_key:
        raise ValueError("GOOGLE_CUSTOM_SEARCH_API_KEY is required when search_provider is 'google_custom_search'")
    if not settings.google_search_engine_id:
        raise ValueError("GOOGLE_SEARCH_ENGINE_ID is required when search_provider is 'google_custom_search'")
