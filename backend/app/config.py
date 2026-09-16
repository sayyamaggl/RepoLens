"""RepoLens configuration — loads from environment variables."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str
    database_url_sync: str

    # LLM
    llm_provider: str = "openrouter"  # "anthropic" or "google" or "openrouter"
    openrouter_api_key: str = ""
    openrouter_model: str = "openrouter/free"
    anthropic_api_key: str = ""
    google_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # GitHub
    github_token: str = ""

    # Repo cloning
    clone_dir: str = "/tmp/repos"

    # App
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

# Ensure clone directory exists
Path(settings.clone_dir).mkdir(parents=True, exist_ok=True)