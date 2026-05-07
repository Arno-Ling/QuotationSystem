"""
StateStore — Protocol for workflow runtime state persistence.

The naive implementation (adapters/sql_state_store.py) reads/writes the
`workflow_runs.context_json` JSON column. The future Harness
implementation writes `workflow_instances.context_json` with
incremental diff support.
"""
from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID


class StateStore(Protocol):
    """Key-value state per workflow run."""

    async def put(self, run_id: UUID, key: str, value: Any) -> None:
        """Set or overwrite a key in the run's context."""
        ...

    async def get(self, run_id: UUID, key: str) -> Any:
        """Read a key from the run's context. Returns None if absent."""
        ...

    async def snapshot(self, run_id: UUID) -> dict[str, Any]:
        """Return the full context as a dict (deep-copied)."""
        ...
