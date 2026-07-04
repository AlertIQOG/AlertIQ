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

    # Auth
    SECRET_KEY: str = "dev-only-secret-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        # .env may carry vars for features on other branches (e.g. RAG) —
        # ignore anything this Settings class doesn't declare.
        extra="ignore",
    )


settings = Settings()
