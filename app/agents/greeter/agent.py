"""Greeter agent: posts a message to the configured Telegram channel."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import Field

from app.agents.base import AgentContext, AgentInput, BaseAgent
from app.integrations.telegram import TelegramBotClient


class GreeterInput(AgentInput):
    text: str = Field(default="Hello 👋", min_length=1, max_length=4096)
    silent: bool = False


class GreeterAgent(BaseAgent[GreeterInput]):
    name: ClassVar[str] = "greeter"
    description: ClassVar[str] = "Sends a hello message to the Telegram channel."
    Input: ClassVar[type[AgentInput]] = GreeterInput

    def __init__(self, telegram: TelegramBotClient, chat_id: int | str) -> None:
        self._telegram = telegram
        self._chat_id = chat_id

    async def execute(self, params: GreeterInput, ctx: AgentContext) -> dict[str, Any]:
        message = await self._telegram.send_message(
            self._chat_id, params.text, disable_notification=params.silent or None
        )
        return {
            "chat_id": message["chat"]["id"],
            "message_id": message["message_id"],
            "text": message.get("text", params.text),
        }
