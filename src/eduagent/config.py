"""Application settings, loaded from environment variables and `.env`."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

WHAT_IT_DOES = (
    "Loads the app's settings (models, routing mode, keys, folders) from the environment and `.env`, and works out which routing mode is really in effect."
)

RoutingMode = Literal["split", "all_gemini", "all_qwen"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-flash-latest"
    gemini_daily_limit: int = 250
    qwen_model: str = "qwen3:4b-instruct"
    embed_model: str = "nomic-embed-text"
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_use_gpu: bool = False
    qwen_timeout_s: float = Field(default=240.0, gt=0)
    qwen_num_ctx: int = Field(default=8192, ge=2048)
    routing_mode: RoutingMode = "split"
    data_dir: Path = Path("data")
    chroma_port: int = Field(default=8001, ge=1, le=65535)
    hybrid_alpha: float = Field(default=0.6, ge=0, le=1)
    rerank_enabled: bool = True
    search_results: int = Field(default=10, ge=1)
    search_results_qwen: int = Field(default=6, ge=1)
    search_module_share: float = Field(default=0.7, ge=0, le=1)
    formula_enrichment: bool = True
    ingest_threads: int = Field(default=4, ge=1)
    models_dir: Path = Path("data/models")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def effective_routing_mode(self) -> RoutingMode:
        """All-Qwen when there is no usable Gemini key, else the configured mode."""
        key = self.gemini_api_key
        if key is None or not key.get_secret_value().strip():
            return "all_qwen"
        return self.routing_mode

    @property
    def sources_dir(self) -> Path:
        return self.data_dir / "sources"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "study.db"

    @property
    def sessions_db_url(self) -> str:
        return f"sqlite+aiosqlite:///{(self.data_dir / 'sessions.db').as_posix()}"
