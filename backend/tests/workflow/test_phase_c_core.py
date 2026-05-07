"""
Phase C smoke test: StateMachine + Expressions + WorkflowLoader.

Validates Checkpoint 3:
- StateMachine: transitions, terminal states, illegal transitions
- Expressions: sandbox, forbidden fragments, undefined vars
- WorkflowLoader: YAML/dict loading, DAG validation, cycle detection

Requirements: REQ-007, REQ-018, REQ-019, REQ-054, REQ-060, REQ-061, REQ-068
"""
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from harness.workflow.errors import (
    CyclicGraphError,
    IllegalTransitionError,
    InvalidNodeRefError,
    SchemaValidationError,
    SecurityError,
    TemplateRenderError,
)
from harness.workflow.expressions import (
    render_bool,
    render_params,
    render_value,
)
from harness.workflow.loader import WorkflowLoader, validate_dag_acyclic
from harness.workflow.models import (
    CallKind,
    DecisionBranch,
    DecisionNodeDef,
    Edge,
    NodeStatus,
    TaskNodeDef,
    WorkflowContext,
    WorkflowDefinition,
    WorkflowStatus,
)
from harness.workflow.state_machine import StateMachine


# ---------------------------------------------------------------------------
# State Machine
# ---------------------------------------------------------------------------

def test_state_machine_workflow_transitions():
    print("\n[TEST] StateMachine workflow transitions")

    # Legal
    assert StateMachine.transition_workflow(WorkflowStatus.PENDING, WorkflowStatus.RUNNING) == WorkflowStatus.RUNNING
    assert StateMachine.transition_workflow(WorkflowStatus.RUNNING, WorkflowStatus.WAITING_APPROVAL) == WorkflowStatus.WAITING_APPROVAL
    assert StateMachine.transition_workflow(WorkflowStatus.RUNNING, WorkflowStatus.COMPLETED) == WorkflowStatus.COMPLETED
    print("  [OK] legal transitions pass")

    # Illegal - PENDING -> WAITING_APPROVAL (must go through RUNNING)
    try:
        StateMachine.transition_workflow(WorkflowStatus.PENDING, WorkflowStatus.WAITING_APPROVAL)
        raise AssertionError("Should have raised IllegalTransitionError")
    except IllegalTransitionError:
        pass
    print("  [OK] illegal transition PENDING -> WAITING_APPROVAL rejected")

    # Terminal absorbing - COMPLETED has no outgoing edges
    for target in WorkflowStatus:
        try:
            StateMachine.transition_workflow(WorkflowStatus.COMPLETED, target)
            raise AssertionError(f"Should have rejected COMPLETED -> {target}")
        except IllegalTransitionError:
            pass
    print("  [OK] terminal state COMPLETED is absorbing")

    # is_terminal helper
    assert StateMachine.is_terminal_workflow(WorkflowStatus.COMPLETED)
    assert StateMachine.is_terminal_workflow(WorkflowStatus.FAILED)
    assert StateMachine.is_terminal_workflow(WorkflowStatus.CANCELLED)
    assert not StateMachine.is_terminal_workflow(WorkflowStatus.RUNNING)
    print("  [OK] is_terminal_workflow correct")


def test_state_machine_node_transitions():
    print("\n[TEST] StateMachine node transitions")

    # Legal
    assert StateMachine.transition_node(NodeStatus.PENDING, NodeStatus.RUNNING) == NodeStatus.RUNNING
    assert StateMachine.transition_node(NodeStatus.RUNNING, NodeStatus.COMPLETED) == NodeStatus.COMPLETED
    assert StateMachine.transition_node(NodeStatus.RUNNING, NodeStatus.WAITING_APPROVAL) == NodeStatus.WAITING_APPROVAL
    assert StateMachine.transition_node(NodeStatus.WAITING_APPROVAL, NodeStatus.COMPLETED) == NodeStatus.COMPLETED
    print("  [OK] legal node transitions pass")

    # Illegal - cannot go from PENDING directly to COMPLETED
    try:
        StateMachine.transition_node(NodeStatus.PENDING, NodeStatus.COMPLETED)
        raise AssertionError("Should have raised IllegalTransitionError")
    except IllegalTransitionError:
        pass
    print("  [OK] illegal node transition rejected")

    # Terminal absorbing
    for target in NodeStatus:
        try:
            StateMachine.transition_node(NodeStatus.FAILED, target)
            raise AssertionError(f"FAILED -> {target} should be rejected")
        except IllegalTransitionError:
            pass
    print("  [OK] terminal node state FAILED is absorbing")


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------

