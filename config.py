from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Audio Recording API"
    CORS_ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "https://dataset-1239123123.web.app"]
    
    # Storage settings
    STORAGE_PATH: str = "uploads"

    # Google Drive OAuth 2.0 settings
    GDRIVE_OAUTH_CLIENT_SECRET_FILE: str = "client_secret.json"
    GDRIVE_OAUTH_TOKEN_FILE: str = "token.json"
    GDRIVE_FOLDER_ID: str = "your_google_drive_folder_id"

    model_config = {"env_file": ".env"}

settings = Settings()
