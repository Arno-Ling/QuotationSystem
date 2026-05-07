"""
FunctionWorkflowEngine — naive implementation of WorkflowEngine Protocol.

A workflow = an `async def xxx_workflow(inputs, run_id) -> dict` function.
Registered via the `@register_workflow("key")` decorator at module load time.

Resume callbacks (invoked by ApprovalService after APPROVE/REJECT) are
registered in RESUME_REGISTRY.

Future Harness replacement:
    HarnessWorkflowEngine — converts these functions to YAML DAG and
    runs via harness.workflow.executor.DAGExecutor.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from interfaces.state_store import StateStore

logger = logging.getLogger(__name__)


# Registry of workflow functions: key -> async (inputs, run_id) -> dict
WORKFLOW_REGISTRY: dict[str, Callable[..., Awaitable[dict[str, Any]]]] = {}

# Registry of resume callbacks: name -> async (run_id, payload) -> None
RESUME_REGISTRY: dict[str, Callable[..., Awaitable[None]]] = {}


def register_workflow(key: str):
    """Decorator: register a workflow function at module top level.

    Example:
        @register_workflow("exception_handling_v1")
        async def exception_handling_workflow(inputs, run_id):
            ...
    """
    def _deco(fn: Callable[..., Awaitable[dict[str, Any]]]):
        if key in WORKFLOW_REGISTRY:
            logger.warning("Overwriting workflow registration: %s", key)
        WORKFLOW_REGISTRY[key] = fn
        logger.debug("Registered workflow: %s", key)
        return fn
    return _deco


def register_resume(name: str):
    """Decorator: register a resume callback for post-approval continuation."""
    def _deco(fn: Callable[..., Awaitable[None]]):
        if name in RESUME_REGISTRY:
            logger.warning("Overwriting resume registration: %s", name)
        RESUME_REGISTRY[name] = fn
        logger.debug("Registered resume callback: %s", name)
        return fn
    return _deco


# Valid state transitions for workflow_runs (validated in _update_status)
VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"running", "cancelled"},
    "running": {"waiting_approval", "completed", "failed", "cancelled"},
    "waiting_approval": {"running", "completed", "failed", "cancelled"},
    # Terminal states
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}


class IllegalTransitionError(Exception):
    def __init__(self, from_s: str, to_s: str) -> None:
        super().__init__(f"Illegal workflow_run transition: {from_s} -> {to_s}")
        self.from_status = from_s
        self.to_status = to_s


class WorkflowNotFoundError(KeyError):
    pass


class FunctionWorkflowEngine:
    """Workflow engine backed by a dict of async functions."""

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        state_store: StateStore,
    ) -> None:
        self._sf = session_factory
        self._state = state_store

    # -----------------------------------------------------------------
    # DB helpers
    # -----------------------------------------------------------------

    async def _create_run(
        self,
        run_id: UUID,
        workflow_key: str,
        inputs: dict[str, Any],
        trigger_source: str,
        trigger_user: Optional[str],
    ) -> None:
        async with self._sf() as session:
            async with session.begin():
                await session.execute(
                    text("""
                        INSERT INTO workflow_runs
                            (id, workflow_key, version, status, inputs_json,
                             context_json, trigger_source, trigger_user,
                             started_at)
                        VALUES
                            (:id, :wkey, 1, 'running', :inp,
                             :ctx, :src, :usr, :now)
                    """),
                    {
                        "id": run_id.bytes,
                        "wkey": workflow_key,
                        "inp": json.dumps(inputs, ensure_ascii=False, default=str),
                        "ctx": json.dumps({}, ensure_ascii=False),
                        "src": trigger_source,
                        "usr": trigger_user,
                        "now": datetime.utcnow(),
                    },
                )

    async def _load_run(self, run_id: UUID) -> dict[str, Any]:
        async with self._sf() as session:
            async with session.begin():
                result = await session.execute(
                    text("""
                        SELECT workflow_key, status, current_step, next_step,
                               inputs_json, outputs_json, context_json,
                               started_at, ended_at, error_message
                        FROM workflow_runs WHERE id = :id
                    """),
                    {"id": run_id.bytes},
                )
                row = result.first()
        if row is None:
            raise KeyError(f"workflow_run not found: {run_id}")
        return {
            "workflow_key": row[0],
            "status": row[1],
            "current_step": row[2],
            "next_step": row[3],
            "inputs": json.loads(row[4]) if isinstance(row[4], str) else row[4],
            "outputs": json.loads(row[5]) if isinstance(row[5], str) else row[5],
            "context": json.loads(row[6]) if isinstance(row[6], str) else row[6],
            "started_at": row[7].isoformat() if row[7] else None,
            "ended_at": row[8].isoformat() if row[8] else None,
            "error_message": row[9],
        }

    async def _update_status(
        self,
        run_id: UUID,
        new_status: str,
        *,
        next_step: Optional[str] = None,
        outputs: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Validate state transition, then UPDATE workflow_runs."""
        async with self._sf() as session:
            async with session.begin():
                # Read current status
                current = await session.execute(
                    text("SELECT status FROM workflow_runs WHERE id = :id"),
                    {"id": run_id.bytes},
                )
                row = current.first()
                if row is None:
                    raise KeyError(f"workflow_run not found: {run_id}")
                old_status = row[0]

                # Validate transition
                if new_status != old_status:
                    if new_status not in VALID_TRANSITIONS.get(old_status, set()):
                        raise IllegalTransitionError(old_status, new_status)

                # Update
                ended_at = datetime.utcnow() if new_status in ("completed", "failed", "cancelled") else None
                await session.execute(
                    text("""
                        UPDATE workflow_runs
                        SET status = :st,
                            next_step = COALESCE(:nxt, next_step),
                            outputs_json = COALESCE(:out, outputs_json),
                            error_message = COALESCE(:err, error_message),
                            ended_at = COALESCE(:end, ended_at)
                        WHERE id = :id
                    """),
                    {
                        "st": new_status,
                        "nxt": next_step,
                        "out": json.dumps(outputs, ensure_ascii=False, default=str) if outputs is not None else None,
                        "err": error,
                        "end": ended_at,
                        "id": run_id.bytes,
                    },
                )

    # -----------------------------------------------------------------
    # Protocol methods
    # -----------------------------------------------------------------

    async def start(
        self,
        workflow_key: str,
        inputs: dict[str, Any],
        *,
        trigger_source: str = "api",
        trigger_user: Optional[str] = None,
    ) -> UUID:
        """Start a new workflow run."""
        if workflow_key not in WORKFLOW_REGISTRY:
            raise WorkflowNotFoundError(
                f"Workflow not registered: {workflow_key} "
                f"(available: {sorted(WORKFLOW_REGISTRY)})"
            )

        run_id = uuid4()
        await self._create_run(run_id, workflow_key, inputs, trigger_source, trigger_user)
        logger.info("Started workflow run %s (key=%s)", run_id, workflow_key)

        fn = WORKFLOW_REGISTRY[workflow_key]
        try:
            result = await fn(inputs=inputs, run_id=run_id)
            # If workflow didn't mark itself waiting_approval, finalize as completed
            if result is None:
                result = {}
            if result.get("status") != "waiting_approval":
                await self._update_status(run_id, "completed", outputs=result)
        except Exception as e:
            logger.exception("Workflow %s failed", workflow_key)
            await self._update_status(run_id, "failed", error=f"{type(e).__name__}: {e}")
            raise
        return run_id

    async def resume(self, run_id: UUID, payload: dict[str, Any]) -> None:
        """Continue a waiting workflow after an external event."""
        run = await self._load_run(run_id)
        next_step = run.get("next_step")
        if not next_step:
            raise ValueError(f"workflow_run {run_id} has no next_step to resume")
        if next_step not in RESUME_REGISTRY:
            raise KeyError(f"Resume callback not registered: {next_step}")

        logger.info("Resuming workflow run %s at step %s", run_id, next_step)
        fn = RESUME_REGISTRY[next_step]
        try:
            await fn(run_id=run_id, payload=payload)
        except Exception as e:
            logger.exception("Resume step %s failed", next_step)
            await self._update_status(run_id, "failed", error=f"{type(e).__name__}: {e}")
            raise

    async def get_status(self, run_id: UUID) -> dict[str, Any]:
        """Return a full status snapshot for the given run."""
        run = await self._load_run(run_id)
        return {
            "run_id": str(run_id),
            "workflow_key": run["workflow_key"],
            "status": run["status"],
            "current_step": run["current_step"],
            "next_step": run["next_step"],
            "started_at": run["started_at"],
            "ended_at": run["ended_at"],
            "outputs": run["outputs"],
            "error": run["error_message"],
        }
