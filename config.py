from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"), extra="ignore"
    )

    api_token: str
    character_name: str

    log_level: str = "INFO"


def load_settings() -> Settings:
    return Settings()
