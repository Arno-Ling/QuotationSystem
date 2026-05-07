"""
ApprovalGateway — Protocol for the approval subsystem.

The naive implementation (adapters/db_approval_gateway.py) reads and
writes workflow_approval_tasks / _records / workflow_state_events
directly. The future Harness implementation delegates to
`harness.workflow.approval.ApprovalManager`.

Reuses AssigneeType / ApprovalAction enums from backend/harness/workflow/models.py
to guarantee schema-level compatibility when migrating.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Protocol
from uuid import UUID

# Reuse enums from harness/workflow/models.py — the only cross-spec import
# allowed (guaranteed by Phase 1 constraint).
from harness.workflow.models import ApprovalAction, AssigneeType


@dataclass
class AssigneeSpec:
    """Who can act on an approval task.

    - `USER`           : single user id
    - `SHARED_ACCOUNT` : multiple real users behind one account
    - `ROLE`           : all members of a role
    """
    type: AssigneeType
    identifier: str
    display_name: Optional[str] = None


class ApprovalGateway(Protocol):
    """Contract for creating and acting on approval tasks."""

    async def create_task(
        self,
        kind: str,
        payload: dict[str, Any],
        assignees: list[AssigneeSpec],
        *,
        run_id: Optional[UUID] = None,
        due_at: Optional[datetime] = None,
    ) -> UUID:
        """Create a new pending approval task.

        A single `task` row is created per assignee, all sharing the same
        `task_id` namespace (a logical task with multiple assignees).
        Returns the logical task_id.
        """
        ...

    async def take_action(
        self,
        task_id: UUID,
        action: ApprovalAction,
        actor_id: str,
        *,
        comment: Optional[str] = None,
        delegate_to: Optional[str] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Execute an approval action. Raises:
        - WorkflowPermissionError if actor is not an authorized assignee
        - IllegalActionError if action is not allowed in current state
        """
        ...

    async def list_pending(
        self,
        assignee_type: AssigneeType,
        assignee_id: str,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> list[dict[str, Any]]:
        """List pending tasks assigned to (type, id). Paginated."""
        ...

    async def get_history(self, task_id: UUID) -> list[dict[str, Any]]:
        """Return append-only approval record chain, oldest first."""
        ...


__all__ = [
    "ApprovalAction",
    "AssigneeSpec",
    "AssigneeType",
    "ApprovalGateway",
]
