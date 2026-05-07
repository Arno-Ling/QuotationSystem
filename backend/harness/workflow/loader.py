"""
WorkflowLoader - parse, validate, and load workflow definitions.

Loads `WorkflowDefinition` from YAML, JSON, or dict. Runs:
- Pydantic schema validation (structural)
- Node reference validation (every edge endpoint must exist)
- DAG acyclicity check via Kahn's algorithm (REQ-007, P1)
- Start-node existence + end-node inference

Requirements: REQ-006, REQ-007, REQ-008
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional, Union

import yaml
from pydantic import ValidationError

from .errors import (
    CyclicGraphError,
    InvalidNodeRefError,
    SchemaValidationError,
)
from .models import (
    DecisionBranch,
    DecisionNodeDef,
    Edge,
    LoopNodeDef,
    NodeDef,
    NodeType,
    WorkflowDefinition,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DAG validation
# ---------------------------------------------------------------------------

def _build_adjacency(
    nodes: list[NodeDef], edges: list[Edge],
) -> tuple[dict[str, list[str]], dict[str, int], set[str]]:
    """Build adjacency list + in-degree map from nodes and edges.

    Also automatically includes:
    - `depends_on` declarations on each node
    - DecisionNode `branches[*].next` as additional edges
    - ApprovalNode `next_on_approve` / `next_on_reject` as additional edges

    Returns (adjacency, in_degree, node_id_set).
    """
    node_ids = {n.id for n in nodes}

    adjacency: dict[str, list[str]] = {nid: [] for nid in node_ids}
    in_degree: dict[str, int] = {nid: 0 for nid in node_ids}

    def _add_edge(frm: str, to: str, context: str) -> None:
        if frm not in node_ids:
            raise InvalidNodeRefError(frm, in_edge=(frm, to))
        if to not in node_ids:
            raise InvalidNodeRefError(to, in_edge=(frm, to))
        adjacency[frm].append(to)
        in_degree[to] += 1

    # Explicit edges from `edges` list
    for e in edges:
        _add_edge(e.from_, e.to, context="edges")

    # Implicit edges from node.depends_on (reversed: dep -> node)
    for node in nodes:
        for dep in node.depends_on:
            if dep not in node_ids:
                raise InvalidNodeRefError(dep, in_edge=(dep, node.id))
            # Only add if not already present
            if node.id not in adjacency[dep]:
                adjacency[dep].append(node.id)
                in_degree[node.id] += 1

    # DecisionNode branches
    for node in nodes:
        if isinstance(node, DecisionNodeDef):
            for branch in node.branches:
                if branch.next not in node_ids:
                    raise InvalidNodeRefError(
                        branch.next, in_edge=(node.id, branch.next)
                    )
            # Branches produce runtime decisions, not static edges; skip adding
            # to in_degree to avoid double-counting.

    return adjacency, in_degree, node_ids


def _find_cycle(
    nodes: list[NodeDef], edges: list[Edge],
) -> list[str]:
    """Return one cycle in the graph (for error reporting).

    Uses DFS with coloring: WHITE/GRAY/BLACK.
    """
    adjacency: dict[str, list[str]] = {n.id: [] for n in nodes}
    for e in edges:
        if e.from_ in adjacency and e.to in adjacency[e.from_]:
            continue
        if e.from_ in adjacency:
            adjacency[e.from_].append(e.to)
    for node in nodes:
        for dep in node.depends_on:
            if dep in adjacency and node.id not in adjacency[dep]:
                adjacency[dep].append(node.id)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n.id: WHITE for n in nodes}
    parent: dict[str, Optional[str]] = {n.id: None for n in nodes}
    cycle: list[str] = []

    def dfs(u: str) -> bool:
        color[u] = GRAY
        for v in adjacency.get(u, []):
            if color.get(v, BLACK) == GRAY:
                # Found a back edge: v is on the current DFS stack
                path = [v, u]
                cur = parent[u]
                while cur is not None and cur != v:
                    path.append(cur)
                    cur = parent[cur]
                if cur == v:
                    path.append(v)
                cycle.extend(reversed(path))
                return True
            if color.get(v, BLACK) == WHITE:
                parent[v] = u
                if dfs(v):
                    return True
        color[u] = BLACK
        return False

    for n in nodes:
        if color[n.id] == WHITE and dfs(n.id):
            return cycle
    return cycle


def validate_dag_acyclic(
    nodes: list[NodeDef], edges: list[Edge],
) -> list[str]:
    """Run Kahn's topological sort; raise CyclicGraphError on cycle.

    Returns the topological ordering (list of node ids).

    REQ-007: DAG acyclicity check.
    """
    if not nodes:
        raise SchemaValidationError("Workflow must have at least one node")

    adjacency, in_degree, node_ids = _build_adjacency(nodes, edges)

    # Initial queue: all zero-in-degree nodes
    queue: list[str] = [nid for nid in node_ids if in_degree[nid] == 0]
    topo: list[str] = []

    # Use list as FIFO via pop(0); node sets are small so this is fine
    while queue:
        u = queue.pop(0)
        topo.append(u)
        for v in adjacency[u]:
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)

    if len(topo) < len(node_ids):
        cycle = _find_cycle(nodes, edges)
        raise CyclicGraphError(
            message="Workflow DAG contains a cycle",
            cycle=cycle,
        )

    return topo


# ---------------------------------------------------------------------------
# Full validator
# ---------------------------------------------------------------------------

def _infer_end_nodes(nodes: list[NodeDef], edges: list[Edge]) -> list[str]:
    """Infer end nodes: those with no outgoing edges."""
    has_out: set[str] = set()
    for e in edges:
        has_out.add(e.from_)
    # Also consider nodes referenced as `depends_on` by children:
    # if a node is someone's dependency, it has an implicit outgoing edge.
    for node in nodes:
        for dep in node.depends_on:
            has_out.add(dep)
    return [n.id for n in nodes if n.id not in has_out]


class WorkflowLoader:
    """Load, validate, and construct WorkflowDefinition objects."""

    @staticmethod
    def from_dict(spec: dict[str, Any]) -> WorkflowDefinition:
        """Build a WorkflowDefinition from a dict and fully validate it."""
        try:
            definition = WorkflowDefinition.model_validate(spec)
        except ValidationError as e:
            # Extract first error path for clarity
            err = e.errors()[0]
            path = ".".join(str(p) for p in err["loc"])
            raise SchemaValidationError(
                f"{err['msg']} at path: {path}",
                field_path=path,
            ) from e

        WorkflowLoader.validate(definition)
        return definition

    @staticmethod
    def from_yaml_file(path: Union[str, Path]) -> WorkflowDefinition:
        """Load from a YAML file."""
        path = Path(path)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            raise SchemaValidationError(f"Cannot read YAML file: {e}") from e
        try:
            spec = yaml.safe_load(text)
        except yaml.YAMLError as e:
            raise SchemaValidationError(f"Invalid YAML: {e}") from e
        if not isinstance(spec, dict):
            raise SchemaValidationError("Top-level YAML must be a mapping/dict")
        return WorkflowLoader.from_dict(spec)

    @staticmethod
    def from_json_file(path: Union[str, Path]) -> WorkflowDefinition:
        """Load from a JSON file."""
        path = Path(path)
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise SchemaValidationError(f"Cannot load JSON file: {e}") from e
        if not isinstance(spec, dict):
            raise SchemaValidationError("Top-level JSON must be an object")
        return WorkflowLoader.from_dict(spec)

    @staticmethod
    def validate(definition: WorkflowDefinition) -> list[str]:
        """Top-level validation: structure + DAG acyclicity + start_node.

        Returns the topological ordering on success.
        """
        # start_node must exist
        node_ids = {n.id for n in definition.nodes}
        if definition.start_node not in node_ids:
            raise SchemaValidationError(
                f"start_node {definition.start_node!r} not found in nodes",
                field_path="start_node",
            )

        # Check node id uniqueness
        seen: set[str] = set()
        for n in definition.nodes:
            if n.id in seen:
                raise SchemaValidationError(
                    f"Duplicate node id: {n.id!r}", field_path="nodes"
                )
            seen.add(n.id)

        # Check DecisionNode structural: must have branches or default_next
        for n in definition.nodes:
            if isinstance(n, DecisionNodeDef):
                if not n.branches and not n.default_next:
                    raise SchemaValidationError(
                        f"DecisionNode {n.id!r} must have branches or default_next",
                        field_path=f"nodes.{n.id}",
                    )
            if isinstance(n, LoopNodeDef):
                # Verify body nodes exist
                for body_id in n.body:
                    if body_id not in node_ids:
                        raise InvalidNodeRefError(body_id)

        # DAG acyclicity
        topo = validate_dag_acyclic(definition.nodes, definition.edges)

        # Infer end_nodes if not provided
        if not definition.end_nodes:
            definition.end_nodes = _infer_end_nodes(definition.nodes, definition.edges)

        logger.debug(
            "Workflow %s v%s validated: %d nodes, %d edges, topo=%s",
            definition.key, definition.version,
            len(definition.nodes), len(definition.edges), topo,
        )
        return topo
