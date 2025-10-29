"""
Configuration Management - PRIORITY 1

IMPLEMENTATION STATUS: ✅ IMPLEMENTED

Centralized configuration using Pydantic Settings.
All environment variables are validated and type-checked.

Usage:
    from src.core.config import settings
    
    api_key = settings.google_api_key
    model = settings.llm_model
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Keys (Required)
    google_api_key: str
    serper_api_key: str
    browserless_api_key: Optional[str] = None  # Optional for local browser usage
    
    # LLM Settings
    llm_model: str = "gemini-2.5-flash"  # Changed from lite version for better reliability
    llm_temperature: float = 0.3  # Increased from 0.0 to encourage better response generation
    
    # Server Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    logging_url: str = "http://localhost:3000/api/socket/log"
    
    # Tool Settings
    max_search_results: int = 10
    scraper_timeout: int = 15000
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra env vars


# Global settings instance
settings = Settings() # type: ignore
