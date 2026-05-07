"""
Phase B smoke test: PersistenceManager round-trip against real MySQL.

Validates Checkpoint 2:
- Definition save/load/deactivate
- Instance create/load/status update/context flush
- Lease acquire/renew/release + mutex behavior
- Node execution save (unique execution_id) + update
- Approval record append + task upsert + pending query
- State event append + list
- find_resumable_instances

Requirements: REQ-001, REQ-021~026, REQ-030, REQ-031, REQ-058

Run:
    python backend/tests/workflow/test_phase_b_persistence.py
"""
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

# Ensure backend/ is importable and .env is loaded
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from harness.workflow.errors import DuplicateDefinitionError, InstanceNotFoundError
from harness.workflow.models import (
    ApprovalAction,
    ApprovalRecord,
    AssigneeSpec,
    AssigneeType,
    CallKind,
    NodeStatus,
    NodeType,
    TaskNodeDef,
    WorkflowContext,
    WorkflowDefinition,
    WorkflowStatus,
)
from harness.workflow.persistence import PersistenceManager


def _build_test_definition(key: str, version: int = 1) -> WorkflowDefinition:
    return WorkflowDefinition(
        key=key,
        version=version,
        name=f"Test Workflow {key}",
        description="Phase B smoke test",
        start_node="n1",
        nodes=[
            TaskNodeDef(
                id="n1",
                name="First Task",
                call_kind=CallKind.TOOL,
                target="noop_tool",
            ),
        ],
        edges=[],
    )


def test_definition_crud(pm: PersistenceManager) -> None:
    print("\n[TEST] Definition CRUD")
    key = f"phase_b_test_{uuid.uuid4().hex[:8]}"

    # 1) Save new definition
    defn = _build_test_definition(key, version=1)
    def_id = pm.save_definition(defn)
    assert def_id > 0, "definition_id should be positive"
    print(f"  [OK] saved definition id={def_id}")

    # 2) Duplicate (key, version) should raise
    try:
        pm.save_definition(defn)
        raise AssertionError("Expected DuplicateDefinitionError")
    except DuplicateDefinitionError:
        print("  [OK] duplicate (key, version) correctly rejected")

    # 3) Load by id
    loaded = pm.load_definition(def_id)
    assert loaded.key == key
    assert loaded.nodes[0].id == "n1"
    print("  [OK] load_definition by id works")

    # 4) Load by key (latest)
    loaded_id, loaded2 = pm.load_definition_by_key(key)
    assert loaded_id == def_id
    assert loaded2.version == 1
    print("  [OK] load_definition_by_key (latest) works")

    # 5) Add a v2 and verify latest selection
    defn_v2 = _build_test_definition(key, version=2)
    v2_id = pm.save_definition(defn_v2)
    latest_id, latest_def = pm.load_definition_by_key(key)
    assert latest_id == v2_id, "Latest active should be v2"
    print("  [OK] version selection picks latest active")

    # 6) Deactivate v2 - latest should fall back to v1
    pm.deactivate_definition(v2_id)
    latest_id2, latest_def2 = pm.load_definition_by_key(key)
    assert latest_id2 == def_id, "After deactivating v2, latest should be v1"
    print("  [OK] deactivate_definition works (v2 hidden, falls back to v1)")


