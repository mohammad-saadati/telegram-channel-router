from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException

from app.agents import AgentNotFoundError, AgentResult
from app.api.deps import ContainerDep

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("")
async def list_agents(container: ContainerDep) -> list[dict[str, Any]]:
    return [
        {"name": a.name, "description": a.description, "input_schema": a.Input.model_json_schema()}
        for a in container.agents.all()
    ]


@router.post("/{name}/run")
async def run_agent(
    name: str, container: ContainerDep, params: dict[str, Any] = Body(default_factory=dict)
) -> AgentResult:
    try:
        agent = container.agents.get(name)
    except AgentNotFoundError:
        raise HTTPException(status_code=404, detail=f"Unknown agent '{name}'") from None
    return await agent.run(params)
