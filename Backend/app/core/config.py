"""
VidScholar Backend - Configuration
================================================
Centralized application settings using pydantic-settings.
All environment-specific values (API keys, DB URLs, CORS origins, etc.)
are loaded from a `.env` file (see `.env.example`) and validated here.

Using a single Settings object (imported as `settings` everywhere else)
means we never scatter `os.getenv()` calls throughout the codebase.
"""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ------------------------------------------------------------------
    # General App Info
    # ------------------------------------------------------------------
    PROJECT_NAME: str = "VidScholar"
    API_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"  # development | staging | production

    # ------------------------------------------------------------------
    # Server
    # ------------------------------------------------------------------
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    # Stored as a raw comma-separated string (e.g.
    # "http://localhost:5173,http://127.0.0.1:5173") rather than as
    # List[str]. This is intentional: pydantic-settings attempts to
    # JSON-decode any env var bound to a non-str field BEFORE custom
    # validators run, which raises a SettingsError for plain
    # comma-separated values coming from a real OS environment variable
    # (as opposed to one read from a .env file, where it happens to work).
    # Keeping this as `str` and exposing a `BACKEND_CORS_ORIGINS_LIST`
    # property below sidesteps that bug entirely and works identically
    # whether the value comes from .env, the shell, or Docker Compose.
    BACKEND_CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def BACKEND_CORS_ORIGINS_LIST(self) -> List[str]:
        """Parses BACKEND_CORS_ORIGINS into a clean list of origin strings."""
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]

    # ------------------------------------------------------------------
    # OpenAI / LLM
    # ------------------------------------------------------------------
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # ------------------------------------------------------------------
    # ChromaDB
    # ------------------------------------------------------------------
    CHROMA_PERSIST_DIR: str = "./chroma_data"

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    DATABASE_URL: str = "sqlite:///./vidscholar.db"

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    LOG_LEVEL: str = "INFO"

    # pydantic-settings configuration: where to load env vars from
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # ignore unknown env vars instead of raising
    )


# Singleton settings instance imported throughout the app
settings = Settings()
