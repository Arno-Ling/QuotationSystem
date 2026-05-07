"""
WorkflowEngine — Protocol for workflow orchestration.

The naive implementation (adapters/function_workflow_engine.py) treats
each workflow as an `async def` Python function. The future Harness
implementation dispatches to a DAG executor.
"""
from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID


class WorkflowEngine(Protocol):
    """Contract for workflow start/resume/status."""

    async def start(
        self,
        workflow_key: str,
        inputs: dict[str, Any],
        *,
        trigger_source: str = "api",
        trigger_user: str | None = None,
    ) -> UUID:
        """Create and start a workflow run. Returns run_id (UUID)."""
        ...

    async def resume(self, run_id: UUID, payload: dict[str, Any]) -> None:
        """Continue a suspended workflow after an external event.

        The engine looks up `workflow_runs.next_step` to decide which
        callable to invoke.
        """
        ...

    async def get_status(self, run_id: UUID) -> dict[str, Any]:
        """Return a JSON-friendly status snapshot."""
        ...