def test_instance_and_context(pm: PersistenceManager) -> tuple[int, uuid.UUID]:
    print("\n[TEST] Instance + Context")
    key = f"phase_b_inst_{uuid.uuid4().hex[:8]}"
    def_id = pm.save_definition(_build_test_definition(key))

    now = datetime.utcnow()
    instance_id = uuid.uuid4()
    ctx = WorkflowContext(
        instance_id=instance_id,
        workflow_key=key,
        version=1,
        inputs={"x": 42},
        outputs={},
        node_statuses={},
        created_at=now,
        updated_at=now,
    )

    # Create
    created_id = pm.create_instance(
        definition_id=def_id,
        workflow_key=key,
        version=1,
        inputs={"x": 42},
        context=ctx,
        trigger_user="alice",
    )
    assert created_id == instance_id
    print(f"  [OK] created instance {instance_id}")

    # Load
    inst = pm.load_instance(instance_id)
    assert inst.workflow_key == key
    assert inst.trigger_user == "alice"
    assert inst.status == WorkflowStatus.PENDING
    print("  [OK] load_instance works")

    # Context round-trip
    loaded_ctx = pm.load_context(instance_id)
    assert loaded_ctx.inputs == {"x": 42}
    assert loaded_ctx.instance_id == instance_id
    print("  [OK] load_context round-trip matches")

    # Update context (apply a node output)
    ctx.apply_node_output("n1", {"result": "done"})
    pm.update_instance_context(instance_id, ctx)

    loaded_ctx2 = pm.load_context(instance_id)
    assert loaded_ctx2.outputs == {"n1": {"result": "done"}}
    assert loaded_ctx2.node_statuses.get("n1") == NodeStatus.COMPLETED
    print("  [OK] update_instance_context + node output persisted")

    # Update status
    pm.update_instance_status(instance_id, WorkflowStatus.RUNNING)
    inst2 = pm.load_instance(instance_id)
    assert inst2.status == WorkflowStatus.RUNNING
    print("  [OK] update_instance_status works")

    # Non-existent instance
    try:
        pm.load_instance(uuid.uuid4())
        raise AssertionError("Expected InstanceNotFoundError")
    except InstanceNotFoundError:
        print("  [OK] non-existent instance raises InstanceNotFoundError")

    return def_id, instance_id


def test_lease_mutex(pm: PersistenceManager, instance_id: uuid.UUID) -> None:
    print("\n[TEST] Lease mutex (REQ-025, P11)")

    # Process A acquires
    assert pm.try_acquire_lease(instance_id, owner="processA", ttl_seconds=60) is True
    print("  [OK] processA acquired lease")

    # Process B cannot acquire while A holds
    assert pm.try_acquire_lease(instance_id, owner="processB", ttl_seconds=60) is False
    print("  [OK] processB denied (A still holds)")

    # A renews
    assert pm.renew_lease(instance_id, owner="processA", ttl_seconds=120) is True
    # B cannot renew
    assert pm.renew_lease(instance_id, owner="processB", ttl_seconds=120) is False
    print("  [OK] renew_lease only works for current owner")

    # A releases
    assert pm.release_lease(instance_id, owner="processA") is True
    # Now B can acquire
    assert pm.try_acquire_lease(instance_id, owner="processB", ttl_seconds=60) is True
    print("  [OK] after release, another owner can acquire")

    # Clean up
    pm.release_lease(instance_id, owner="processB")


def test_node_execution_idempotency(pm: PersistenceManager, instance_id: uuid.UUID) -> None:
    print("\n[TEST] Node execution uniqueness (REQ-024, P3)")

    execution_id = str(uuid.uuid4())

    # First insert succeeds
    ok = pm.save_node_execution(
        instance_id=instance_id,
        node_id="n1",
        node_type=NodeType.TASK,
        execution_id=execution_id,
        status=NodeStatus.RUNNING,
    )
    assert ok is True
    print("  [OK] first save_node_execution succeeded")

    # Second insert with same execution_id returns False
    ok2 = pm.save_node_execution(
        instance_id=instance_id,
        node_id="n1",
        node_type=NodeType.TASK,
        execution_id=execution_id,
        status=NodeStatus.RUNNING,
    )
    assert ok2 is False
    print("  [OK] duplicate execution_id correctly returns False (no exception)")

    # Update the first execution
    pm.update_node_execution(
        execution_id,
        status=NodeStatus.COMPLETED,
        output={"result": 123},
    )
    print("  [OK] update_node_execution works")


