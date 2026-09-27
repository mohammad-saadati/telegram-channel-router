"""Composition root: the only place that wires concrete dependencies together.

Both the FastAPI app and the CLI build a Container, so agents behave identically
regardless of entry point.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agents import AgentRegistry
from app.agents.greeter import GreeterAgent
from app.core.config import Settings
from app.integrations.telegram import TelegramBotClient
from app.workflows import WorkflowEngine
from app.workflows.definitions import WORKFLOWS


@dataclass
class Container:
    settings: Settings
    telegram: TelegramBotClient
    agents: AgentRegistry
    workflows: WorkflowEngine

    async def aclose(self) -> None:
        await self.telegram.aclose()


def build_agents(settings: Settings, telegram: TelegramBotClient) -> AgentRegistry:
    registry = AgentRegistry()
    registry.register(GreeterAgent(telegram, chat_id=settings.telegram_channel_target))
    return registry


def build_container(settings: Settings) -> Container:
    telegram = TelegramBotClient(
        settings.telegram_bot_token.get_secret_value(),
        api_base=settings.telegram_api_base,
        timeout=settings.telegram_timeout,
    )
    agents = build_agents(settings, telegram)
    return Container(
        settings=settings,
        telegram=telegram,
        agents=agents,
        workflows=WorkflowEngine(agents, WORKFLOWS),
    )
