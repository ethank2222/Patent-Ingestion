import os
from dataclasses import dataclass


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


@dataclass(frozen=True)
class Settings:
    app_env: str
    app_debug: bool
    secret_key: str
    database_url: str
    redis_url: str
    rq_async: bool
    uspto_api_base: str
    uspto_api_key: str
    uspto_timeout_seconds: int
    use_sample_data_on_failure: bool
    default_ingest_days: int
    default_ingest_limit: int
    openai_api_key: str
    openai_summary_model: str
    prompt_version: str
    summary_max_output_tokens: int
    summary_source_char_limit: int
    admin_api_token: str


class Config:
    @staticmethod
    def load() -> Settings:
        raw_db = os.getenv("DATABASE_URL", "sqlite:///patents.db")
        return Settings(
            app_env=os.getenv("APP_ENV", "development"),
            app_debug=_as_bool(os.getenv("APP_DEBUG"), default=True),
            secret_key=os.getenv("SECRET_KEY", "dev-secret-change-me"),
            database_url=_normalize_database_url(raw_db),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            rq_async=_as_bool(os.getenv("RQ_ASYNC"), default=True),
            uspto_api_base=os.getenv("USPTO_API_BASE", "https://api.uspto.gov/api/v1"),
            uspto_api_key=os.getenv("USPTO_API_KEY", ""),
            uspto_timeout_seconds=int(os.getenv("USPTO_TIMEOUT_SECONDS", "30")),
            use_sample_data_on_failure=_as_bool(os.getenv("USE_SAMPLE_DATA_ON_FAILURE"), default=True),
            default_ingest_days=int(os.getenv("DEFAULT_INGEST_DAYS", "30")),
            default_ingest_limit=int(os.getenv("DEFAULT_INGEST_LIMIT", "500")),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_summary_model=os.getenv("OPENAI_SUMMARY_MODEL", "gpt-4.1-mini"),
            prompt_version=os.getenv("PROMPT_VERSION", "summary-v2"),
            summary_max_output_tokens=int(os.getenv("SUMMARY_MAX_OUTPUT_TOKENS", "500")),
            summary_source_char_limit=int(os.getenv("SUMMARY_SOURCE_CHAR_LIMIT", "3500")),
            admin_api_token=os.getenv("ADMIN_API_TOKEN", "change-me"),
        )
