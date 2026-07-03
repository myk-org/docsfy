from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    admin_key: str = ""  # Required — validated at startup
    ai_provider: str = ""
    ai_model: str = ""
    ai_cli_timeout: int = Field(default=60, gt=0)
    log_level: str = "INFO"
    data_dir: str = "/data"
    secure_cookies: bool = True  # Set to False for local HTTP dev
    max_concurrent_pages: int = Field(
        default=10,
        gt=0,
        description="Maximum number of AI CLI calls to run in parallel during page generation and validation",
    )
    vision_provider: str = ""
    vision_model: str = ""

    def get_env_overrides(self) -> dict[str, str]:
        """Return a dict mapping DB column names to env var names for settings with an active env var."""
        env_mappings: dict[str, tuple[str, str]] = {
            "ai_provider": ("AI_PROVIDER", "default_ai_provider"),
            "ai_model": ("AI_MODEL", "default_ai_model"),
            "ai_cli_timeout": ("AI_CLI_TIMEOUT", "ai_cli_timeout"),
            "max_concurrent_pages": ("MAX_CONCURRENT_PAGES", "max_concurrent_pages"),
            "vision_provider": ("VISION_PROVIDER", "vision_provider"),
            "vision_model": ("VISION_MODEL", "vision_model"),
        }
        return {
            db_col: env_var
            for _setting, (env_var, db_col) in env_mappings.items()
            if env_var in os.environ
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
