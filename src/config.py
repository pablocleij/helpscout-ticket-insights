"""Application configuration using Pydantic settings."""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # HelpScout Configuration
    helpscout_api_key: str

    # Database
    database_url: str = "postgresql://helpscout:helpscout@localhost:5432/helpscout_insights"

    # OpenAI Configuration
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4-turbo-preview"

    # Application Settings
    log_level: str = "INFO"
    analysis_batch_size: int = 50
    max_tickets_per_sync: int = 1000

    # Initial Sync Configuration
    sync_start_date: Optional[str] = None
    auto_initial_sync: bool = True
    auto_initial_analysis: bool = True


# Global settings instance
settings = Settings()
