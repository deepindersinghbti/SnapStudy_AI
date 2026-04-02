from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SnapStudy API"
    app_version: str = "0.1.0"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"

    secret_key: str = "change-this-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    database_url: str = "sqlite:///./snapstudy.db"
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 20
    pdf_max_pages: int = 20
    min_text_length: int = 50
    tesseract_cmd: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    gemini_api_key: str = ""
    ai_model: str = "gemini-flash-latest"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
