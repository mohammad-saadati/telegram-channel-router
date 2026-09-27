"""Agent contract shared by every agent in the system.

An agent is a single, focused unit of work with:
- a unique ``name`` (used by the registry, API and workflows)
- a pydantic ``Input`` model (validated params; also documents the API)
- an async ``execute`` that returns a dict of outputs

Dependencies (API clients, settings, ...) are injected through ``__init__``.
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, Generic, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class AgentInput(BaseModel):
    """Base class for agent inputs. Subclass per agent."""


InputT = TypeVar("InputT", bound=AgentInput)


@dataclass
class AgentContext:
    """State shared across one run (a single agent call or a whole workflow)."""

    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    data: dict[str, Any] = field(default_factory=dict)


class AgentResult(BaseModel):
    agent: str
    success: bool
    output: dict[str, Any] = {}
    error: str | None = None


class BaseAgent(ABC, Generic[InputT]):
    name: ClassVar[str]
    description: ClassVar[str] = ""
    Input: ClassVar[type[AgentInput]] = AgentInput

    @abstractmethod
    async def execute(self, params: InputT, ctx: AgentContext) -> dict[str, Any]:
        """Do the work. Raise on failure; ``run`` turns exceptions into a failed result."""

    async def run(self, params: dict[str, Any] | None = None, ctx: AgentContext | None = None) -> AgentResult:
        ctx = ctx or AgentContext()
        try:
            parsed = self.Input.model_validate(params or {})
            output = await self.execute(parsed, ctx)  # type: ignore[arg-type]
        except Exception as exc:
            logger.exception("agent=%s run_id=%s failed", self.name, ctx.run_id)
            return AgentResult(agent=self.name, success=False, error=str(exc))
        logger.info("agent=%s run_id=%s succeeded", self.name, ctx.run_id)
        return AgentResult(agent=self.name, success=True, output=output)
