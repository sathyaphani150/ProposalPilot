"""
ProposalPilot AI — Application Configuration
Manages all settings via environment variables with Pydantic Settings.
"""
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import AnyHttpUrl, Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve the .env file in the root directory relative to this file
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────
    APP_NAME: str = "ProposalPilot AI"
    APP_ENV: str = "development"
    APP_DEBUG: bool = False
    APP_SECRET_KEY: Optional[str] = Field(None, min_length=32)
    APP_CORS_ORIGINS: List[str] = ["http://localhost:5174", "http://localhost:3000"]

    # ── Database ───────────────────────────────────────────────────────
    DATABASE_URL: str = Field(..., pattern=r"^postgresql\+asyncpg://")
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "proposalpilot"

    # ── Redis / Celery ─────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # ── Qdrant ─────────────────────────────────────────────────────────
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION_RFP: str = "rfp_documents"
    QDRANT_COLLECTION_KB: str = "internal_knowledge_base"
    QDRANT_COLLECTION_PROPOSALS: str = "proposals"

    # ── LLM ────────────────────────────────────────────────────────────
    LLM_PROVIDER: str = "groq"  # openai | azure | google | groq | ollama
    LLM_MODEL: str = "openai/gpt-oss-120b"
    RFP_ANALYSIS_MODEL: str = "openai/gpt-oss-120b"
    ARCHITECTURE_MODEL: str = "openai/gpt-oss-120b"
    OPENAI_API_KEY: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_DEPLOYMENT_NAME: str = "gpt-4o"
    AZURE_OPENAI_API_VERSION: str = "2024-02-01"
    GOOGLE_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    GROQ_API_KEY1: str = ""
    GROQ_API_KEY2: str = ""
    GROQ_API_KEY3: str = ""
    GROQ_API_KEYS: str = ""
    OLLAMA_URL: str = "http://localhost:11434/api/generate"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536

    # ── File Storage ───────────────────────────────────────────────────
    UPLOAD_DIR: str = "./storage/uploads"
    MAX_UPLOAD_SIZE_MB: int = 20
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "docx", "txt", "md"]

    # ── JWT ────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: Optional[str] = Field(None, min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # ── Observability ──────────────────────────────────────────────────
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "proposalpilot"
    LANGCHAIN_TRACING_V2: bool = False

    @computed_field  # type: ignore[misc]
    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @field_validator("APP_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("[") and v.endswith("]"):
                try:
                    import json
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed]
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v

    @field_validator("ALLOWED_EXTENSIONS", mode="before")
    @classmethod
    def parse_extensions(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("[") and v.endswith("]"):
                try:
                    import json
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(item).strip().lower() for item in parsed]
                except Exception:
                    pass
            return [ext.strip().lower() for ext in v.split(",") if ext.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def groq_api_keys(self) -> list[str]:
        keys: list[str] = []
        for raw_value in (
            self.GROQ_API_KEYS,
            self.GROQ_API_KEY,
            self.GROQ_API_KEY1,
            self.GROQ_API_KEY2,
            self.GROQ_API_KEY3,
        ):
            for key in str(raw_value or "").split(","):
                cleaned = key.strip()
                if cleaned and cleaned not in keys:
                    keys.append(cleaned)
        return keys


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — singleton pattern."""
    return Settings()  # type: ignore[call-arg]
