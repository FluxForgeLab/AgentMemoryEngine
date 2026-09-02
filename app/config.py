from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from storage import DEFAULT_DB_PATH, SERVICE_TABLE_NAME

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    memory_db_path: str = DEFAULT_DB_PATH
    memory_table_name: str = SERVICE_TABLE_NAME

    embedding_provider: str = "qwen"
    reranker_provider: str = "qwen"

    embedding_dim: int = 1024

    llm_provider: str = "deepseek"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""

    log_dir: str = ""
    log_disabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("AME_LOG_DISABLED", "LOG_DISABLED", "log_disabled"),
    )

    model_config = SettingsConfigDict(
        env_file=_PROJECT_ROOT / ".env",
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
