# app/config.py
import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
load_dotenv()  # This explicitly loads .env file

class Settings(BaseSettings):
    # Security settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "supersecret")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    PASSWORD_SALT: str = os.getenv("PASSWORD_SALT", "salt123")

    # Demo admin credentials
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")

    # AWS Configuration
    AWS_REGION: str = os.getenv("AWS_REGION", "eu-central-1")
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    
    # Bedrock Knowledge Base Configuration
    BEDROCK_KNOWLEDGE_BASE_ID: str = os.getenv("BEDROCK_KNOWLEDGE_BASE_ID", "")
    BEDROCK_GENERATION_MODEL: str = os.getenv("BEDROCK_GENERATION_MODEL", "anthropic.claude-3-sonnet-20240229-v1:0")
    BEDROCK_EMBEDDING_MODEL: str = os.getenv("BEDROCK_EMBEDDING_MODEL", "amazon.titan-embed-text-v1")
    BEDROCK_GUARDRAIL_ID: str = os.getenv("BEDROCK_GUARDRAIL_ID", "")
    BEDROCK_GUARDRAIL_VERSION: str = os.getenv("BEDROCK_GUARDRAIL_VERSION", "DRAFT")
    
    # Document Processing Configuration
    PDF_FOLDER_PATH: str = os.getenv("PDF_FOLDER_PATH", "./pdfs")
    S3_PREFIX: str = os.getenv("S3_PREFIX", "documents/")
    
    # Application Configuration
    APP_ENV: str = os.getenv("APP_ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes", "on")
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_RETENTION_DAYS: int = int(os.getenv("LOG_RETENTION_DAYS", "30"))
    
    # Legacy Bedrock config (keeping for backward compatibility)
    bedrock_region: str = os.getenv("AWS_REGION", "eu-central-1")
    bedrock_model_id: str = os.getenv("BEDROCK_GENERATION_MODEL", "anthropic.claude-v2")
    
    # LangSmith Configuration
    LANGCHAIN_TRACING_V2: bool = Field(default=True, env='LANGCHAIN_TRACING_V2')
    LANGCHAIN_ENDPOINT: str = Field(default="https://api.smith.langchain.com", env='LANGCHAIN_ENDPOINT')
    LANGCHAIN_API_KEY: Optional[str] = Field(default=None, env='LANGCHAIN_API_KEY')
    LANGCHAIN_PROJECT: str = Field(default="llm-app-1", env='LANGCHAIN_PROJECT')

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

settings = Settings()