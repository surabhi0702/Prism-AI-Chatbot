"""PRISM — Application Settings (Pydantic v2)"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(BASE_DIR, ".env"),
        extra="ignore"
    )

    # LLM
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-5"

    # Database
    database_url: str = "postgresql+asyncpg://prism_user:prism_pass@127.0.0.1:5432/prism_db"
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

    @property
    def origins_list(self):
        return [o.strip() for o in self.allowed_origins.split(",")]

    @property
    def languages_list(self):
        return [l.strip() for l in self.supported_languages.split(",")]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
