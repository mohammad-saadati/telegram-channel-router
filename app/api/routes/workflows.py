from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.deps import ContainerDep
from app.workflows import WorkflowNotFoundError, WorkflowRun

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("")
async def list_workflows(container: ContainerDep) -> list[dict[str, Any]]:
    return [
        {"name": wf.name, "description": wf.description, "steps": [s.agent for s in wf.steps]}
        for wf in container.workflows.all()
    ]


@router.post("/{name}/run")
async def run_workflow(name: str, container: ContainerDep) -> WorkflowRun:
    try:
        return await container.workflows.run(name)
    except WorkflowNotFoundError:
        raise HTTPException(status_code=404, detail=f"Unknown workflow '{name}'") from None
