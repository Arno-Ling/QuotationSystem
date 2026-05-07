"""
AgentRunner — Protocol for executing Agents.

The naive implementation (adapters/inline_agent_runner.py) routes to
in-process `SimpleAgent` classes. The future Harness implementation
routes to `AgentLoop.run()` (ReAct).

Business code depends only on `AgentRunner`, never on a concrete class.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class AgentRunRequest:
    """Request to run an Agent."""
    agent_key: str                              # e.g. "simple_exception_agent"
    inputs: dict[str, Any]
    context: dict[str, Any] | None = None


@dataclass
class AgentRunResult:
    """Result of an Agent run."""
    success: bool
    outputs: dict[str, Any] = field(default_factory=dict)
    steps: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    duration_ms: int = 0


class AgentRunner(Protocol):
    """Contract for any Agent execution engine."""

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        """Execute the agent identified by `request.agent_key`.

        Must never raise; all failures wrapped in `AgentRunResult(success=False)`.
        """
        ...
