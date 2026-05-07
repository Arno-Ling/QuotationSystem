"""
WorkflowContext helpers: serialization and mutation.

The Pydantic model is defined in `models.py`; this module provides
higher-level helpers used by the executor.

Requirements: REQ-022
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from .models import NodeStatus, WorkflowContext


def create_initial_context(
    instance_id: UUID,
    workflow_key: str,
    version: int,
    inputs: dict[str, Any],
) -> WorkflowContext:
    """Create a fresh WorkflowContext for a new instance."""
    now = datetime.utcnow()
    return WorkflowContext(
        instance_id=instance_id,
        workflow_key=workflow_key,
        version=version,
        inputs=dict(inputs),
        outputs={},
        variables={},
        node_statuses={},
        node_attempts={},
        current_nodes=[],
        created_at=now,
        updated_at=now,
    )


def context_diff(
    old: Optional[WorkflowContext], new: WorkflowContext,
) -> dict[str, Any]:
    """Compute a shallow diff between two contexts (for monitoring/debug).

    This is informational only; persistence currently flushes the full
    context (Pydantic `model_dump_json`). A future optimization could
    write only changed fields (REQ-022 "incremental diff for large
    contexts").
    """
    if old is None:
        return {"kind": "initial"}

    diff: dict[str, Any] = {}
    # Output keys added since old
    new_outputs = set(new.outputs) - set(old.outputs)
    if new_outputs:
        diff["new_outputs"] = sorted(new_outputs)

    # Node status changes
    status_changes: dict[str, tuple[Optional[str], str]] = {}
    all_nodes = set(old.node_statuses) | set(new.node_statuses)
    for nid in all_nodes:
        old_s = old.node_statuses.get(nid)
        new_s = new.node_statuses.get(nid)
        if old_s != new_s:
            status_changes[nid] = (
                old_s.value if old_s else None,
                new_s.value if new_s else None,  # type: ignore[union-attr]
            )
    if status_changes:
        diff["status_changes"] = status_changes

    return diff
