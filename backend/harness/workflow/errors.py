"""
Exception hierarchy for the Harness Workflow Engine.

All custom exceptions inherit from `WorkflowError`.

Categories:
    - DAG definition errors    : CyclicGraphError, InvalidNodeRefError,
                                 SchemaValidationError, DuplicateDefinitionError
    - Node execution errors    : NodeExecutionError, ToolNotFoundError,
                                 AgentNotFoundError, SkillLoadError,
                                 NoMatchingBranchError
    - State transition errors  : IllegalTransitionError
    - Approval errors          : PermissionError (workflow-specific),
                                 IllegalActionError
    - Persistence errors       : DatabaseError, InstanceLockedError,
                                 InstanceNotFoundError, DefinitionNotFoundError
    - Template errors          : TemplateRenderError, SecurityError
"""
from __future__ import annotations

from typing import Any, Optional


class WorkflowError(Exception):
    """Base class for all workflow engine exceptions."""

    def __init__(self, message: str, *, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | details={self.details}"
        return self.message


# ---------------------------------------------------------------------------
# DAG definition errors
# ---------------------------------------------------------------------------

class CyclicGraphError(WorkflowError):
    """Raised when a workflow definition contains a cycle.

    Attributes:
        cycle: A list of node ids forming at least one cycle, if known.
    """

    def __init__(self, message: str = "DAG contains a cycle", *, cycle: Optional[list[str]] = None) -> None:
        super().__init__(message, details={"cycle": cycle or []})
        self.cycle = cycle or []


class InvalidNodeRefError(WorkflowError):
    """An edge references a node id that is not in the node set."""

    def __init__(self, node_id: str, *, in_edge: Optional[tuple[str, str]] = None) -> None:
        msg = f"Edge references unknown node: {node_id!r}"
        super().__init__(msg, details={"node_id": node_id, "in_edge": in_edge})
        self.node_id = node_id


class SchemaValidationError(WorkflowError):
    """Inputs/outputs or a workflow definition fails schema validation."""

    def __init__(self, message: str, *, field_path: Optional[str] = None) -> None:
        super().__init__(message, details={"field_path": field_path})
        self.field_path = field_path


class DuplicateDefinitionError(WorkflowError):
    """Attempting to register a (key, version) that already exists."""

    def __init__(self, key: str, version: int) -> None:
        msg = f"Workflow definition already exists: key={key!r}, version={version}"
        super().__init__(msg, details={"key": key, "version": version})
        self.key = key
        self.version = version


# ---------------------------------------------------------------------------
# Node execution errors
# ---------------------------------------------------------------------------

class NodeExecutionError(WorkflowError):
    """Generic node execution failure; wraps the underlying exception."""

    def __init__(self, node_id: str, cause: Exception) -> None:
        msg = f"Node {node_id!r} execution failed: {cause}"
        super().__init__(msg, details={"node_id": node_id, "cause_type": type(cause).__name__})
        self.node_id = node_id
        self.cause = cause


class ToolNotFoundError(WorkflowError):
    """`TaskNode(call_kind="tool")` target is not registered in ToolRegistry."""

    def __init__(self, tool_name: str) -> None:
        super().__init__(f"Tool not found: {tool_name!r}", details={"tool_name": tool_name})
        self.tool_name = tool_name


class AgentNotFoundError(WorkflowError):
    """`TaskNode(call_kind="agent")` target is not registered in Orchestrator."""

    def __init__(self, agent_id: str) -> None:
        super().__init__(f"Agent not found: {agent_id!r}", details={"agent_id": agent_id})
        self.agent_id = agent_id


class SkillLoadError(WorkflowError):
    """`TaskNode(call_kind="skill")` target format invalid or class not importable."""

    def __init__(self, target: str, reason: str) -> None:
        super().__init__(f"Skill load failed: {target!r} ({reason})",
                         details={"target": target, "reason": reason})
        self.target = target


class NoMatchingBranchError(WorkflowError):
    """DecisionNode has no branch matching and no default_next."""

    def __init__(self, node_id: str) -> None:
        super().__init__(f"DecisionNode {node_id!r} has no matching branch and no default_next",
                         details={"node_id": node_id})
        self.node_id = node_id


# ---------------------------------------------------------------------------
# State transition errors
# ---------------------------------------------------------------------------

class IllegalTransitionError(WorkflowError):
    """State transition is not allowed by the state machine."""

    def __init__(self, from_state: str, to_state: str, *, scope: str = "workflow") -> None:
        msg = f"Illegal {scope} transition: {from_state} -> {to_state}"
        super().__init__(msg, details={"from": from_state, "to": to_state, "scope": scope})
        self.from_state = from_state
        self.to_state = to_state
        self.scope = scope


# ---------------------------------------------------------------------------
# Approval errors
# ---------------------------------------------------------------------------

class WorkflowPermissionError(WorkflowError):
    """Actor is not authorized to perform the approval action.

    Named with `Workflow` prefix to avoid clashing with the built-in
    `PermissionError`.
    """

    def __init__(self, actor_id: str, node_id: str) -> None:
        msg = f"Actor {actor_id!r} is not authorized to act on node {node_id!r}"
        super().__init__(msg, details={"actor_id": actor_id, "node_id": node_id})
        self.actor_id = actor_id
        self.node_id = node_id


class IllegalActionError(WorkflowError):
    """The action is not in the node's `allowed_actions` list."""

    def __init__(self, action: str, allowed: list[str]) -> None:
        msg = f"Action {action!r} is not allowed; allowed={allowed}"
        super().__init__(msg, details={"action": action, "allowed": allowed})
        self.action = action
        self.allowed = allowed


# ---------------------------------------------------------------------------
# Persistence errors
# ---------------------------------------------------------------------------

class DatabaseError(WorkflowError):
    """Generic database operation failure."""


class InstanceLockedError(WorkflowError):
    """Another process holds the lease on this instance."""

    def __init__(self, instance_id: str, lease_owner: Optional[str] = None) -> None:
        msg = f"Instance {instance_id!r} is locked by another process"
        super().__init__(msg, details={"instance_id": instance_id, "lease_owner": lease_owner})
        self.instance_id = instance_id


class InstanceNotFoundError(WorkflowError):
    """No workflow instance exists with the given id."""

    def __init__(self, instance_id: str) -> None:
        super().__init__(f"Instance not found: {instance_id!r}",
                         details={"instance_id": instance_id})
        self.instance_id = instance_id


class DefinitionNotFoundError(WorkflowError):
    """No workflow definition exists with the given key/version."""

    def __init__(self, key: str, version: Optional[int] = None) -> None:
        msg = f"Workflow definition not found: key={key!r}" + (f", version={version}" if version else "")
        super().__init__(msg, details={"key": key, "version": version})
        self.key = key
        self.version = version


# ---------------------------------------------------------------------------
# Template / security errors
# ---------------------------------------------------------------------------

class TemplateRenderError(WorkflowError):
    """Template evaluation failed (bad expression, missing key, runtime error)."""

    def __init__(self, template: str, cause: Exception) -> None:
        msg = f"Template render failed: {template!r} ({cause})"
        super().__init__(msg, details={"template": template, "cause_type": type(cause).__name__})
        self.template = template
        self.cause = cause


class SecurityError(WorkflowError):
    """Sandbox violation (access to forbidden object/attribute in template)."""
