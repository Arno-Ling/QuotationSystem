"""
Pydantic data models for the Harness Workflow Engine.

Contains:
- Enums (WorkflowStatus, NodeStatus, NodeType, ErrorStrategy, AssigneeType, ApprovalAction)
- Node definitions (TaskNodeDef, DecisionNodeDef, ParallelNodeDef, ApprovalNodeDef, LoopNodeDef)
- Workflow definitions (Edge, WorkflowDefinition, RetryPolicy)
- Runtime models (WorkflowContext, NodeResult, ApprovalRecord, AssigneeSpec, WorkflowInstance)
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class WorkflowStatus(str, Enum):
    """Workflow instance lifecycle states.

    Transitions are enforced by StateMachine.
    """
    PENDING = "pending"                    # 待分析
    RUNNING = "running"                    # 分析中
    WAITING_APPROVAL = "waiting_approval"  # 待审批
    EXECUTING = "executing"                # 审批通过后的执行阶段
    COMPLETED = "completed"                # 完成 (terminal)
    FAILED = "failed"                      # 失败 (terminal)
    SUSPENDED = "suspended"                # 人工挂起
    CANCELLED = "cancelled"                # 取消 (terminal)


class NodeStatus(str, Enum):
    """Node execution lifecycle states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"                # terminal
    FAILED = "failed"                      # terminal
    SKIPPED = "skipped"                    # terminal
    WAITING_APPROVAL = "waiting_approval"


class NodeType(str, Enum):
    """Supported node types."""
    TASK = "task"
    DECISION = "decision"
    PARALLEL = "parallel"
    APPROVAL = "approval"
    LOOP = "loop"


class ErrorStrategy(str, Enum):
    """How to handle a node failure."""
    FAIL_WORKFLOW = "fail_workflow"    # Entire workflow fails
    SKIP = "skip"                      # Skip the node, continue
    RETRY = "retry"                    # Honor retry_policy
    GO_TO = "go_to"                    # Jump to a specified node


class JoinStrategy(str, Enum):
    """ParallelNode completion criterion."""
    ALL = "all"
    ANY = "any"
    MAJORITY = "majority"


# --- Approval-related enums

class AssigneeType(str, Enum):
    """How an approval task is assigned."""
    USER = "user"                        # Single user account
    SHARED_ACCOUNT = "shared_account"    # Shared account (multiple real users)
    ROLE = "role"                        # Role (multiple members)


class ApprovalAction(str, Enum):
    """12 approval actions supported by the engine.

    Terminal actions for a node: APPROVE / REJECT / REJECT_RETURN / WITHDRAW.
    Non-terminal (flow/edit): SAVE / SUBMIT / RETRIEVE / DELEGATE / FORWARD.
    Informational (no state change): READ / ACK.
    Extension slot: CUSTOM.
    """
    SAVE = "save"                      # 保存 (draft)
    SUBMIT = "submit"                  # 提交
    RETRIEVE = "retrieve"              # 取回
    APPROVE = "approve"                # 审核通过
    REJECT_RETURN = "reject_return"    # 退回
    REJECT = "reject"                  # 拒绝
    WITHDRAW = "withdraw"              # 撤销
    READ = "read"                      # 阅示
    ACK = "ack"                        # 阅批
    DELEGATE = "delegate"              # 委托
    FORWARD = "forward"                # 直送
    CUSTOM = "custom"                  # 业务自定义扩展

    @classmethod
    def terminal_actions(cls) -> set["ApprovalAction"]:
        """Actions that terminate the approval node."""
        return {cls.APPROVE, cls.REJECT, cls.REJECT_RETURN, cls.WITHDRAW}


class TimeoutStrategy(str, Enum):
    """How to handle an approval timeout."""
    AUTO_APPROVE = "auto_approve"
    AUTO_REJECT = "auto_reject"
    ESCALATE = "escalate"
    FAIL = "fail"


class CallKind(str, Enum):
    """TaskNode dispatch target."""
    TOOL = "tool"
    AGENT = "agent"
    SKILL = "skill"
    CALLABLE = "callable"    # Python callable (code-defined only, not YAML)


# ---------------------------------------------------------------------------
# Retry / Edge primitives
# ---------------------------------------------------------------------------