def _make_ctx(inputs=None, outputs=None, variables=None):
    now = datetime.utcnow()
    return WorkflowContext(
        instance_id=uuid4(),
        workflow_key="test",
        version=1,
        inputs=inputs or {},
        outputs=outputs or {},
        variables=variables or {},
        created_at=now,
        updated_at=now,
    )


def test_expressions_basic_rendering():
    print("\n[TEST] Expressions - basic rendering")

    ctx = _make_ctx(
        inputs={"name": "alice"},
        outputs={"n1": {"score": 85}},
    )

    # String template
    assert render_value("Hello {{ inputs.name }}", ctx) == "Hello alice"

    # Dict with nested templates
    params = {
        "user": "{{ inputs.name }}",
        "score": "{{ outputs.n1.score }}",
        "literal": 42,
    }
    rendered = render_params(params, ctx)
    assert rendered["user"] == "alice"
    assert rendered["score"] == "85"  # Jinja returns strings
    assert rendered["literal"] == 42
    print("  [OK] basic rendering + dict + nested")

    # Boolean expression
    assert render_bool("outputs.n1.score >= 70", ctx) is True
    assert render_bool("outputs.n1.score < 50", ctx) is False
    print("  [OK] render_bool works")


def test_expressions_sandbox():
    print("\n[TEST] Expressions - sandbox (REQ-054, P9)")

    ctx = _make_ctx()

    # Forbidden fragments
    bad_templates = [
        "{{ os.system('ls') }}",
        '{{ __import__("os") }}',
        "{{ ''.__class__.__mro__ }}",
        "{{ open('/etc/passwd') }}",
        "{{ eval('1+1') }}",
    ]
    for t in bad_templates:
        try:
            render_value(t, ctx)
            raise AssertionError(f"Should have blocked: {t}")
        except (SecurityError, TemplateRenderError):
            pass
    print(f"  [OK] {len(bad_templates)} malicious templates all blocked")


def test_expressions_undefined_raises():
    print("\n[TEST] Expressions - undefined vars raise (no silent None)")

    ctx = _make_ctx()
    try:
        render_value("{{ outputs.missing.field }}", ctx)
        raise AssertionError("Should have raised TemplateRenderError")
    except TemplateRenderError:
        pass
    print("  [OK] undefined variable raises TemplateRenderError")


# ---------------------------------------------------------------------------
# WorkflowLoader + DAG validation
# ---------------------------------------------------------------------------

def _simple_linear_dag_dict():
    return {
        "key": "linear_test",
        "name": "Linear Test",
        "start_node": "a",
        "nodes": [
            {"id": "a", "name": "A", "type": "task",
             "call_kind": "tool", "target": "noop"},
            {"id": "b", "name": "B", "type": "task",
             "call_kind": "tool", "target": "noop"},
            {"id": "c", "name": "C", "type": "task",
             "call_kind": "tool", "target": "noop"},
        ],
        "edges": [
            {"from": "a", "to": "b"},
            {"from": "b", "to": "c"},
        ],
    }


def test_loader_linear_dag():
    print("\n[TEST] WorkflowLoader - linear DAG")

    defn = WorkflowLoader.from_dict(_simple_linear_dag_dict())
    assert defn.key == "linear_test"
    assert len(defn.nodes) == 3
    # end_nodes inferred as ['c']
    assert defn.end_nodes == ["c"]
    print("  [OK] linear DAG loaded + end_node inferred")