def test_approval_records_and_tasks(pm: PersistenceManager, instance_id: uuid.UUID) -> None:
    print("\n[TEST] Approval records & tasks (REQ-027, REQ-030, REQ-031)")

    # Upsert a pending task
    assignee = AssigneeSpec(type=AssigneeType.USER, identifier="bob")
    pm.upsert_approval_task(
        instance_id=instance_id,
        node_id="approval_1",
        assignee=assignee,
        status="pending",
        due_at=datetime.utcnow() + timedelta(hours=1),
    )
    print("  [OK] upsert_approval_task pending")

    # List pending
    tasks = pm.list_pending_tasks(AssigneeType.USER, "bob")
    assert len(tasks) == 1
    assert tasks[0]["node_id"] == "approval_1"
    print(f"  [OK] list_pending_tasks returns {len(tasks)} tasks")

    # Insert an approval record (append-only)
    record = ApprovalRecord(
        instance_id=instance_id,
        node_id="approval_1",
        action=ApprovalAction.APPROVE,
        actor_id="bob",
        assignee_snapshot=assignee,
        comment="方案可行",
        created_at=datetime.utcnow(),
    )
    pm.insert_approval_record(record)
    print("  [OK] insert_approval_record appended")

    # Complete the task
    pm.complete_approval_task(
        instance_id=instance_id,
        node_id="approval_1",
        action=ApprovalAction.APPROVE,
        actor_id="bob",
    )

    # After completion, pending list should be empty for bob
    tasks2 = pm.list_pending_tasks(AssigneeType.USER, "bob")
    assert all(t["node_id"] != "approval_1" for t in tasks2)
    print("  [OK] completed task no longer in pending list")

    # Timeout scan should not find the just-created task (future due_at)
    timed_out = pm.find_timed_out_tasks()
    node_ids = {t["node_id"] for t in timed_out}
    assert "approval_1" not in node_ids
    print("  [OK] find_timed_out_tasks skips future due_at")


def test_state_events(pm: PersistenceManager, instance_id: uuid.UUID) -> None:
    print("\n[TEST] State events (REQ-020, REQ-058)")

    # Append several events
    pm.append_state_event(
        instance_id,
        event_type="workflow_started",
        to_status=WorkflowStatus.RUNNING.value,
    )
    pm.append_state_event(
        instance_id,
        event_type="node_completed",
        node_id="n1",
        from_status=NodeStatus.RUNNING.value,
        to_status=NodeStatus.COMPLETED.value,
        payload={"output_size": 42},
    )
    pm.append_state_event(
        instance_id,
        event_type="workflow_completed",
        from_status=WorkflowStatus.RUNNING.value,
        to_status=WorkflowStatus.COMPLETED.value,
    )

    events = pm.list_state_events(instance_id)
    assert len(events) >= 3
    print(f"  [OK] list_state_events returned {len(events)} events")

    # Filtered list
    node_events = pm.list_state_events(instance_id, event_type="node_completed")
    assert len(node_events) == 1
    assert node_events[0]["node_id"] == "n1"
    print("  [OK] filtered list by event_type works")


def test_find_resumable(pm: PersistenceManager, instance_id: uuid.UUID) -> None:
    print("\n[TEST] find_resumable_instances (REQ-023)")

    # Instance is currently RUNNING with no lease - should be resumable
    resumable = pm.find_resumable_instances()
    assert instance_id in resumable
    print(f"  [OK] found {len(resumable)} resumable instances (incl. current)")

    # Acquire a fresh lease - should no longer be resumable
    pm.try_acquire_lease(instance_id, owner="test_process", ttl_seconds=60)
    resumable2 = pm.find_resumable_instances()
    assert instance_id not in resumable2
    print("  [OK] instance with fresh lease is NOT resumable")

    pm.release_lease(instance_id, owner="test_process")


def main() -> None:
    print("=" * 70)
    print("Phase B Persistence Tests")
    print("=" * 70)

    pm = PersistenceManager()

    test_definition_crud(pm)
    _, instance_id = test_instance_and_context(pm)
    test_lease_mutex(pm, instance_id)
    test_node_execution_idempotency(pm, instance_id)
    test_approval_records_and_tasks(pm, instance_id)
    test_state_events(pm, instance_id)
    test_find_resumable(pm, instance_id)

    print()
    print("=" * 70)
    print("[OK] All Phase B persistence tests passed")
    print("=" * 70)


if __name__ == "__main__":
    main()
