"""PRISM — Application Settings (Pydantic v2)"""
from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.database.connection import database_host_from_url, normalize_database_url

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"

# Load .env before Settings() so DATABASE_URL is available at import time
load_dotenv(ENV_FILE, override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-5"

    # Database — must be set via DATABASE_URL in .env (Supabase)
    database_url: str
    # Set false only if corporate proxy causes SSL cert errors (development)
    database_ssl_verify: bool = True

    redis_url: str = "redis://127.0.0.1:6379/0"

    # Vector store
    chroma_persist_dir: str = "./data/chroma_db"
    chroma_host: str = "127.0.0.1"
    chroma_port: int = 8001

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # Crawlers
    ncbi_api_key: str = ""
    pubmed_email: str = "team@feuji.com"

    # Agent thresholds
    specialist_confidence_threshold: float = 0.70
    human_frustration_threshold: int = 75
    max_chat_history: int = 20
    top_k_initial: int = 10
    top_k_final: int = 10

    # Multilingual
    supported_languages: str = "en,hi,te,es,pa"
    default_language: str = "en"

    # Multimodal
    whisper_model: str = "base"
    upload_dir: str = "./data/uploads"
    max_upload_mb: int = 25

    # CORS
    allowed_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:5177,http://localhost:5178,http://127.0.0.1:5177,http://127.0.0.1:5178"

    # Env
    environment: str = "development"
    log_level: str = "INFO"

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError(
                "DATABASE_URL is required. Add it to .env (Supabase connection string). "
                "Example: postgresql+asyncpg://user:password@db.xxx.supabase.co:5432/postgres"
            )
        host = database_host_from_url(v)
        if host in ("127.0.0.1", "localhost"):
            raise ValueError(
                f"DATABASE_URL points to local host ({host}). "
                "Use your Supabase connection string from Project Settings → Database."
            )
        return normalize_database_url(v)

    @property
    def database_host(self) -> str:
        return database_host_from_url(self.database_url)

    @property
    def origins_list(self):
        return [o.strip() for o in self.allowed_origins.split(",")]

    @property
    def languages_list(self):
        return [l.strip() for l in self.supported_languages.split(",")]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
