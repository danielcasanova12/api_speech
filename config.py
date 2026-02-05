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

    # Email settings (SMTP)
    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_USER: str
    SMTP_PASSWORD: str
    EMAILS_FROM_EMAIL: str
    PROJECT_NAME: str = "Audio Recording API"

    # AWS S3 settings
    S3_BUCKET_NAME: str = "your_s3_bucket_name"
    AWS_ACCESS_KEY_ID: str = "your_aws_access_key_id"
    AWS_SECRET_ACCESS_KEY: str = "your_aws_secret_access_key"
    AWS_REGION: str = "your_aws_region"

    model_config = {"env_file": ".env"}

settings = Settings()
