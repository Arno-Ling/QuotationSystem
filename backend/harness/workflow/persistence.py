"""
PersistenceManager - MySQL persistence layer for the Workflow Engine.

All SQL uses %s parameterized queries (never string concatenation) to prevent
SQL injection. Reuses the connection pattern from backend/database/db_utils.py.

Responsibilities:
- Workflow definitions CRUD (save, load, deactivate)
- Workflow instances CRUD (create, load, status update, context flush)
- Node executions (save, update, list) with execution_id uniqueness
- Approval records & tasks (append-only, pending query, timeout scan)
- State events (append-only audit log)
- Lease-based mutual exclusion (try_acquire / renew / release)

Requirements: REQ-021, REQ-022, REQ-024, REQ-025, REQ-057
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Iterator, Optional
from uuid import UUID, uuid4

import pymysql
from pymysql.connections import Connection

from .errors import (
    DatabaseError,
    DefinitionNotFoundError,
    DuplicateDefinitionError,
    InstanceNotFoundError,
)
from .models import (
    ApprovalAction,
    ApprovalRecord,
    AssigneeSpec,
    AssigneeType,
    NodeStatus,
    NodeType,
    WorkflowContext,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _uuid_to_bytes(u: UUID) -> bytes:
    """Convert a UUID to 16-byte BINARY(16) representation."""
    return u.bytes


def _bytes_to_uuid(b: bytes) -> UUID:
    """Convert BINARY(16) back to UUID."""
    return UUID(bytes=b)


def _compute_spec_hash(spec_dict: dict[str, Any]) -> str:
    """Stable SHA-256 hash of the canonicalized workflow spec."""
    canonical = json.dumps(spec_dict, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# PersistenceManager
# ---------------------------------------------------------------------------

class PersistenceManager:
    """Single boundary for all MySQL access from the workflow engine."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ) -> None:
        """Initialize with explicit config or read from environment."""
        self._config = {
            "host": host or os.getenv("DB_HOST", "localhost"),
            "port": int(port or os.getenv("DB_PORT", "3306")),
            "user": user or os.getenv("DB_USER", "root"),
            "password": password if password is not None else os.getenv("DB_PASSWORD", ""),
            "database": database or os.getenv("DB_NAME", "mold_procurement"),
            "charset": "utf8mb4",
            "autocommit": False,
        }
        logger.info(
            "PersistenceManager initialized: %s@%s:%s/%s",
            self._config["user"], self._config["host"],
            self._config["port"], self._config["database"],
        )

    @contextmanager
    def _connect(self) -> Iterator[Connection]:
        """Context-managed connection with automatic close."""
        conn = None
        try:
            conn = pymysql.connect(**self._config)
            yield conn
        except pymysql.err.Error as e:
            raise DatabaseError(f"Database operation failed: {e}") from e
        finally:
            if conn is not None:
                conn.close()

    # =======================================================================
    # Workflow Definitions
    # =======================================================================

    def save_definition(self, definition: WorkflowDefinition) -> int:
        """Persist a workflow definition. Returns the new definition_id.

        Raises DuplicateDefinitionError if (key, version) already exists.
        """
        spec_dict = definition.model_dump(by_alias=True, mode="json")
        spec_hash = _compute_spec_hash(spec_dict)
        spec_json = json.dumps(spec_dict, ensure_ascii=False)

        sql = """
            INSERT INTO workflow_definitions
                (`key`, version, name, description, spec_json, spec_hash, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, 1)
        """

        with self._connect() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        sql,
                        (definition.key, definition.version, definition.name,
                         definition.description or "", spec_json, spec_hash),
                    )
                    definition_id = cur.lastrowid
                    conn.commit()
                    logger.info(
                        "Saved workflow definition: key=%s version=%s id=%s",
                        definition.key, definition.version, definition_id,
                    )
                    return definition_id
            except pymysql.err.IntegrityError as e:
                conn.rollback()
                # Unique constraint on (key, version)
                if "uk_key_version" in str(e) or "Duplicate entry" in str(e):
                    raise DuplicateDefinitionError(definition.key, definition.version) from e
                raise DatabaseError(f"Failed to save definition: {e}") from e

    def load_definition(self, definition_id: int) -> WorkflowDefinition:
        """Load a workflow definition by its numeric id."""
        sql = "SELECT spec_json FROM workflow_definitions WHERE id = %s"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (definition_id,))
                row = cur.fetchone()
                if row is None:
                    raise DefinitionNotFoundError(key=f"id={definition_id}")
                spec_json = row[0]
                spec_dict = json.loads(spec_json) if isinstance(spec_json, str) else spec_json
                return WorkflowDefinition.model_validate(spec_dict)

    def load_definition_by_key(
        self, key: str, version: Optional[int] = None
    ) -> tuple[int, WorkflowDefinition]:
        """Load a definition by key (and optional version).

        If version is None, returns the latest active version.
        Returns (definition_id, WorkflowDefinition).
        """
        if version is None:
            sql = """
                SELECT id, spec_json FROM workflow_definitions
                WHERE `key` = %s AND is_active = 1
                ORDER BY version DESC LIMIT 1
            """
            params: tuple[Any, ...] = (key,)
        else:
            sql = """
                SELECT id, spec_json FROM workflow_definitions
                WHERE `key` = %s AND version = %s
            """
            params = (key, version)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
                if row is None:
                    raise DefinitionNotFoundError(key=key, version=version)
                definition_id, spec_json = row
                spec_dict = json.loads(spec_json) if isinstance(spec_json, str) else spec_json
                return definition_id, WorkflowDefinition.model_validate(spec_dict)

    def deactivate_definition(self, definition_id: int) -> None:
        """Soft-delete (set is_active=0). Running instances are unaffected."""
        sql = "UPDATE workflow_definitions SET is_active = 0 WHERE id = %s"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (definition_id,))
                conn.commit()
                logger.info("Deactivated definition id=%s", definition_id)

    # =======================================================================
    # Workflow Instances
    # =======================================================================

    def create_instance(
        self,
        definition_id: int,
        workflow_key: str,
        version: int,
        inputs: dict[str, Any],
        context: WorkflowContext,
        *,
        trigger_source: str = "api",
        trigger_user: Optional[str] = None,
    ) -> UUID:
        """Create a new workflow instance. Returns the new instance UUID."""
        instance_id = context.instance_id
        now = datetime.utcnow()

        sql = """
            INSERT INTO workflow_instances
                (id, definition_id, workflow_key, version, status,
                 trigger_source, trigger_user, inputs_json, context_json,
                 current_nodes, started_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (_uuid_to_bytes(instance_id), definition_id, workflow_key, version,
                     WorkflowStatus.PENDING.value, trigger_source, trigger_user,
                     json.dumps(inputs, ensure_ascii=False, default=str),
                     context.model_dump_json(),
                     json.dumps([], ensure_ascii=False), now),
                )
                conn.commit()
                logger.info("Created instance %s (workflow=%s v%s)",
                            instance_id, workflow_key, version)
                return instance_id

    def load_instance(self, instance_id: UUID) -> WorkflowInstance:
        """Load a workflow instance by id."""
        sql = """
            SELECT id, definition_id, workflow_key, version, status,
                   trigger_source, trigger_user, error_message,
                   lease_owner, lease_expires_at,
                   started_at, ended_at, created_at, updated_at
            FROM workflow_instances WHERE id = %s
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (_uuid_to_bytes(instance_id),))
                row = cur.fetchone()
                if row is None:
                    raise InstanceNotFoundError(str(instance_id))
                return WorkflowInstance(
                    id=_bytes_to_uuid(row[0]),
                    definition_id=row[1],
                    workflow_key=row[2],
                    version=row[3],
                    status=WorkflowStatus(row[4]),
                    trigger_source=row[5],
                    trigger_user=row[6],
                    error_message=row[7],
                    lease_owner=row[8],
                    lease_expires_at=row[9],
                    started_at=row[10],
                    ended_at=row[11],
                    created_at=row[12],
                    updated_at=row[13],
                )

    def load_context(self, instance_id: UUID) -> WorkflowContext:
        """Load the WorkflowContext JSON snapshot for an instance."""
        sql = "SELECT context_json FROM workflow_instances WHERE id = %s"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (_uuid_to_bytes(instance_id),))
                row = cur.fetchone()
                if row is None:
                    raise InstanceNotFoundError(str(instance_id))
                return WorkflowContext.model_validate_json(row[0])

    def update_instance_status(
        self,
        instance_id: UUID,
        status: WorkflowStatus,
        *,
        error_message: Optional[str] = None,
        ended: bool = False,
    ) -> None:
        """Update an instance's status (and optionally ended_at)."""
        sql = """
            UPDATE workflow_instances
            SET status = %s,
                error_message = %s,
                ended_at = CASE WHEN %s THEN %s ELSE ended_at END
            WHERE id = %s
        """
        now = datetime.utcnow()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (status.value, error_message, ended, now,
                     _uuid_to_bytes(instance_id)),
                )
                conn.commit()

    def update_instance_context(
        self, instance_id: UUID, context: WorkflowContext,
    ) -> None:
        """Flush the full context to the instance row (REQ-022)."""
        sql = """
            UPDATE workflow_instances
            SET context_json = %s, current_nodes = %s
            WHERE id = %s
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (context.model_dump_json(),
                     json.dumps(context.current_nodes, ensure_ascii=False),
                     _uuid_to_bytes(instance_id)),
                )
                conn.commit()

    def find_resumable_instances(self) -> list[UUID]:
        """Find instances with lease expired/missing and non-terminal status."""
        sql = """
            SELECT id FROM workflow_instances
            WHERE status IN (%s, %s, %s)
              AND (lease_owner IS NULL OR lease_expires_at < %s)
        """
        now = datetime.utcnow()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (WorkflowStatus.RUNNING.value,
                     WorkflowStatus.WAITING_APPROVAL.value,
                     WorkflowStatus.SUSPENDED.value, now),
                )
                return [_bytes_to_uuid(row[0]) for row in cur.fetchall()]

    # =======================================================================
    # Lease management (REQ-025)
    # =======================================================================

    def try_acquire_lease(
        self, instance_id: UUID, owner: str, ttl_seconds: int = 60,
    ) -> bool:
        """Try to acquire a lease on the instance. Returns True on success."""
        sql = """
            UPDATE workflow_instances
            SET lease_owner = %s, lease_expires_at = %s
            WHERE id = %s
              AND (lease_owner IS NULL OR lease_expires_at < %s)
        """
        now = datetime.utcnow()
        expires = now + timedelta(seconds=ttl_seconds)
        with self._connect() as conn:
            with conn.cursor() as cur:
                affected = cur.execute(
                    sql,
                    (owner, expires, _uuid_to_bytes(instance_id), now),
                )
                conn.commit()
                return affected > 0

    def renew_lease(self, instance_id: UUID, owner: str, ttl_seconds: int = 60) -> bool:
        """Renew an existing lease (only the current owner can renew)."""
        sql = """
            UPDATE workflow_instances
            SET lease_expires_at = %s
            WHERE id = %s AND lease_owner = %s
        """
        expires = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        with self._connect() as conn:
            with conn.cursor() as cur:
                affected = cur.execute(
                    sql, (expires, _uuid_to_bytes(instance_id), owner),
                )
                conn.commit()
                return affected > 0

    def release_lease(self, instance_id: UUID, owner: str) -> bool:
        """Release a lease (only the owner can release)."""
        sql = """
            UPDATE workflow_instances
            SET lease_owner = NULL, lease_expires_at = NULL
            WHERE id = %s AND lease_owner = %s
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                affected = cur.execute(
                    sql, (_uuid_to_bytes(instance_id), owner),
                )
                conn.commit()
                return affected > 0

    # =======================================================================
    # Node executions (REQ-024)
    # =======================================================================

    def save_node_execution(
        self,
        instance_id: UUID,
        node_id: str,
        node_type: NodeType,
        execution_id: str,
        status: NodeStatus,
        *,
        attempt: int = 1,
        input_data: Optional[dict[str, Any]] = None,
        started_at: Optional[datetime] = None,
    ) -> bool:
        """Insert a new node execution row. Returns False on duplicate execution_id."""
        sql = """
            INSERT INTO workflow_node_executions
                (instance_id, node_id, node_type, attempt, status,
                 input_json, started_at, execution_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        started_at = started_at or datetime.utcnow()
        input_json = (json.dumps(input_data, ensure_ascii=False, default=str)
                      if input_data is not None else None)
        with self._connect() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        sql,
                        (_uuid_to_bytes(instance_id), node_id, node_type.value,
                         attempt, status.value, input_json, started_at, execution_id),
                    )
                    conn.commit()
                    return True
            except pymysql.err.IntegrityError:
                # Duplicate execution_id - another process already recorded this
                conn.rollback()
                return False

    def update_node_execution(
        self,
        execution_id: str,
        status: NodeStatus,
        *,
        output: Any = None,
        error: Optional[str] = None,
        ended_at: Optional[datetime] = None,
    ) -> None:
        """Finalize a node execution (set final status + output/error)."""
        ended_at = ended_at or datetime.utcnow()
        output_json = (json.dumps(output, ensure_ascii=False, default=str)
                       if output is not None else None)

        sql = """
            UPDATE workflow_node_executions
            SET status = %s,
                output_json = %s,
                error_message = %s,
                ended_at = %s,
                duration_ms = TIMESTAMPDIFF(MICROSECOND, started_at, %s) DIV 1000
            WHERE execution_id = %s
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (status.value, output_json, error, ended_at, ended_at,
                     execution_id),
                )
                conn.commit()

    # =======================================================================
    # Approval records & tasks (REQ-027, REQ-030, REQ-031)
    # =======================================================================

    def insert_approval_record(self, record: ApprovalRecord) -> None:
        """Insert an approval record (append-only, never update/delete)."""
        sql = """
            INSERT INTO workflow_approval_records
                (id, instance_id, node_id, action, actor_id,
                 assignee_type, assignee_id, comment, delegate_to, metadata_json,
                 created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (_uuid_to_bytes(record.id),
                     _uuid_to_bytes(record.instance_id),
                     record.node_id,
                     record.action.value,
                     record.actor_id,
                     record.assignee_snapshot.type.value,
                     record.assignee_snapshot.identifier,
                     record.comment,
                     record.delegate_to,
                     json.dumps(record.metadata, ensure_ascii=False, default=str),
                     record.created_at),
                )
                conn.commit()

    def upsert_approval_task(
        self,
        instance_id: UUID,
        node_id: str,
        assignee: AssigneeSpec,
        *,
        status: str = "pending",
        due_at: Optional[datetime] = None,
    ) -> None:
        """Create or reuse a pending approval task."""
        sql = """
            INSERT INTO workflow_approval_tasks
                (instance_id, node_id, assignee_type, assignee_id, status, due_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                status = VALUES(status),
                due_at = VALUES(due_at)
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (_uuid_to_bytes(instance_id), node_id,
                     assignee.type.value, assignee.identifier,
                     status, due_at),
                )
                conn.commit()

    def complete_approval_task(
        self,
        instance_id: UUID,
        node_id: str,
        action: ApprovalAction,
        actor_id: str,
    ) -> None:
        """Mark the approval task(s) for a node as completed."""
        sql = """
            UPDATE workflow_approval_tasks
            SET status = 'completed',
                claimed_by = %s,
                completion_action = %s,
                completed_at = %s
            WHERE instance_id = %s AND node_id = %s AND status IN ('pending', 'claimed')
        """
        now = datetime.utcnow()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (actor_id, action.value, now,
                     _uuid_to_bytes(instance_id), node_id),
                )
                conn.commit()

    def list_pending_tasks(
        self,
        assignee_type: AssigneeType,
        assignee_id: str,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> list[dict[str, Any]]:
        """Query pending approval tasks for an assignee.

        Uses the (assignee_type, assignee_id, status) composite index.
        """
        offset = max(0, (page - 1) * page_size)
        sql = """
            SELECT t.id, t.instance_id, t.node_id,
                   t.assignee_type, t.assignee_id,
                   t.status, t.due_at, t.created_at,
                   i.workflow_key, i.version
            FROM workflow_approval_tasks t
            JOIN workflow_instances i ON t.instance_id = i.id
            WHERE t.assignee_type = %s
              AND t.assignee_id = %s
              AND t.status = 'pending'
            ORDER BY t.created_at DESC
            LIMIT %s OFFSET %s
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (assignee_type.value, assignee_id, page_size, offset))
                rows = cur.fetchall()
                return [
                    {
                        "task_id": r[0],
                        "instance_id": str(_bytes_to_uuid(r[1])),
                        "node_id": r[2],
                        "assignee_type": r[3],
                        "assignee_id": r[4],
                        "status": r[5],
                        "due_at": r[6].isoformat() if r[6] else None,
                        "created_at": r[7].isoformat() if r[7] else None,
                        "workflow_key": r[8],
                        "version": r[9],
                    }
                    for r in rows
                ]

    def find_timed_out_tasks(self, now: Optional[datetime] = None) -> list[dict[str, Any]]:
        """Find pending approval tasks past their due_at (for timeout scanner)."""
        now = now or datetime.utcnow()
        sql = """
            SELECT id, instance_id, node_id, assignee_type, assignee_id, due_at
            FROM workflow_approval_tasks
            WHERE status = 'pending' AND due_at IS NOT NULL AND due_at < %s
            LIMIT 1000
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (now,))
                rows = cur.fetchall()
                return [
                    {
                        "task_id": r[0],
                        "instance_id": _bytes_to_uuid(r[1]),
                        "node_id": r[2],
                        "assignee_type": AssigneeType(r[3]),
                        "assignee_id": r[4],
                        "due_at": r[5],
                    }
                    for r in rows
                ]

    # =======================================================================
    # State events (REQ-020, REQ-058)
    # =======================================================================

    def append_state_event(
        self,
        instance_id: UUID,
        event_type: str,
        *,
        node_id: Optional[str] = None,
        from_status: Optional[str] = None,
        to_status: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> None:
        """Append a state event (append-only audit log)."""
        sql = """
            INSERT INTO workflow_state_events
                (instance_id, node_id, event_type, from_status, to_status,
                 payload_json, occurred_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        payload_json = (json.dumps(payload, ensure_ascii=False, default=str)
                        if payload is not None else None)
        now = datetime.utcnow()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (_uuid_to_bytes(instance_id), node_id, event_type,
                     from_status, to_status, payload_json, now),
                )
                conn.commit()

    def list_state_events(
        self,
        instance_id: UUID,
        *,
        event_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """List state events for an instance (optionally filtered by type)."""
        if event_type is None:
            sql = """
                SELECT id, node_id, event_type, from_status, to_status,
                       payload_json, occurred_at
                FROM workflow_state_events
                WHERE instance_id = %s
                ORDER BY occurred_at ASC, id ASC
            """
            params: tuple[Any, ...] = (_uuid_to_bytes(instance_id),)
        else:
            sql = """
                SELECT id, node_id, event_type, from_status, to_status,
                       payload_json, occurred_at
                FROM workflow_state_events
                WHERE instance_id = %s AND event_type = %s
                ORDER BY occurred_at ASC, id ASC
            """
            params = (_uuid_to_bytes(instance_id), event_type)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
                return [
                    {
                        "id": r[0],
                        "node_id": r[1],
                        "event_type": r[2],
                        "from_status": r[3],
                        "to_status": r[4],
                        "payload": json.loads(r[5]) if isinstance(r[5], str) else r[5],
                        "occurred_at": r[6].isoformat() if r[6] else None,
                    }
                    for r in rows
                ]
