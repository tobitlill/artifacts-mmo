from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(PROJECT_ROOT / ".env"), extra="ignore")

    api_token: str
    character_name: str
    api_base_url: str = "https://api.artifactsmmo.com"

    ollama_host: str = "http://localhost:11434/v1"
    # Tactical runs every turn and must stay fast/resident — 5.2GB, comfortable on a 10GB card.
    tactical_model: str = "qwen3:8b"
    # Strategic runs rarely (goal selection only), so a one-time model-swap cost per trigger is
    # cheap to pay for meaningfully better reasoning. qwen3:14b (9.3GB q4_K_M) is the strongest
    # model that still fits a 10GB card on its own — tight (~0.7GB headroom for KV-cache/driver
    # overhead), so a sliver of it may spill to CPU offload, which is fine for an infrequent call.
    # Requires `ollama pull qwen3:14b` first. Fall back to "qwen3:8b" here if 14b proves too slow.
    strategic_model: str = "qwen3:8b"
    strategic_model_use_thinking: bool = True

    log_level: str = "INFO"

    min_request_interval_seconds: float = 0.25
    full_state_refresh_every: int = 20
    max_consecutive_loop_errors: int = 5

    @property
    def memory_db_path(self) -> Path:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        return DATA_DIR / "memory.db"


def load_settings() -> Settings:
    return Settings()
