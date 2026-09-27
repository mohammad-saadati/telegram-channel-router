"""Thin async client for the Telegram Bot API.

Agents depend on this class (or a fake with the same methods in tests), never on
httpx directly, so the transport can be swapped without touching agent code.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class TelegramAPIError(RuntimeError):
    def __init__(self, method: str, description: str, error_code: int | None = None) -> None:
        super().__init__(f"{method} failed ({error_code}): {description}")
        self.method = method
        self.description = description
        self.error_code = error_code


class TelegramBotClient:
    def __init__(
        self,
        token: str,
        *,
        api_base: str = "https://api.telegram.org",
        timeout: float = 15.0,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = f"{api_base.rstrip('/')}/bot{token}"
        self._http = http or httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _call(self, method: str, **params: Any) -> Any:
        payload = {k: v for k, v in params.items() if v is not None}
        try:
            response = await self._http.post(f"{self._base_url}/{method}", json=payload)
        except httpx.HTTPError as exc:
            # Never include the URL: it contains the bot token.
            raise TelegramAPIError(method, type(exc).__name__) from None
        data = response.json()
        if not data.get("ok"):
            raise TelegramAPIError(method, data.get("description", "unknown error"), data.get("error_code"))
        return data["result"]

    async def get_me(self) -> dict[str, Any]:
        return await self._call("getMe")

    async def get_chat(self, chat_id: int | str) -> dict[str, Any]:
        return await self._call("getChat", chat_id=chat_id)

    async def get_updates(
        self,
        offset: int | None = None,
        timeout: int = 0,
        allowed_updates: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        return await self._call("getUpdates", offset=offset, timeout=timeout, allowed_updates=allowed_updates)

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        *,
        parse_mode: str | None = None,
        disable_notification: bool | None = None,
    ) -> dict[str, Any]:
        return await self._call(
            "sendMessage",
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            disable_notification=disable_notification,
        )