class RetryPolicy(BaseModel):
    """Retry policy for node execution."""
    max_attempts: int = Field(default=3, ge=1, le=10)
    backoff_seconds: float = Field(default=1.0, ge=0)
    backoff_multiplier: float = Field(default=2.0, ge=1.0)
    retry_on: list[str] = Field(
        default_factory=list,
        description="Exception class names to retry on; empty = retry on all",
    )
    go_to_node: Optional[str] = Field(
        default=None,
        description="Only used when ErrorStrategy.GO_TO; target node id",
    )


class Edge(BaseModel):
    """DAG edge from one node to another.

    Uses `from_` field name with alias `from` to avoid Python keyword conflict.
    `condition` is optional and only used for DecisionNode out-edges.
    """
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(..., alias="from")
    to: str
    condition: Optional[str] = None  # Jinja2 expression, for Decision edges


# ---------------------------------------------------------------------------
# Node definitions (declarative)
# ---------------------------------------------------------------------------

class _BaseNodeDef(BaseModel):
    """Shared fields for all node definitions."""
    id: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=255)
    depends_on: list[str] = Field(default_factory=list)
    retry_policy: Optional[RetryPolicy] = None
    timeout_seconds: Optional[int] = Field(default=300, ge=1, le=86400)
    on_error: ErrorStrategy = ErrorStrategy.FAIL_WORKFLOW


class TaskNodeDef(_BaseNodeDef):
    """Task node: dispatches to a Tool / Agent / Skill / callable."""
    type: Literal[NodeType.TASK] = NodeType.TASK
    call_kind: CallKind
    target: str = Field(
        ...,
        description="Tool name / agent_id / 'module.path:ClassName' / callable ref",
    )
    params: dict[str, Any] = Field(default_factory=dict)
    output_key: Optional[str] = Field(
        default=None,
        description="Key in context.outputs; defaults to node id",
    )


class DecisionBranch(BaseModel):
    """One conditional branch in a DecisionNode."""
    condition: str = Field(..., description="Jinja2 expression returning bool")
    next: str = Field(..., description="Target node id when condition is true")


class DecisionNodeDef(_BaseNodeDef):
    """Decision node: evaluates branches in order, first match wins."""
    type: Literal[NodeType.DECISION] = NodeType.DECISION
    branches: list[DecisionBranch] = Field(default_factory=list)
    default_next: Optional[str] = None

    @field_validator("branches")
    @classmethod
    def _at_least_one_branch_or_default(cls, v: list[DecisionBranch]) -> list[DecisionBranch]:
        # Validation of "branches or default_next" is done at WorkflowDefinition level
        return v


class ParallelNodeDef(_BaseNodeDef):
    """Parallel node: executes branch children concurrently with asyncio.gather."""
    type: Literal[NodeType.PARALLEL] = NodeType.PARALLEL
    branches: list[str] = Field(..., min_length=1, description="Child node ids")
    join_strategy: JoinStrategy = JoinStrategy.ALL
    fail_fast: bool = True


class AssigneeSpec(BaseModel):
    """Approval assignee specification."""
    type: AssigneeType
    identifier: str = Field(..., min_length=1, max_length=128)
    display_name: Optional[str] = None


class ApprovalNodeDef(_BaseNodeDef):
    """Approval node: suspends workflow, waits for external action."""
    type: Literal[NodeType.APPROVAL] = NodeType.APPROVAL
    assignees: list[AssigneeSpec] = Field(..., min_length=1)
    allowed_actions: list[ApprovalAction] = Field(
        default_factory=lambda: [ApprovalAction.APPROVE, ApprovalAction.REJECT]
    )
    timeout_seconds: Optional[int] = Field(default=None, ge=1)
    on_timeout: TimeoutStrategy = TimeoutStrategy.AUTO_REJECT
    escalate_to: Optional[list[AssigneeSpec]] = None
    next_on_approve: str
    next_on_reject: Optional[str] = None


