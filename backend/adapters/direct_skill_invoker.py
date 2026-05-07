"""
DirectSkillInvoker — naive implementation of SkillInvoker Protocol.

Stores Skill functions in an in-memory dict; `invoke` is a direct
`await fn(**kwargs)`.

Future Harness replacement:
    ToolRegistryInvoker — delegate to harness.tools.ToolRegistry for
    permission audit, retry, metrics.
"""
from __future__ import annotations

import logging
from typing import Any

from interfaces.skill_invoker import SkillFn

logger = logging.getLogger(__name__)


class SkillNotFoundError(KeyError):
    """Raised when invoke() is called with an unregistered skill name."""


class DirectSkillInvoker:
    """In-memory Skill registry + invoker."""

    def __init__(self) -> None:
        self._skills: dict[str, SkillFn] = {}

    def register(self, name: str, fn: SkillFn) -> None:
        """Register a Skill. Overwrites any existing registration."""
        if name in self._skills:
            logger.warning("Overwriting existing skill: %s", name)
        self._skills[name] = fn
        logger.debug("Registered skill: %s", name)

    def register_decorator(self, name: str):
        """Use as a decorator to register a Skill at module top level.

        Example:
            @invoker.register_decorator("analyze_exception")
            async def analyze_exception_skill(**kwargs) -> dict:
                ...
        """
        def _deco(fn: SkillFn) -> SkillFn:
            self.register(name, fn)
            return fn
        return _deco

    async def invoke(self, name: str, **kwargs: Any) -> dict[str, Any]:
        """Invoke a Skill. Raises SkillNotFoundError if absent."""
        if name not in self._skills:
            raise SkillNotFoundError(
                f"Skill not registered: {name!r} "
                f"(available: {sorted(self._skills)})"
            )
        return await self._skills[name](**kwargs)

    def list_skills(self) -> list[str]:
        """Return all registered Skill names, sorted."""
        return sorted(self._skills.keys())

    def clear(self) -> None:
        """Remove all registered skills (primarily for tests)."""
        self._skills.clear()
