"""Declarative workflow definitions. Add new workflows to WORKFLOWS."""

from __future__ import annotations

from app.workflows.engine import Workflow, WorkflowStep

CHANNEL_HELLO = Workflow(
    name="channel_hello",
    description="Connectivity check: the greeter agent says hello in the channel.",
    steps=(WorkflowStep(agent="greeter"),),
)

WORKFLOWS: list[Workflow] = [CHANNEL_HELLO]
