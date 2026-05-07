"""
StateMachine - pure-function state transition validator.

This is a pure module: it does NOT read or write the database, and it
produces no side effects. Its only job is to answer the question:

    Given `current_state`, is the transition to `new_state` legal?

Two independent state machines are defined:
- WORKFLOW_TRANSITIONS for `WorkflowStatus`
- NODE_TRANSITIONS     for `NodeStatus`

Terminal states (COMPLETED / FAILED / CANCELLED for workflows;
COMPLETED / FAILED / SKIPPED for nodes) have no outgoing edges - they
are absorbing.

Requirements: REQ-018, REQ-019, REQ-061
"""
from __future__ import annotations

from .errors import IllegalTransitionError
from .models import NodeStatus, WorkflowStatus


# ---------------------------------------------------------------------------
# Transition tables
# ---------------------------------------------------------------------------

WORKFLOW_TRANSITIONS: dict[WorkflowStatus, set[WorkflowStatus]] = {
    WorkflowStatus.PENDING: {
        WorkflowStatus.RUNNING,
        WorkflowStatus.CANCELLED,
    },
    WorkflowStatus.RUNNING: {
        WorkflowStatus.WAITING_APPROVAL,
        WorkflowStatus.EXECUTING,
        WorkflowStatus.COMPLETED,
        WorkflowStatus.FAILED,
        WorkflowStatus.SUSPENDED,
        WorkflowStatus.CANCELLED,
    },
    WorkflowStatus.WAITING_APPROVAL: {
        WorkflowStatus.EXECUTING,
        WorkflowStatus.RUNNING,
        WorkflowStatus.COMPLETED,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED,
    },
    WorkflowStatus.EXECUTING: {
        WorkflowStatus.RUNNING,
        WorkflowStatus.COMPLETED,
        WorkflowStatus.FAILED,
        WorkflowStatus.SUSPENDED,
        WorkflowStatus.CANCELLED,
    },
    WorkflowStatus.SUSPENDED: {
        WorkflowStatus.RUNNING,
        WorkflowStatus.EXECUTING,
        WorkflowStatus.CANCELLED,
    },
    # Terminal states
    WorkflowStatus.COMPLETED: set(),
    WorkflowStatus.FAILED: set(),
    WorkflowStatus.CANCELLED: set(),
}


NODE_TRANSITIONS: dict[NodeStatus, set[NodeStatus]] = {
    NodeStatus.PENDING: {
        NodeStatus.RUNNING,
        NodeStatus.SKIPPED,
    },
    NodeStatus.RUNNING: {
        NodeStatus.COMPLETED,
        NodeStatus.FAILED,
        NodeStatus.WAITING_APPROVAL,
    },
    NodeStatus.WAITING_APPROVAL: {
        NodeStatus.COMPLETED,
        NodeStatus.FAILED,
        NodeStatus.SKIPPED,
    },
    # Terminal states
    NodeStatus.COMPLETED: set(),
    NodeStatus.FAILED: set(),
    NodeStatus.SKIPPED: set(),
}


# Terminal state sets for convenience / property tests
WORKFLOW_TERMINAL_STATES: frozenset[WorkflowStatus] = frozenset({
    WorkflowStatus.COMPLETED,
    WorkflowStatus.FAILED,
    WorkflowStatus.CANCELLED,
})

NODE_TERMINAL_STATES: frozenset[NodeStatus] = frozenset({
    NodeStatus.COMPLETED,
    NodeStatus.FAILED,
    NodeStatus.SKIPPED,
})


# ---------------------------------------------------------------------------
# StateMachine class
# ---------------------------------------------------------------------------

class StateMachine:
    """Pure-function state transition validator.

    Usage:
        new = StateMachine.transition_workflow(current, target)
        new = StateMachine.transition_node(current, target)
    """

    @staticmethod
    def is_terminal_workflow(status: WorkflowStatus) -> bool:
        """Return True if the workflow status is terminal (absorbing)."""
        return status in WORKFLOW_TERMINAL_STATES

    @staticmethod
    def is_terminal_node(status: NodeStatus) -> bool:
        """Return True if the node status is terminal (absorbing)."""
        return status in NODE_TERMINAL_STATES

    @staticmethod
    def can_transition_workflow(
        current: WorkflowStatus, target: WorkflowStatus
    ) -> bool:
        """Check whether `current -> target` is a legal workflow transition."""
        if current not in WORKFLOW_TRANSITIONS:
            return False
        return target in WORKFLOW_TRANSITIONS[current]

    @staticmethod
    def can_transition_node(
        current: NodeStatus, target: NodeStatus
    ) -> bool:
        """Check whether `current -> target` is a legal node transition."""
        if current not in NODE_TRANSITIONS:
            return False
        return target in NODE_TRANSITIONS[current]

    @classmethod
    def transition_workflow(
        cls, current: WorkflowStatus, target: WorkflowStatus,
    ) -> WorkflowStatus:
        """Validate and return the new workflow status.

        Raises:
            IllegalTransitionError: if the transition is not allowed.
        """
        if not cls.can_transition_workflow(current, target):
            raise IllegalTransitionError(
                from_state=current.value,
                to_state=target.value,
                scope="workflow",
            )
        return target

    @classmethod
    def transition_node(
        cls, current: NodeStatus, target: NodeStatus,
    ) -> NodeStatus:
        """Validate and return the new node status.

        Raises:
            IllegalTransitionError: if the transition is not allowed.
        """
        if not cls.can_transition_node(current, target):
            raise IllegalTransitionError(
                from_state=current.value,
                to_state=target.value,
                scope="node",
            )
        return target

    @staticmethod
    def valid_next_workflow(current: WorkflowStatus) -> set[WorkflowStatus]:
        """List legal next states for the given workflow status."""
        return WORKFLOW_TRANSITIONS.get(current, set()).copy()

    @staticmethod
    def valid_next_node(current: NodeStatus) -> set[NodeStatus]:
        """List legal next states for the given node status."""
        return NODE_TRANSITIONS.get(current, set()).copy()
