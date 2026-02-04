from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Audio Recording API"
    CORS_ALLOWED_ORIGINS: list[str] 
    
    # Storage settings
    STORAGE_PATH: str = "uploads"

    # Google Drive OAuth 2.0 settings
    GDRIVE_OAUTH_CLIENT_SECRET_FILE: str = "client_secret.json"
    GDRIVE_OAUTH_TOKEN_FILE: str = "token.json"
    GDRIVE_FOLDER_ID: str 

    # NeonDB settings
    NEONDB_CONNECTION_STRING: str

    # JWT Secret Key
    SECRET_KEY: str

    model_config = {"env_file": ".env"}

settings = Settings()
