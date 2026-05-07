"""
AgentHarness - AI Agent 控制框架

一个为大型语言模型（LLM）设计的操作系统层（Harness），
让模型从只能生成文本的静态状态，变成一个能自主思考、调用工具、
管理记忆、规划并执行长程任务的AI智能体（Agent）。
"""

__version__ = "0.1.0"
__author__ = "AgentHarness Team"

# 核心组件
from .core.agent_loop import AgentLoop
from .core.parser import OutputParser, ParsedOutput, ToolCall, FinalAnswer

# 配置
from .config.agent_config import AgentConfig, ToolPermission, default_config

# 工具
from .tools.registry import ToolRegistry, Tool, registry
from .tools.decorators import tool, sensitive_tool, readonly_tool

# 记忆
from .memory.short_term import ShortTermMemory, Message
from .memory.long_term import LongTermMemory

# 安全
from .security.guardrails import SecurityManager, InputGuardrails, OutputAudit, GuardrailViolation

# 可观测性
from .observability.logger import StructuredLogger, structured_logger
from .observability.callback import (
    BaseCallback,
    ConsoleCallback,
    WebSocketCallback,
    CallbackManager
)

# 规划
from .planning.planner import Planner, Plan, Task

# 编排
from .orchestration.orchestrator import Orchestrator, AgentInfo

__all__ = [
    # 版本信息
    "__version__",
    "__author__",
    
    # 核心
    "AgentLoop",
    "OutputParser",
    "ParsedOutput",
    "ToolCall",
    "FinalAnswer",
    
    # 配置
    "AgentConfig",
    "ToolPermission",
    "default_config",
    
    # 工具
    "ToolRegistry",
    "Tool",
    "registry",
    "tool",
    "sensitive_tool",
    "readonly_tool",
    
    # 记忆
    "ShortTermMemory",
    "Message",
    "LongTermMemory",
    
    # 安全
    "SecurityManager",
    "InputGuardrails",
    "OutputAudit",
    "GuardrailViolation",
    
    # 可观测性
    "StructuredLogger",
    "structured_logger",
    "BaseCallback",
    "ConsoleCallback",
    "WebSocketCallback",
    "CallbackManager",
    
    # 规划
    "Planner",
    "Plan",
    "Task",
    
    # 编排
    "Orchestrator",
    "AgentInfo",
]