def test_loader_detects_cycle():
    print("\n[TEST] WorkflowLoader - cycle detection (REQ-007, P1)")

    cyclic = _simple_linear_dag_dict()
    cyclic["edges"].append({"from": "c", "to": "a"})  # create cycle

    try:
        WorkflowLoader.from_dict(cyclic)
        raise AssertionError("Should have raised CyclicGraphError")
    except CyclicGraphError as e:
        assert len(e.cycle) > 0, "Cycle should report node list"
        print(f"  [OK] cycle detected: {e.cycle}")


def test_loader_self_loop():
    print("\n[TEST] WorkflowLoader - self-loop is a cycle")

    spec = _simple_linear_dag_dict()
    spec["edges"].append({"from": "b", "to": "b"})  # self-loop

    try:
        WorkflowLoader.from_dict(spec)
        raise AssertionError("Self-loop should be rejected")
    except CyclicGraphError:
        pass
    print("  [OK] self-loop rejected")


def test_loader_invalid_node_ref():
    print("\n[TEST] WorkflowLoader - invalid node ref in edge")

    spec = _simple_linear_dag_dict()
    spec["edges"].append({"from": "a", "to": "nonexistent"})

    try:
        WorkflowLoader.from_dict(spec)
        raise AssertionError("Should have raised InvalidNodeRefError")
    except InvalidNodeRefError:
        pass
    print("  [OK] invalid node ref rejected")


def test_loader_duplicate_node_id():
    print("\n[TEST] WorkflowLoader - duplicate node id")

    spec = _simple_linear_dag_dict()
    spec["nodes"].append({
        "id": "a",  # duplicate!
        "name": "A2",
        "type": "task",
        "call_kind": "tool",
        "target": "noop",
    })

    try:
        WorkflowLoader.from_dict(spec)
        raise AssertionError("Should have raised SchemaValidationError")
    except SchemaValidationError:
        pass
    print("  [OK] duplicate node id rejected")


def test_loader_decision_node_with_branches():
    print("\n[TEST] WorkflowLoader - decision node with branches")

    spec = {
        "key": "with_decision",
        "name": "Decision Test",
        "start_node": "a",
        "nodes": [
            {"id": "a", "name": "Start", "type": "task",
             "call_kind": "tool", "target": "noop"},
            {"id": "d", "name": "Decide", "type": "decision",
             "branches": [
                 {"condition": "{{ outputs.a.ok }}", "next": "pass"},
             ],
             "default_next": "fail"},
            {"id": "pass", "name": "Pass", "type": "task",
             "call_kind": "tool", "target": "noop"},
            {"id": "fail", "name": "Fail", "type": "task",
             "call_kind": "tool", "target": "noop"},
        ],
        "edges": [
            {"from": "a", "to": "d"},
        ],
    }

    defn = WorkflowLoader.from_dict(spec)
    assert len(defn.nodes) == 4
    print("  [OK] decision node workflow loaded")


def test_loader_topological_order():
    print("\n[TEST] WorkflowLoader - topological ordering")

    defn = WorkflowLoader.from_dict(_simple_linear_dag_dict())
    topo = validate_dag_acyclic(defn.nodes, defn.edges)
    # `a` must come before `b` which must come before `c`
    assert topo.index("a") < topo.index("b") < topo.index("c")
    print(f"  [OK] topological order: {topo}")


def main():
    print("=" * 70)
    print("Phase C Core Engine Tests")
    print("=" * 70)

    test_state_machine_workflow_transitions()
    test_state_machine_node_transitions()
    test_expressions_basic_rendering()
    test_expressions_sandbox()
    test_expressions_undefined_raises()
    test_loader_linear_dag()
    test_loader_detects_cycle()
    test_loader_self_loop()
    test_loader_invalid_node_ref()
    test_loader_duplicate_node_id()
    test_loader_decision_node_with_branches()
    test_loader_topological_order()

    print()
    print("=" * 70)
    print("[OK] All Phase C core engine tests passed")
    print("=" * 70)


if __name__ == "__main__":
    main()
