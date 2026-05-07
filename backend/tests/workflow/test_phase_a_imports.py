"""
Phase A smoke test: verify all models and errors import correctly.

This test validates Checkpoint 1 (Task 6):
- Module structure is importable
- All enums are defined
- All Pydantic models validate
- Exception hierarchy is in place
- ApprovalAction has 12 members
"""
import sys
from pathlib import Path
from datetime import datetime
from uuid import uuid4

# Ensure backend/ is importable when running this file directly
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))


def test_all_enums_importable():
    """REQ-018, REQ-019, REQ-027, REQ-028: All enums are defined and importable."""
    from harness.workflow.models import (
        WorkflowStatus,
        NodeStatus,
        NodeType,
        ErrorStrategy,
        JoinStrategy,
        AssigneeType,
        ApprovalAction,
        TimeoutStrategy,
        CallKind,
    )

    # Check enum member counts
    assert len(list(WorkflowStatus)) == 8, "WorkflowStatus should have 8 states"
    assert len(list(NodeStatus)) == 6, "NodeStatus should have 6 states"
    assert len(list(NodeType)) == 5, "NodeType should have 5 types"
    assert len(list(ApprovalAction)) == 12, "ApprovalAction should have 12 actions"
    assert len(list(AssigneeType)) == 3, "AssigneeType should have 3 types"


def test_all_node_definitions_importable():
    """REQ-011 ~ REQ-017: All node definition models import."""
    from harness.workflow.models import (
        TaskNodeDef,
        DecisionNodeDef,
        DecisionBranch,
        ParallelNodeDef,
        ApprovalNodeDef,
        LoopNodeDef,
        RetryPolicy,
        Edge,
        AssigneeSpec,
    )

    # Construct a minimal valid instance of each
    RetryPolicy(max_attempts=3)
    Edge(**{"from": "a", "to": "b"})


def test_all_exceptions_importable():
    """REQ-053: Exception hierarchy is complete."""
    from harness.workflow.errors import (
        WorkflowError,
        CyclicGraphError,
        InvalidNodeRefError,
        SchemaValidationError,
        DuplicateDefinitionError,
        NodeExecutionError,
        ToolNotFoundError,
        AgentNotFoundError,
        SkillLoadError,
        NoMatchingBranchError,
        IllegalTransitionError,
        WorkflowPermissionError,
        IllegalActionError,
        DatabaseError,
        InstanceLockedError,
        InstanceNotFoundError,
        DefinitionNotFoundError,
        TemplateRenderError,
        SecurityError,
    )

    # All custom errors inherit from WorkflowError
    for exc_class in [
        CyclicGraphError, InvalidNodeRefError, SchemaValidationError,
        DuplicateDefinitionError, NodeExecutionError, ToolNotFoundError,
        AgentNotFoundError, SkillLoadError, NoMatchingBranchError,
        IllegalTransitionError, WorkflowPermissionError, IllegalActionError,
        DatabaseError, InstanceLockedError, InstanceNotFoundError,
        DefinitionNotFoundError, TemplateRenderError, SecurityError,
    ]:
        assert issubclass(exc_class, WorkflowError), f"{exc_class.__name__} must inherit WorkflowError"


def test_workflow_definition_construct():
    """REQ-006: WorkflowDefinition can be constructed with minimal fields."""
    from harness.workflow.models import (
        WorkflowDefinition,
        TaskNodeDef,
        CallKind,
        Edge,
    )

    definition = WorkflowDefinition(
        key="test_workflow",
        version=1,
        name="Test Workflow",
        start_node="n1",
        nodes=[
            TaskNodeDef(
                id="n1",
                name="First Task",
                call_kind=CallKind.TOOL,
                target="some_tool",
            ),
        ],
        edges=[],
    )

    assert definition.key == "test_workflow"
    assert len(definition.nodes) == 1
    assert definition.max_concurrent_nodes == 8  # default


def test_workflow_context_roundtrip():
    """REQ-022: WorkflowContext serialization round-trip."""
    from harness.workflow.models import WorkflowContext, NodeStatus

    now = datetime.utcnow()
    ctx = WorkflowContext(
        instance_id=uuid4(),
        workflow_key="test",
        inputs={"x": 1},
        outputs={"n1": {"result": 42}},
        node_statuses={"n1": NodeStatus.COMPLETED},
        created_at=now,
        updated_at=now,
    )

    # Round-trip
    json_str = ctx.model_dump_json()
    ctx2 = WorkflowContext.model_validate_json(json_str)

    assert ctx2.instance_id == ctx.instance_id
    assert ctx2.outputs == ctx.outputs
    assert ctx2.node_statuses == ctx.node_statuses


def test_approval_action_terminal_set():
    """ApprovalAction.terminal_actions() returns the 4 terminal actions."""
    from harness.workflow.models import ApprovalAction

    terminal = ApprovalAction.terminal_actions()
    assert ApprovalAction.APPROVE in terminal
    assert ApprovalAction.REJECT in terminal
    assert ApprovalAction.REJECT_RETURN in terminal
    assert ApprovalAction.WITHDRAW in terminal
    assert len(terminal) == 4


def test_cyclic_graph_error_carries_cycle():
    """REQ-007: CyclicGraphError carries the cycle node list."""
    from harness.workflow.errors import CyclicGraphError

    exc = CyclicGraphError(cycle=["a", "b", "a"])
    assert exc.cycle == ["a", "b", "a"]
    assert "a" in str(exc)


if __name__ == "__main__":
    test_all_enums_importable()
    test_all_node_definitions_importable()
    test_all_exceptions_importable()
    test_workflow_definition_construct()
    test_workflow_context_roundtrip()
    test_approval_action_terminal_set()
    test_cyclic_graph_error_carries_cycle()
    print("[OK] Phase A smoke tests all passed")
    print("  - 12 approval actions defined")
    print("  - 8 workflow statuses defined")
    print("  - 5 node types defined")
    print("  - WorkflowContext round-trip works")
    print("  - All exceptions inherit WorkflowError")
