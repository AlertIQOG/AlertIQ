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

    # Notifications — Slack (Incoming Webhook)
    SLACK_WEBHOOK_URL: str = ""

    # Notifications — Email (SMTP). For Gmail: host=smtp.gmail.com, port=587, TLS on,
    # password = an App Password (requires 2FA on the account).
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""  # defaults to SMTP_USERNAME when empty
    SMTP_USE_TLS: bool = True
    EMAIL_DEFAULT_TO: str = ""  # fallback recipient for the test endpoint

    # Future: Auth, etc.
    # SECRET_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()
