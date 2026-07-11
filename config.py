from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


PROJECT_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    APP_NAME: str = "Audio Recording API"
    CORS_ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]
    
    # Storage settings
    STORAGE_PATH: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = Field(default=50, gt=0)

    # Google Drive OAuth 2.0 settings
    GDRIVE_OAUTH_CLIENT_SECRET_FILE: str = "client_secret.json"
    GDRIVE_OAUTH_TOKEN_FILE: str = "token.json"
    GDRIVE_FOLDER_ID: str = ""

    # NeonDB settings
    NEONDB_CONNECTION_STRING: str

    # Docker PostgreSQL settings (optional, used by docker-compose)
    POSTGRES_USER: str | None = None
    POSTGRES_PASSWORD: str | None = None
    POSTGRES_DB: str | None = None

    # JWT Secret Key
    SECRET_KEY: str = Field(min_length=32)

    # Email settings (SMTP)
    SMTP_HOST: str = ""
    SMTP_PORT: int = Field(default=587, gt=0, le=65535)
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM_EMAIL: str = ""
    SMTP_TIMEOUT_SECONDS: int = Field(default=15, gt=0, le=120)
    FRONTEND_BASE_URL: str = "https://dataset-1239123123.web.app"
    PROJECT_NAME: str = "Audio Recording API"

    # AWS S3 settings
    S3_BUCKET_NAME: str = Field(min_length=3)
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "sa-east-1"


    model_config = {
        "env_file": PROJECT_DIR / ".env",
        "env_file_encoding": "utf-8",
    }

settings = Settings()
