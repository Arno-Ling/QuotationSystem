"""
Phase C End-to-End MVP Test.

This test demonstrates the core claim of the MVP (per spec):
    "YAML 加载 → DAG 校验 → 线性执行 Task 节点 → 持久化 → 结果查询"

The dispatcher is a stub that simulates different Task node logic, so the
test runs fully offline (no real Tool/Agent/Skill needed).

Checkpoint 3 acceptance criteria:
- YAML loads into a validated WorkflowDefinition
- Linear DAG of 3 Task nodes executes in order
- Each node's output is persisted to context.outputs
- State events are recorded for each transition
- Final query via load_instance returns COMPLETED

Requirements: REQ-005, REQ-020, REQ-022, REQ-024
"""
import asyncio
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from harness.workflow.context import create_initial_context
from harness.workflow.executor import DAGExecutor
from harness.workflow.loader import WorkflowLoader
from harness.workflow.models import NodeStatus, TaskNodeDef, WorkflowStatus
from harness.workflow.persistence import PersistenceManager


# ---------------------------------------------------------------------------
# Stub dispatcher for Task nodes (MVP: all call_kind=tool go through here)
# ---------------------------------------------------------------------------

STUB_TOOLS = {
    "validate_input": lambda params, ctx: {
        "ok": True,
        "description": f"Validated input: {params.get('exception_id', 'unknown')}",
    },
    "analyze_tool": lambda params, ctx: {
        "root_cause": "simulated_cause",
        "severity": "major",
        "confidence": 85,
    },
    "write_report": lambda params, ctx: {
        "report_path": f"/tmp/report_{params.get('exception_id')}.pdf",
        "saved": True,
    },
}


async def stub_dispatcher(node, params, ctx):
    """Simulate node execution; only handles TaskNode(call_kind=tool)."""
    if not isinstance(node, TaskNodeDef):
        raise NotImplementedError(f"MVP dispatcher only handles TaskNode, got {type(node)}")

    fn = STUB_TOOLS.get(node.target)
    if fn is None:
        raise ValueError(f"Stub has no tool: {node.target}")

    # Small simulated delay so we can see concurrency
    await asyncio.sleep(0.01)
    return fn(params, ctx)


# ---------------------------------------------------------------------------
# Test workflow YAML (3-node linear)
# ---------------------------------------------------------------------------

LINEAR_WORKFLOW_YAML = """
key: mvp_linear_test
version: 1
name: MVP Linear Test Workflow
description: 3-node linear DAG for Phase C E2E validation
start_node: validate

nodes:
  - id: validate
    name: Input Validation
    type: task
    call_kind: tool
    target: validate_input
    params:
      exception_id: "{{ inputs.exception_id }}"

  - id: analyze
    name: Analysis
    type: task
    depends_on: [validate]
    call_kind: tool
    target: analyze_tool
    params:
      description: "{{ outputs.validate.description }}"

  - id: report
    name: Generate Report
    type: task
    depends_on: [analyze]
    call_kind: tool
    target: write_report
    params:
      exception_id: "{{ inputs.exception_id }}"
      severity: "{{ outputs.analyze.severity }}"

end_nodes: [report]
"""


async def run_mvp_test():
    print("=" * 70)
    print("Phase C - End-to-End MVP Test")
    print("=" * 70)

    pm = PersistenceManager()

    # 1. Write YAML to a temp file and load
    print("\n[STEP 1] Load workflow from YAML")
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8",
    ) as f:
        f.write(LINEAR_WORKFLOW_YAML)
        yaml_path = f.name

    definition = WorkflowLoader.from_yaml_file(yaml_path)
    print(f"  [OK] Loaded: {definition.key} v{definition.version}")
    print(f"       {len(definition.nodes)} nodes, {len(definition.edges)} edges")
    print(f"       start_node = {definition.start_node}")
    print(f"       end_nodes = {definition.end_nodes}")

    # 2. Persist the definition
    print("\n[STEP 2] Persist definition + create instance")
    # Use a unique key per run to avoid duplicate
    definition.key = f"mvp_linear_test_{uuid4().hex[:8]}"
    def_id = pm.save_definition(definition)
    print(f"  [OK] Definition saved, id={def_id}")

    # 3. Create instance
    instance_id = uuid4()
    context = create_initial_context(
        instance_id=instance_id,
        workflow_key=definition.key,
        version=1,
        inputs={"exception_id": "EXC-MVP-001"},
    )
    pm.create_instance(
        definition_id=def_id,
        workflow_key=definition.key,
        version=1,
        inputs={"exception_id": "EXC-MVP-001"},
        context=context,
        trigger_user="test_user",
    )
    print(f"  [OK] Instance created: {instance_id}")

    # 4. Execute
    print("\n[STEP 3] Execute DAG")
    executor = DAGExecutor(persistence=pm, dispatcher=stub_dispatcher)
    result = await executor.execute(instance_id, definition, context)
    print(f"  [OK] Execution result: {result}")

    assert result.status == WorkflowStatus.COMPLETED, f"Expected COMPLETED, got {result.status}"

    # 5. Verify persistence
    print("\n[STEP 4] Verify persistence")
    loaded_instance = pm.load_instance(instance_id)
    assert loaded_instance.status == WorkflowStatus.COMPLETED
    assert loaded_instance.ended_at is not None
    print(f"  [OK] Instance.status = COMPLETED")
    print(f"       started_at = {loaded_instance.started_at}")
    print(f"       ended_at   = {loaded_instance.ended_at}")

    loaded_ctx = pm.load_context(instance_id)
    # All 3 nodes should be COMPLETED
    for node_id in ("validate", "analyze", "report"):
        assert loaded_ctx.node_statuses.get(node_id) == NodeStatus.COMPLETED, \
            f"Node {node_id} not completed: {loaded_ctx.node_statuses.get(node_id)}"
    print(f"  [OK] All 3 nodes in context.node_statuses = COMPLETED")

    # Outputs
    assert "validate" in loaded_ctx.outputs
    assert loaded_ctx.outputs["validate"]["ok"] is True
    assert loaded_ctx.outputs["analyze"]["confidence"] == 85
    assert loaded_ctx.outputs["report"]["saved"] is True
    print(f"  [OK] All node outputs persisted to context.outputs")
    print(f"       validate = {loaded_ctx.outputs['validate']}")
    print(f"       analyze  = {loaded_ctx.outputs['analyze']}")
    print(f"       report   = {loaded_ctx.outputs['report']}")

    # 6. Verify state events
    print("\n[STEP 5] Verify state events (audit log)")
    events = pm.list_state_events(instance_id)
    event_types = [e["event_type"] for e in events]
    print(f"  [OK] {len(events)} events recorded:")
    for et in event_types:
        print(f"         - {et}")

    expected_events = [
        "workflow_started",
        "node_started",
        "node_completed",  # validate
        "node_started",
        "node_completed",  # analyze
        "node_started",
        "node_completed",  # report
        "workflow_completed",
    ]
    assert event_types == expected_events, \
        f"Expected {expected_events}, got {event_types}"
    print("  [OK] Event sequence matches expected order")

    # 7. Clean up
    Path(yaml_path).unlink(missing_ok=True)

    print()
    print("=" * 70)
    print("[OK] Phase C MVP End-to-End test PASSED")
    print("=" * 70)
    print()
    print("  YAML loaded -> DAG validated -> 3 tasks executed in order")
    print("  -> outputs persisted -> state events recorded -> status COMPLETED")


if __name__ == "__main__":
    asyncio.run(run_mvp_test())
