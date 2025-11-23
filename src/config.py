"""Application configuration using Pydantic settings."""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # HelpScout Configuration
    helpscout_api_key: str
    helpscout_app_id: Optional[str] = None
    helpscout_app_secret: Optional[str] = None
    helpscout_webhook_secret: Optional[str] = None

    # Database
    database_url: str = "postgresql://helpscout:helpscout@localhost:5432/helpscout_insights"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM Provider
    llm_provider: str = "openai"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4-turbo-preview"
    anthropic_api_key: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None
    azure_openai_key: Optional[str] = None

    # Application Settings
    environment: str = "development"
    log_level: str = "INFO"
    sync_interval_hours: int = 6
    analysis_batch_size: int = 50
    max_tickets_per_sync: int = 1000

    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Analysis Configuration
    analysis_lookback_days: int = 7
    top_insights_limit: int = 10
    enable_embeddings: bool = False

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"


# Global settings instance
settings = Settings()
