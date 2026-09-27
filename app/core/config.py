"""Typed application settings loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", env_ignore_empty=True
    )

    app_name: str = "telegram-agents"
    log_level: str = "INFO"

    telegram_bot_token: SecretStr
    telegram_api_base: str = "https://api.telegram.org"
    telegram_timeout: float = 15.0
    telegram_channel_name: str = ""
    telegram_channel_id: int | None = Field(default=None)

    @property
    def telegram_channel_target(self) -> int | str:
        """Chat identifier accepted by the Bot API.

        Private channels only work with the numeric id. A public channel can be
        addressed as ``@username``.
        """
        if self.telegram_channel_id is not None:
            return self.telegram_channel_id
        if self.telegram_channel_name:
            name = self.telegram_channel_name
            return name if name.startswith("@") else f"@{name}"
        raise ValueError("Set TELEGRAM_CHANNEL_ID (private channel) or TELEGRAM_CHANNEL_NAME (public).")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
