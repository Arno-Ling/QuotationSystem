"""
SkillInvoker — Protocol for registering and invoking Skills.

Each Skill is `async def xxx_skill(**kwargs) -> dict[str, Any]`.

The naive implementation (adapters/direct_skill_invoker.py) uses an
in-memory dict. The future Harness implementation delegates to
`harness.tools.ToolRegistry` for permission audit / retry.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Protocol

# A Skill is an async callable taking kwargs and returning a dict.
SkillFn = Callable[..., Awaitable[dict[str, Any]]]


class SkillInvoker(Protocol):
    """Contract for a Skill registry + invoker."""

    def register(self, name: str, fn: SkillFn) -> None:
        """Register a Skill under the given name.

        Overwrites any existing registration with the same name.
        """
        ...

    async def invoke(self, name: str, **kwargs: Any) -> dict[str, Any]:
        """Invoke a registered Skill. Raises SkillNotFoundError if absent."""
        ...

    def list_skills(self) -> list[str]:
        """List all registered Skill names."""
        ...
