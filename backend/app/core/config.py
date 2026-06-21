from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    APP_NAME: str = "AlertIQ Backend"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS - comma-separated list of allowed origins
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    # Database
    DATABASE_URL: str = "postgresql://alertiq:alertiq@localhost:5432/alertiq"

    # ── Resolution Copilot (RAG) ──────────────────────────────────────
    # Generation provider switch: "anthropic" or "google". Selects which
    # LLM the copilot uses for generation; embeddings stay on Voyage.
    LLM_PROVIDER: str = "anthropic"

    # Anthropic Claude
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-opus-4-8"

    # Google Gemini
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Embeddings — one model per vector index. Provider: "voyage" or "google".
    EMBEDDING_PROVIDER: str = "voyage"
    VOYAGE_API_KEY: str = ""
    EMBEDDING_MODEL: str = "voyage-3"          # Voyage embedding model
    GOOGLE_EMBEDDING_MODEL: str = "gemini-embedding-001"  # Google embedding model
    EMBEDDING_DIM: int = 1024

    # Retrieval tuning
    RAG_TOP_K: int = 5
    RAG_RELEVANCE_FLOOR: float = 0.5
    # HNSW search breadth. pgvector's default (40) collapses recall when the
    # corpus holds many near-identical vectors (e.g. repeated test alerts): the
    # greedy graph walk gets trapped in that cluster and misses the true nearest
    # neighbours. Must be >= the query LIMIT; higher = better recall, slower.
    RAG_HNSW_EF_SEARCH: int = 200

    # Future: Auth, etc.
    # SECRET_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()
