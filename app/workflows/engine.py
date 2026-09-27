"""Workflow = ordered list of agent steps sharing one AgentContext.

Each step's output is stored in ``ctx.data[step.key]`` so later agents can read
what earlier agents produced. Execution stops at the first failed step unless the
step sets ``continue_on_error``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from app.agents import AgentContext, AgentRegistry, AgentResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkflowStep:
    agent: str
    params: dict[str, Any] = field(default_factory=dict)
    key: str | None = None  # name in ctx.data; defaults to the agent name
    continue_on_error: bool = False


@dataclass(frozen=True)
class Workflow:
    name: str
    steps: tuple[WorkflowStep, ...]
    description: str = ""


class WorkflowNotFoundError(KeyError):
    pass


class WorkflowRun(BaseModel):
    workflow: str
    run_id: str
    success: bool
    steps: list[AgentResult]


class WorkflowEngine:
    def __init__(self, agents: AgentRegistry, workflows: list[Workflow]) -> None:
        self._agents = agents
        self._workflows = {wf.name: wf for wf in workflows}
        for wf in workflows:  # fail fast on typos at startup, not at run time
            for step in wf.steps:
                agents.get(step.agent)

    def get(self, name: str) -> Workflow:
        try:
            return self._workflows[name]
        except KeyError:
            raise WorkflowNotFoundError(name) from None

    def all(self) -> list[Workflow]:
        return list(self._workflows.values())

    async def run(self, name: str, ctx: AgentContext | None = None) -> WorkflowRun:
        workflow = self.get(name)
        ctx = ctx or AgentContext()
        results: list[AgentResult] = []
        success = True
        for step in workflow.steps:
            result = await self._agents.get(step.agent).run(step.params, ctx)
            ctx.data[step.key or step.agent] = result.output
            results.append(result)
            if not result.success and not step.continue_on_error:
                success = False
                break
        logger.info("workflow=%s run_id=%s success=%s", name, ctx.run_id, success)
        return WorkflowRun(workflow=name, run_id=ctx.run_id, success=success, steps=results)
