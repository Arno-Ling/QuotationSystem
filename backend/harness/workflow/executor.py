"""
DAGExecutor - topology-aware scheduler for workflow nodes.

Responsibilities:
- Compute initial ready queue from topological sort
- Dispatch ready nodes to node-type-specific executors
- Enforce `max_concurrent_nodes` concurrency limit via asyncio.wait
- Resolve successors when a node completes (static edges + decision branches)
- Persist node status + context after each node via PersistenceManager
- Emit state events via optional CallbackManager
- Handle retries, failures, skips (per ErrorStrategy)

For the MVP (Phase C), only TaskNode via a pluggable callable is supported.
Decision / Parallel / Approval / Loop dispatch is added in Phase D/E.

Requirements: REQ-005, REQ-020, REQ-022, REQ-024, REQ-049, REQ-050, REQ-071
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional
from uuid import UUID, uuid4

from .context import create_initial_context
from .errors import (
    NodeExecutionError,
    NoMatchingBranchError,
    WorkflowError,
)
from .expressions import render_bool, render_params
from .models import (
    CallKind,
    DecisionBranch,
    DecisionNodeDef,
    Edge,
    ErrorStrategy,
    NodeDef,
    NodeStatus,
    NodeType,
    TaskNodeDef,
    WorkflowContext,
    WorkflowDefinition,
    WorkflowStatus,
)
from .persistence import PersistenceManager
from .state_machine import StateMachine

logger = logging.getLogger(__name__)


# Dispatcher signature: given rendered params + context, return any output
NodeDispatcher = Callable[[NodeDef, dict[str, Any], WorkflowContext], Awaitable[Any]]


class ExecutionResult:
    """Final result of a DAGExecutor.execute() run."""
    def __init__(
        self,
        status: WorkflowStatus,
        error: Optional[str] = None,
        failed_node: Optional[str] = None,
    ) -> None:
        self.status = status
        self.error = error
        self.failed_node = failed_node

    def __repr__(self) -> str:
        return f"<ExecutionResult status={self.status.value} failed={self.failed_node}>"


class DAGExecutor:
    """Schedules and executes nodes respecting DAG dependencies.

    The executor does NOT know how to execute specific node types - that
    is delegated to a `dispatcher` callable provided at construction.
    This decouples scheduling from business logic.
    """

    def __init__(
        self,
        persistence: PersistenceManager,
        dispatcher: NodeDispatcher,
        *,
        on_state_event: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> None:
        self.persistence = persistence
        self.dispatcher = dispatcher
        self.on_state_event = on_state_event

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    def _build_adjacency(
        self, definition: WorkflowDefinition,
    ) -> tuple[dict[str, NodeDef], dict[str, set[str]], dict[str, set[str]]]:
        """Return (id->node, successors, predecessors)."""
        nodes_by_id = {n.id: n for n in definition.nodes}
        succ: dict[str, set[str]] = {n.id: set() for n in definition.nodes}
        pred: dict[str, set[str]] = {n.id: set() for n in definition.nodes}

        for e in definition.edges:
            if e.from_ in succ and e.to in succ:
                succ[e.from_].add(e.to)
                pred[e.to].add(e.from_)

        # depends_on creates implicit edges
        for n in definition.nodes:
            for dep in n.depends_on:
                if dep in succ:
                    succ[dep].add(n.id)
                    pred[n.id].add(dep)

        return nodes_by_id, succ, pred

    def _compute_initial_ready(
        self,
        definition: WorkflowDefinition,
        context: WorkflowContext,
        pred: dict[str, set[str]],
    ) -> list[str]:
        """Return node ids whose predecessors are all completed/skipped."""
        ready: list[str] = []
        for n in definition.nodes:
            status = context.node_statuses.get(n.id, NodeStatus.PENDING)
            if status != NodeStatus.PENDING:
                continue
            if all(
                context.node_statuses.get(p)
                in (NodeStatus.COMPLETED, NodeStatus.SKIPPED)
                for p in pred[n.id]
            ):
                ready.append(n.id)
        return ready

    def _resolve_successors(
        self,
        completed_id: str,
        node: NodeDef,
        definition: WorkflowDefinition,
        context: WorkflowContext,
        succ: dict[str, set[str]],
        pred: dict[str, set[str]],
    ) -> list[str]:
        """When `completed_id` completes, return newly-ready nodes."""
        next_candidates: set[str] = set()

        # For DecisionNode, pick branch based on condition
        if isinstance(node, DecisionNodeDef):
            chosen = self._eval_decision(node, context)
            if chosen:
                next_candidates.add(chosen)
        else:
            # Static successors
            next_candidates.update(succ[completed_id])

        # Filter: predecessors all done, and status is PENDING
        ready: list[str] = []
        for nid in next_candidates:
            status = context.node_statuses.get(nid, NodeStatus.PENDING)
            if status != NodeStatus.PENDING:
                continue
            if all(
                context.node_statuses.get(p)
                in (NodeStatus.COMPLETED, NodeStatus.SKIPPED)
                for p in pred[nid]
            ):
                ready.append(nid)
        return ready

    def _eval_decision(
        self, node: DecisionNodeDef, context: WorkflowContext,
    ) -> Optional[str]:
        """Evaluate a DecisionNode's branches; return chosen next node id."""
        for branch in node.branches:
            try:
                if render_bool(branch.condition, context):
                    return branch.next
            except Exception as e:
                logger.warning("Decision branch failed: %s", e)
                continue
        if node.default_next:
            return node.default_next
        raise NoMatchingBranchError(node.id)

    # -----------------------------------------------------------------
    # Core execution loop
    # -----------------------------------------------------------------

    async def execute(
        self,
        instance_id: UUID,
        definition: WorkflowDefinition,
        context: WorkflowContext,
    ) -> ExecutionResult:
        """Run the workflow until completion, failure, or approval wait."""
        logger.info("Executing workflow %s instance=%s", definition.key, instance_id)

        # Transition to RUNNING (if PENDING)
        instance = self.persistence.load_instance(instance_id)
        if instance.status == WorkflowStatus.PENDING:
            StateMachine.transition_workflow(WorkflowStatus.PENDING, WorkflowStatus.RUNNING)
            self.persistence.update_instance_status(instance_id, WorkflowStatus.RUNNING)
            self.persistence.append_state_event(
                instance_id,
                event_type="workflow_started",
                from_status=WorkflowStatus.PENDING.value,
                to_status=WorkflowStatus.RUNNING.value,
            )

        nodes_by_id, succ, pred = self._build_adjacency(definition)
        ready: list[str] = self._compute_initial_ready(definition, context, pred)

        # Mark any non-terminal, non-ready nodes with status PENDING (if not already)
        for n in definition.nodes:
            if n.id not in context.node_statuses:
                context.node_statuses[n.id] = NodeStatus.PENDING

        running_tasks: dict[asyncio.Task, str] = {}
        terminal_error: Optional[tuple[str, str]] = None  # (node_id, error)

        try:
            while ready or running_tasks:
                # Launch as many ready nodes as concurrency allows
                while ready and len(running_tasks) < definition.max_concurrent_nodes:
                    node_id = ready.pop(0)
                    node = nodes_by_id[node_id]
                    task = asyncio.create_task(
                        self._run_single_node(instance_id, node, context)
                    )
                    running_tasks[task] = node_id
                    context.current_nodes.append(node_id)
                    context.node_statuses[node_id] = NodeStatus.RUNNING

                if not running_tasks:
                    break

                done, _ = await asyncio.wait(
                    running_tasks.keys(),
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for task in done:
                    completed_id = running_tasks.pop(task)
                    if completed_id in context.current_nodes:
                        context.current_nodes.remove(completed_id)

                    try:
                        output = task.result()
                        context.apply_node_output(completed_id, output)
                        self.persistence.update_instance_context(instance_id, context)
                        self.persistence.append_state_event(
                            instance_id,
                            event_type="node_completed",
                            node_id=completed_id,
                            to_status=NodeStatus.COMPLETED.value,
                        )

                        new_ready = self._resolve_successors(
                            completed_id, nodes_by_id[completed_id],
                            definition, context, succ, pred,
                        )
                        ready.extend(new_ready)

                    except Exception as e:
                        context.node_statuses[completed_id] = NodeStatus.FAILED
                        err_msg = f"{type(e).__name__}: {e}"
                        self.persistence.update_instance_context(instance_id, context)
                        self.persistence.append_state_event(
                            instance_id,
                            event_type="node_failed",
                            node_id=completed_id,
                            to_status=NodeStatus.FAILED.value,
                            payload={"error": err_msg},
                        )
                        logger.error("Node %s failed: %s", completed_id, err_msg)

                        node = nodes_by_id[completed_id]
                        if node.on_error == ErrorStrategy.SKIP:
                            # Mark skipped and continue
                            context.node_statuses[completed_id] = NodeStatus.SKIPPED
                            new_ready = self._resolve_successors(
                                completed_id, node, definition, context, succ, pred,
                            )
                            ready.extend(new_ready)
                        else:
                            # FAIL_WORKFLOW - stop everything
                            terminal_error = (completed_id, err_msg)
                            for t in running_tasks:
                                t.cancel()
                            break

                if terminal_error:
                    break

            if terminal_error:
                node_id, err = terminal_error
                self.persistence.update_instance_status(
                    instance_id, WorkflowStatus.FAILED,
                    error_message=f"Node {node_id}: {err}",
                    ended=True,
                )
                self.persistence.append_state_event(
                    instance_id,
                    event_type="workflow_failed",
                    to_status=WorkflowStatus.FAILED.value,
                    payload={"failed_node": node_id, "error": err},
                )
                return ExecutionResult(
                    WorkflowStatus.FAILED, error=err, failed_node=node_id,
                )

            # All ready-reachable nodes done
            self.persistence.update_instance_status(
                instance_id, WorkflowStatus.COMPLETED, ended=True,
            )
            self.persistence.append_state_event(
                instance_id,
                event_type="workflow_completed",
                from_status=WorkflowStatus.RUNNING.value,
                to_status=WorkflowStatus.COMPLETED.value,
            )
            return ExecutionResult(WorkflowStatus.COMPLETED)

        except asyncio.CancelledError:
            # Propagate cancellation
            for t in running_tasks:
                t.cancel()
            raise

    async def _run_single_node(
        self,
        instance_id: UUID,
        node: NodeDef,
        context: WorkflowContext,
    ) -> Any:
        """Execute a single node, with timeout and basic retry support."""
        attempts_allowed = 1
        backoff = 0.0
        multiplier = 1.0
        if node.retry_policy:
            attempts_allowed = node.retry_policy.max_attempts
            backoff = node.retry_policy.backoff_seconds
            multiplier = node.retry_policy.backoff_multiplier

        last_error: Optional[Exception] = None
        for attempt in range(1, attempts_allowed + 1):
            execution_id = str(uuid4())
            context.node_attempts[node.id] = attempt

            # Render params (for TaskNode) once per attempt
            params: dict[str, Any] = {}
            if isinstance(node, TaskNodeDef):
                try:
                    params = render_params(node.params, context)
                except Exception as e:
                    last_error = e
                    break

            # Record execution start
            started = datetime.utcnow()
            self.persistence.save_node_execution(
                instance_id=instance_id,
                node_id=node.id,
                node_type=NodeType(node.type),
                execution_id=execution_id,
                status=NodeStatus.RUNNING,
                attempt=attempt,
                input_data=params if params else None,
                started_at=started,
            )
            self.persistence.append_state_event(
                instance_id,
                event_type="node_started",
                node_id=node.id,
                to_status=NodeStatus.RUNNING.value,
                payload={"attempt": attempt, "execution_id": execution_id},
            )

            # Dispatch (with optional timeout)
            try:
                if node.timeout_seconds:
                    output = await asyncio.wait_for(
                        self.dispatcher(node, params, context),
                        timeout=node.timeout_seconds,
                    )
                else:
                    output = await self.dispatcher(node, params, context)

                # Success
                self.persistence.update_node_execution(
                    execution_id, NodeStatus.COMPLETED, output=output,
                )
                return output

            except asyncio.CancelledError:
                self.persistence.update_node_execution(
                    execution_id, NodeStatus.FAILED, error="cancelled",
                )
                raise

            except Exception as e:
                last_error = e
                self.persistence.update_node_execution(
                    execution_id, NodeStatus.FAILED, error=f"{type(e).__name__}: {e}",
                )
                logger.warning(
                    "Node %s attempt %d/%d failed: %s",
                    node.id, attempt, attempts_allowed, e,
                )

                if attempt < attempts_allowed:
                    wait = backoff * (multiplier ** (attempt - 1))
                    await asyncio.sleep(wait)

        # All attempts exhausted
        raise NodeExecutionError(node.id, last_error or Exception("unknown"))
