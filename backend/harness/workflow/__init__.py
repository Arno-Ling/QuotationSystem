"""
Harness Workflow Engine
========================

DAG-based workflow orchestration engine for the Harness framework.

Provides:
- Declarative workflow definitions (YAML/JSON)
- Five node types: Task / Decision / Parallel / Approval / Loop
- MySQL persistence with crash recovery
- Human approval with 12 actions and 3 assignee types
- WebSocket real-time progress streaming
- Reuses existing Harness: ToolRegistry / AgentLoop / Memory / Security / Callback

This module is additive: it does NOT modify any existing harness/ submodule.
"""

__version__ = "0.1.0"
