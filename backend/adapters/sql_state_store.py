"""
SqlStateStore — naive implementation of StateStore Protocol.

Reads/writes `workflow_runs.context_json` (a JSON column) using
SQLAlchemy. Each put() is a SELECT ... FOR UPDATE + UPDATE in a
transaction to avoid concurrent overwrites.

Future Harness replacement:
    HarnessStateStore — writes workflow_instances.context_json with
    incremental diff + Redis cache for hot runs.
"""
from __future__ import annotations

import copy
import json
import logging
from typing import Any, Callable
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class SqlStateStore:
    """Key-value state backed by workflow_runs.context_json."""

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
    ) -> None:
        self._sf = session_factory

    async def _load_context(self, session: AsyncSession, run_id: UUID) -> dict[str, Any]:
        result = await session.execute(
            text(
                "SELECT context_json FROM workflow_runs WHERE id = :rid FOR UPDATE"
            ),
            {"rid": run_id.bytes},
        )
        row = result.first()
        if row is None:
            raise KeyError(f"workflow_run not found: {run_id}")
        raw = row[0]
        if raw is None:
            return {}
        return json.loads(raw) if isinstance(raw, str) else raw

    async def _save_context(
        self, session: AsyncSession, run_id: UUID, context: dict[str, Any],
    ) -> None:
        await session.execute(
            text(
                "UPDATE workflow_runs SET context_json = :ctx WHERE id = :rid"
            ),
            {"ctx": json.dumps(context, ensure_ascii=False, default=str),
             "rid": run_id.bytes},
        )

    async def put(self, run_id: UUID, key: str, value: Any) -> None:
        """Set a key under the run's context. Single transaction."""
        async with self._sf() as session:
            async with session.begin():
                ctx = await self._load_context(session, run_id)
                ctx[key] = value
                await self._save_context(session, run_id, ctx)
        logger.debug("StateStore.put run_id=%s key=%s", run_id, key)

    async def get(self, run_id: UUID, key: str) -> Any:
        """Read a key; None if absent."""
        async with self._sf() as session:
            async with session.begin():
                ctx = await self._load_context(session, run_id)
        return ctx.get(key)

    async def snapshot(self, run_id: UUID) -> dict[str, Any]:
        """Deep-copied snapshot of the full context."""
        async with self._sf() as session:
            async with session.begin():
                ctx = await self._load_context(session, run_id)
        return copy.deepcopy(ctx)
