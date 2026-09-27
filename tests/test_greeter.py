from __future__ import annotations

import asyncio
from typing import Any

from app.agents import AgentRegistry
from app.agents.greeter import GreeterAgent
from app.integrations.telegram import TelegramAPIError
from app.workflows import WorkflowEngine
from app.workflows.definitions import WORKFLOWS


class FakeTelegram:
    def __init__(self, fail: bool = False) -> None:
        self.sent: list[tuple[Any, str]] = []
        self.fail = fail

    async def send_message(self, chat_id: Any, text: str, **_: Any) -> dict[str, Any]:
        if self.fail:
            raise TelegramAPIError("sendMessage", "chat not found", 400)
        self.sent.append((chat_id, text))
        return {"message_id": 1, "chat": {"id": chat_id}, "text": text}


def test_greeter_sends_hello() -> None:
    telegram = FakeTelegram()
    result = asyncio.run(GreeterAgent(telegram, chat_id=-100123).run())  # type: ignore[arg-type]
    assert result.success
    assert telegram.sent == [(-100123, "Hello 👋")]
    assert result.output["message_id"] == 1


def test_greeter_reports_api_error() -> None:
    result = asyncio.run(GreeterAgent(FakeTelegram(fail=True), chat_id=1).run())  # type: ignore[arg-type]
    assert not result.success
    assert "chat not found" in (result.error or "")


def test_greeter_rejects_empty_text() -> None:
    result = asyncio.run(GreeterAgent(FakeTelegram(), chat_id=1).run({"text": ""}))  # type: ignore[arg-type]
    assert not result.success


def test_channel_hello_workflow() -> None:
    registry = AgentRegistry()
    registry.register(GreeterAgent(FakeTelegram(), chat_id=1))  # type: ignore[arg-type]
    run = asyncio.run(WorkflowEngine(registry, WORKFLOWS).run("channel_hello"))
    assert run.success
    assert [s.agent for s in run.steps] == ["greeter"]
