import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    PORT: int = 8000
    HOST: str = "127.0.0.1"
    MOCK_MODE: bool = True
    DATABASE_URL: str = "sqlite:///./leadvoice.db"
    
    # API credentials
    RETELL_API_KEY: str = Field(default="")
    RETELL_AGENT_ID: str = Field(default="")
    GROQ_API_KEY: str = Field(default="")
    WHATSAPP_ACCESS_TOKEN: str = Field(default="")
    WHATSAPP_PHONE_NUMBER_ID: str = Field(default="")
    WHATSAPP_API_VERSION: str = Field(default="v18.0")
    WHATSAPP_RECIPIENT_PHONE: str = Field(default="")
    
    # Telegram credentials
    MESSAGING_PROVIDER: str = Field(default="telegram")
    TELEGRAM_BOT_TOKEN: str = Field(default="")
    TELEGRAM_CHAT_ID: str = Field(default="")
    
    # Voice credentials & settings
    VOICE_PROVIDER: str = Field(default="mock")

    # Attachments
    RESUME_FILE_PATH: str = Field(default="")
    ARCHITECTURE_IMAGE_PATH: str = Field(default="")

    PUBLIC_BASE_URL: str = "http://localhost:8000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate settings
settings = Settings()
