"""
DbApprovalGateway — naive implementation of ApprovalGateway Protocol (skeleton).

Phase 1: implements create_task / list_pending / get_history (read + insert).
Phase 3: `take_action` (APPROVE / REJECT) implemented in services/approval_service.py.

Future Harness replacement:
    HarnessApprovalGateway — delegates to harness.workflow.approval.ApprovalManager;
    uses asyncio.Event to suspend/resume workflow coroutines instead of
    the current "callback after commit" approach.

DB schema is identical (migration 002), so this swap is zero-SQL.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Callable, Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from interfaces.approval_gateway import (
    ApprovalAction,
    AssigneeSpec,
    AssigneeType,
)

logger = logging.getLogger(__name__)


def _uuid_bytes(u: UUID) -> bytes:
    return u.bytes


def _bytes_uuid(b: bytes) -> UUID:
    return UUID(bytes=b)


class DbApprovalGateway:
    """Reads/writes workflow_approval_tasks / _records / workflow_state_events.

    Phase 1 skeleton: only create_task + list_pending + get_history.
    take_action is NotImplementedError at this layer; Phase 3's
    ApprovalService extends this class to implement it.
    """

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
    ) -> None:
        self._sf = session_factory

    # -----------------------------------------------------------------
    # Task creation (Phase 1)
    # -----------------------------------------------------------------

    async def create_task(
        self,
        kind: str,
        payload: dict[str, Any],
        assignees: list[AssigneeSpec],
        *,
        run_id: Optional[UUID] = None,
        due_at: Optional[datetime] = None,
    ) -> UUID:
        """Create a pending approval task in a single transaction.

        - Inserts one row per assignee into workflow_approval_tasks
        - Inserts one 'submit' row into workflow_approval_records (actor='system')
        - Inserts one 'approval_task_created' event into workflow_state_events
        - Uses `kind` as node_id to route resume callbacks later
        """
        if not assignees:
            raise ValueError("assignees must be non-empty")

        task_id = uuid4()
        task_id_bytes = _uuid_bytes(task_id)
        # If no run_id given, use task_id as surrogate instance_id for FK-free MVP
        instance_id_bytes = _uuid_bytes(run_id) if run_id else task_id_bytes
        now = datetime.utcnow()
        payload_json = json.dumps(payload, ensure_ascii=False, default=str)

        async with self._sf() as session:
            async with session.begin():
                # 1. INSERT tasks (one per assignee)
                for a in assignees:
                    await session.execute(
                        text("""
                            INSERT INTO workflow_approval_tasks
                                (instance_id, node_id, assignee_type, assignee_id,
                                 status, due_at)
                            VALUES (:iid, :nid, :atype, :aid, 'pending', :due)
                        """),
                        {
                            "iid": instance_id_bytes,
                            "nid": kind,
                            "atype": a.type.value,
                            "aid": a.identifier,
                            "due": due_at,
                        },
                    )

                # 2. INSERT initial SUBMIT record (by system)
                record_id = uuid4()
                first_assignee = assignees[0]
                await session.execute(
                    text("""
                        INSERT INTO workflow_approval_records
                            (id, instance_id, node_id, action, actor_id,
                             assignee_type, assignee_id, comment,
                             metadata_json, created_at)
                        VALUES
                            (:rid, :iid, :nid, :act, 'system',
                             :atype, :aid, :cmt,
                             :meta, :now)
                    """),
                    {
                        "rid": _uuid_bytes(record_id),
                        "iid": instance_id_bytes,
                        "nid": kind,
                        "act": ApprovalAction.SUBMIT.value,
                        "atype": first_assignee.type.value,
                        "aid": first_assignee.identifier,
                        "cmt": f"Task created: kind={kind}",
                        "meta": json.dumps({
                            "task_id": str(task_id),
                            "payload": payload,
                            "assignees": [
                                {"type": a.type.value, "id": a.identifier}
                                for a in assignees
                            ],
                        }, ensure_ascii=False, default=str),
                        "now": now,
                    },
                )

                # 3. State event
                await session.execute(
                    text("""
                        INSERT INTO workflow_state_events
                            (instance_id, node_id, event_type, to_status,
                             payload_json, occurred_at)
                        VALUES
                            (:iid, :nid, 'approval_task_created', 'pending',
                             :payload, :now)
                    """),
                    {
                        "iid": instance_id_bytes,
                        "nid": kind,
                        "payload": payload_json,
                        "now": now,
                    },
                )

        logger.info(
            "Created approval task task_id=%s kind=%s assignees=%d",
            task_id, kind, len(assignees),
        )
        return task_id

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
        """Phase 1 skeleton — full logic in services/approval_service.py."""
        raise NotImplementedError(
            "take_action() is implemented by ApprovalService (Phase 3). "
            "This gateway is Phase-1 skeleton for task creation + queries only."
        )

    # -----------------------------------------------------------------
    # Read-only queries (Phase 1)
    # -----------------------------------------------------------------

    async def list_pending(
        self,
        assignee_type: AssigneeType,
        assignee_id: str,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> list[dict[str, Any]]:
        offset = max(0, (page - 1) * page_size)
        async with self._sf() as session:
            async with session.begin():
                result = await session.execute(
                    text("""
                        SELECT t.id, HEX(t.instance_id), t.node_id,
                               t.assignee_type, t.assignee_id,
                               t.status, t.due_at, t.created_at
                        FROM workflow_approval_tasks t
                        WHERE t.assignee_type = :atype
                          AND t.assignee_id = :aid
                          AND t.status = 'pending'
                        ORDER BY t.created_at DESC
                        LIMIT :lim OFFSET :off
                    """),
                    {
                        "atype": assignee_type.value, "aid": assignee_id,
                        "lim": page_size, "off": offset,
                    },
                )
                rows = result.fetchall()

        return [
            {
                "pk": r[0],
                "instance_id": r[1],
                "kind": r[2],              # node_id carries the business kind
                "assignee_type": r[3],
                "assignee_id": r[4],
                "status": r[5],
                "due_at": r[6].isoformat() if r[6] else None,
                "created_at": r[7].isoformat() if r[7] else None,
            }
            for r in rows
        ]

    async def get_history(self, task_id: UUID) -> list[dict[str, Any]]:
        """Return history by joining on the metadata task_id field.

        MVP: we stored task_id in metadata_json; query by instance_id
        (= task_id bytes when run_id was None) for O(log n) via index.
        """
        task_id_bytes = _uuid_bytes(task_id)
        async with self._sf() as session:
            async with session.begin():
                result = await session.execute(
                    text("""
                        SELECT HEX(id), HEX(instance_id), node_id,
                               action, actor_id, assignee_type, assignee_id,
                               comment, delegate_to, metadata_json, created_at
                        FROM workflow_approval_records
                        WHERE instance_id = :iid
                        ORDER BY created_at ASC, id ASC
                    """),
                    {"iid": task_id_bytes},
                )
                rows = result.fetchall()

        return [
            {
                "record_id": r[0],
                "instance_id": r[1],
                "kind": r[2],
                "action": r[3],
                "actor_id": r[4],
                "assignee_type": r[5],
                "assignee_id": r[6],
                "comment": r[7],
                "delegate_to": r[8],
                "metadata": (json.loads(r[9]) if isinstance(r[9], str) and r[9] else r[9]) or {},
                "created_at": r[10].isoformat() if r[10] else None,
            }
            for r in rows
        ]
