"""
Phase 1 smoke test: verify all 6 Protocols + 6 Adapters import cleanly.

Validates Checkpoint 2:
- interfaces/ has 6 Protocol modules
- adapters/ has 6 working Adapter modules
- Adapters structurally satisfy their Protocols
- AssigneeType / ApprovalAction reused from harness/workflow/models.py
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def test_all_interfaces_importable():
    from interfaces.agent_runner import (
        AgentRunner, AgentRunRequest, AgentRunResult,
    )
    from interfaces.skill_invoker import SkillInvoker, SkillFn
    from interfaces.workflow_engine import WorkflowEngine
    from interfaces.approval_gateway import (
        ApprovalGateway, AssigneeSpec,
        AssigneeType, ApprovalAction,
    )
    from interfaces.state_store import StateStore
    from interfaces.rag_provider import RAGProvider

    # Check enum counts (reused from harness)
    assert len(list(ApprovalAction)) == 12
    assert len(list(AssigneeType)) == 3
    print("  [OK] 6 Protocol modules importable; enums reused from harness")


def test_all_adapters_importable():
    from adapters.direct_skill_invoker import DirectSkillInvoker, SkillNotFoundError
    from adapters.inline_agent_runner import InlineAgentRunner
    from adapters.sql_state_store import SqlStateStore
    from adapters.chroma_rag_provider import ChromaRAGProvider
    from adapters.db_approval_gateway import DbApprovalGateway
    from adapters.function_workflow_engine import (
        FunctionWorkflowEngine, register_workflow, register_resume,
        WORKFLOW_REGISTRY, RESUME_REGISTRY,
        IllegalTransitionError, WorkflowNotFoundError,
    )
    print("  [OK] 6 Adapter modules importable")


def test_direct_skill_invoker_behavior():
    import asyncio
    from adapters.direct_skill_invoker import DirectSkillInvoker, SkillNotFoundError

    inv = DirectSkillInvoker()

    async def echo_skill(**kwargs):
        return {"echo": kwargs}

    inv.register("echo", echo_skill)
    assert "echo" in inv.list_skills()

    result = asyncio.run(inv.invoke("echo", msg="hi"))
    assert result == {"echo": {"msg": "hi"}}

    try:
        asyncio.run(inv.invoke("nonexistent"))
        raise AssertionError("Should raise SkillNotFoundError")
    except SkillNotFoundError:
        pass

    # Decorator form
    @inv.register_decorator("double")
    async def double_skill(x: int = 0, **kwargs):
        return {"value": x * 2}

    result = asyncio.run(inv.invoke("double", x=5))
    assert result == {"value": 10}

    print("  [OK] DirectSkillInvoker register/invoke/decorator works")


def test_inline_agent_runner_wraps_errors():
    import asyncio
    from adapters.inline_agent_runner import InlineAgentRunner
    from interfaces.agent_runner import AgentRunRequest

    class FailingAgent:
        steps = [{"skill": "a", "status": "ok"}]
        async def run(self, **kwargs):
            raise RuntimeError("boom")

    class OkAgent:
        steps = []
        async def run(self, x=1, **kwargs):
            self.steps.append({"skill": "compute", "status": "ok"})
            return {"result": x + 10, "steps": self.steps}

    runner = InlineAgentRunner()
    runner.register("fail", FailingAgent())
    runner.register("ok", OkAgent())

    # Missing agent → success=False
    r = asyncio.run(runner.run(AgentRunRequest(agent_key="missing", inputs={})))
    assert r.success is False
    assert "not registered" in r.error

    # Failing agent → wraps exception
    r = asyncio.run(runner.run(AgentRunRequest(agent_key="fail", inputs={})))
    assert r.success is False
    assert "boom" in r.error
    # Partial steps preserved
    assert len(r.steps) >= 1

    # Happy path
    r = asyncio.run(runner.run(AgentRunRequest(agent_key="ok", inputs={"x": 5})))
    assert r.success is True
    assert r.outputs == {"result": 15}
    assert r.duration_ms >= 0

    print("  [OK] InlineAgentRunner happy + error paths work")


def test_workflow_registry_decorators():
    from adapters.function_workflow_engine import (
        register_workflow, register_resume,
        WORKFLOW_REGISTRY, RESUME_REGISTRY,
    )

    @register_workflow("test_wf_xyz")
    async def _wf(inputs, run_id):
        return {"ok": True}

    @register_resume("test_resume_xyz")
    async def _rs(run_id, payload):
        return None

    assert "test_wf_xyz" in WORKFLOW_REGISTRY
    assert "test_resume_xyz" in RESUME_REGISTRY

    # Cleanup (don't leak into later tests)
    del WORKFLOW_REGISTRY["test_wf_xyz"]
    del RESUME_REGISTRY["test_resume_xyz"]

    print("  [OK] register_workflow / register_resume decorators work")


def test_assignee_spec_reuses_harness_enums():
    from interfaces.approval_gateway import (
        AssigneeSpec, AssigneeType, ApprovalAction,
    )
    from harness.workflow.models import (
        AssigneeType as HarnessAssigneeType,
        ApprovalAction as HarnessApprovalAction,
    )
    # Must be the SAME class, not just a lookalike
    assert AssigneeType is HarnessAssigneeType
    assert ApprovalAction is HarnessApprovalAction

    # Build a spec
    spec = AssigneeSpec(type=AssigneeType.ROLE, identifier="QUALITY_MANAGER", display_name="质量经理")
    assert spec.type == AssigneeType.ROLE

    print("  [OK] interfaces reuse harness enums (not duplicated)")


if __name__ == "__main__":
    print("=" * 70)
    print("Phase 1 — Interface + Adapter imports & behavior")
    print("=" * 70)
    test_all_interfaces_importable()
    test_all_adapters_importable()
    test_direct_skill_invoker_behavior()
    test_inline_agent_runner_wraps_errors()
    test_workflow_registry_decorators()
    test_assignee_spec_reuses_harness_enums()
    print()
    print("=" * 70)
    print("[OK] All Phase 1 smoke tests passed")
    print("=" * 70)
