"""Application settings loaded from .env and config/trade_series_config.yml."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "trade_series_config.yml"
SQL_DIR = PROJECT_ROOT / "sql"
DOCS_DIR = PROJECT_ROOT / "docs"
REPORTS_DIR = PROJECT_ROOT / "reports"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # GUS DBW & NBP APIs
    gus_dbw_api_key: str = Field(default="", alias="GUS_DBW_API_KEY")
    gus_dbw_base_url: str = Field(
        default="https://api-dbw.stat.gov.pl/api/1.1.0",
        alias="GUS_DBW_BASE_URL",
    )
    nbp_api_base_url: str = Field(
        default="https://api.nbp.pl/api/exchangerates",
        alias="NBP_API_BASE_URL",
    )

    # Supabase PostgreSQL 16
    database_url: str = Field(default="", alias="DATABASE_URL")

    # Supabase S3-Compatible Storage (Bronze layer)
    supabase_s3_endpoint: str = Field(default="", alias="SUPABASE_S3_ENDPOINT")
    supabase_s3_region: str = Field(default="eu-central-1", alias="SUPABASE_S3_REGION")
    supabase_s3_access_key_id: str = Field(default="", alias="SUPABASE_S3_ACCESS_KEY_ID")
    supabase_s3_secret_access_key: str = Field(default="", alias="SUPABASE_S3_SECRET_ACCESS_KEY")
    supabase_storage_bucket: str = Field(default="gus-bronze", alias="SUPABASE_STORAGE_BUCKET")

    # Optional Power Automate Webhook
    pa_webhook_url: str = Field(default="", alias="PA_WEBHOOK_URL")

    @property
    def sqlalchemy_url(self) -> str:
        """Ensure SQLAlchemy uses the psycopg v3 driver."""
        url = self.database_url.strip()
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    @property
    def psycopg_dsn(self) -> str:
        """Return a DSN compatible with direct psycopg.connect()."""
        url = self.database_url.strip()
        if url.startswith("postgresql+psycopg://"):
            return url.replace("postgresql+psycopg://", "postgresql://", 1)
        return url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def load_trade_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)

