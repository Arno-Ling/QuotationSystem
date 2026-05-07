"""
InlineAgentRunner — naive implementation of AgentRunner Protocol.

Maintains an in-memory mapping `agent_key -> SimpleAgent` instance.
Routes a run request to the corresponding agent's `.run(**inputs)` in
the same process.

Future Harness replacement:
    HarnessAgentRunner — dispatch through harness.Orchestrator to
    AgentLoop.run() with full ReAct loop.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from interfaces.agent_runner import AgentRunRequest, AgentRunResult

logger = logging.getLogger(__name__)


class InlineAgentRunner:
    """In-process router: agent_key -> SimpleAgent instance."""

    def __init__(self) -> None:
        self._agents: dict[str, Any] = {}

    def register(self, agent_key: str, agent: Any) -> None:
        """Register a SimpleAgent instance under its key.

        The agent must expose `async def run(**kwargs) -> dict[str, Any]`.
        """
        if agent_key in self._agents:
            logger.warning("Overwriting existing agent: %s", agent_key)
        self._agents[agent_key] = agent
        logger.debug("Registered agent: %s", agent_key)

    def unregister(self, agent_key: str) -> None:
        self._agents.pop(agent_key, None)

    def list_agents(self) -> list[str]:
        return sorted(self._agents.keys())

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        """Route the request to the agent and wrap all exceptions."""
        t0 = time.monotonic()
        agent = self._agents.get(request.agent_key)
        if agent is None:
            return AgentRunResult(
                success=False,
                error=f"Agent not registered: {request.agent_key!r}",
                duration_ms=0,
            )

        try:
            outputs = await agent.run(**request.inputs)
            duration_ms = int((time.monotonic() - t0) * 1000)
            steps = outputs.pop("steps", []) if isinstance(outputs, dict) else []
            return AgentRunResult(
                success=True,
                outputs=outputs if isinstance(outputs, dict) else {"result": outputs},
                steps=steps,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.exception("Agent %s failed", request.agent_key)
            # Try to salvage partial steps from the agent
            steps = getattr(agent, "steps", []) or []
            return AgentRunResult(
                success=False,
                error=f"{type(e).__name__}: {e}",
                steps=list(steps),
                duration_ms=duration_ms,
            )