class LoopNodeDef(_BaseNodeDef):
    """Loop node: repeats body either by iterator or condition (P2)."""
    type: Literal[NodeType.LOOP] = NodeType.LOOP
    body: list[str] = Field(..., min_length=1, description="Body node ids")
    iterator_expr: Optional[str] = Field(
        default=None,
        description="Jinja2 expression returning iterable; takes precedence over condition_expr",
    )
    condition_expr: Optional[str] = Field(
        default=None,
        description="Jinja2 boolean expression; loop while true",
    )
    max_iterations: int = Field(default=100, ge=1, le=10000)

    @field_validator("condition_expr")
    @classmethod
    def _one_of_iterator_or_condition(cls, v: Optional[str], info: Any) -> Optional[str]:
        iterator = info.data.get("iterator_expr")
        if iterator is None and v is None:
            raise ValueError("LoopNodeDef requires either iterator_expr or condition_expr")
        return v


# Union type for all node definitions (discriminator on `type` field)
NodeDef = Union[
    TaskNodeDef,
    DecisionNodeDef,
    ParallelNodeDef,
    ApprovalNodeDef,
    LoopNodeDef,
]


# ---------------------------------------------------------------------------
# Workflow definition
# ---------------------------------------------------------------------------

class WorkflowDefinition(BaseModel):
    """Declarative workflow definition (DAG)."""
    key: str = Field(..., min_length=1, max_length=128, description="Business unique key")
    version: int = Field(default=1, ge=1)
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""

    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)

    nodes: list[NodeDef] = Field(..., min_length=1)
    edges: list[Edge] = Field(default_factory=list)

    start_node: str
    end_nodes: list[str] = Field(default_factory=list)

    global_timeout_seconds: Optional[int] = Field(default=None, ge=1)
    max_concurrent_nodes: int = Field(default=8, ge=1, le=64)

    model_config = ConfigDict(populate_by_name=True)


# ---------------------------------------------------------------------------
# Runtime models
# ---------------------------------------------------------------------------

class WorkflowContext(BaseModel):
    """Runtime data bus threaded through a workflow execution.

    Serialization is done via `model_dump_json()` / `model_validate_json()`;
    round-trip equivalence is guaranteed for Property P4.
    """
    instance_id: UUID
    workflow_key: str
    version: int = 1
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)
    node_statuses: dict[str, NodeStatus] = Field(default_factory=dict)
    node_attempts: dict[str, int] = Field(default_factory=dict)
    current_nodes: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    def apply_node_output(self, node_id: str, output: Any, output_key: Optional[str] = None) -> None:
        """Record a node's output and mark it as completed."""
        key = output_key or node_id
        self.outputs[key] = output
        self.node_statuses[node_id] = NodeStatus.COMPLETED
        self.updated_at = datetime.utcnow()

    def mark_node_status(self, node_id: str, status: NodeStatus) -> None:
        """Mark a node's status without changing outputs."""
        self.node_statuses[node_id] = status
        self.updated_at = datetime.utcnow()


class NodeResult(BaseModel):
    """Result of a single node execution attempt."""
    node_id: str
    status: NodeStatus
    output: Any = None
    error: Optional[str] = None
    attempt: int = Field(default=1, ge=1)
    started_at: datetime
    ended_at: datetime


class ApprovalRecord(BaseModel):
    """A single approval action record (append-only)."""
    id: UUID = Field(default_factory=uuid4)
    instance_id: UUID
    node_id: str
    action: ApprovalAction
    actor_id: str = Field(..., max_length=128)
    assignee_snapshot: AssigneeSpec
    comment: Optional[str] = Field(default=None, max_length=4096)
    delegate_to: Optional[str] = Field(default=None, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class WorkflowInstance(BaseModel):
    """Workflow instance runtime representation."""
    id: UUID
    definition_id: int
    workflow_key: str
    version: int
    status: WorkflowStatus
    trigger_source: Optional[str] = None
    trigger_user: Optional[str] = None
    error_message: Optional[str] = None
    lease_owner: Optional[str] = None
    lease_expires_at: Optional[datetime] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class InstanceStatusView(BaseModel):
    """View returned by `WorkflowEngine.get_status()`.

    Combines instance metadata with per-node status snapshots.
    """
    instance_id: UUID
    workflow_key: str
    version: int
    status: WorkflowStatus
    current_nodes: list[str] = Field(default_factory=list)
    node_statuses: dict[str, NodeStatus] = Field(default_factory=dict)
    started_at: datetime
    ended_at: Optional[datetime] = None
    error_message: Optional[str] = None
