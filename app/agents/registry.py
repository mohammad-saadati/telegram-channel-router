"""Lookup table of agent instances by name."""

from __future__ import annotations

from app.agents.base import BaseAgent


class AgentNotFoundError(KeyError):
    pass


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        if agent.name in self._agents:
            raise ValueError(f"Agent '{agent.name}' is already registered")
        self._agents[agent.name] = agent

    def get(self, name: str) -> BaseAgent:
        try:
            return self._agents[name]
        except KeyError:
            raise AgentNotFoundError(name) from None

    def all(self) -> list[BaseAgent]:
        return list(self._agents.values())
