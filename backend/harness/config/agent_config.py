"""
AgentConfig - 中央配置管理
管理 Agent 的所有配置参数
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


class ToolPermission(str, Enum):
    """工具权限级别"""
    READ_ONLY = "read_only"      # 只读操作
    READ_WRITE = "read_write"    # 读写操作
    SENSITIVE = "sensitive"       # 敏感操作，需要人工确认


class AgentConfig(BaseModel):
    """Agent 配置模型"""
    
    # LLM 配置
    model_name: str = Field(default="gpt-4", description="LLM 模型名称")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="生成温度")
    max_tokens: int = Field(default=2000, description="最大生成 token 数")
    
    # 执行配置
    max_steps: int = Field(default=10, ge=1, le=50, description="最大执行步数")
    reflection_interval: int = Field(default=3, ge=1, description="反思间隔步数")
    enable_planning: bool = Field(default=True, description="是否启用规划模式")
    
    # 记忆配置
    max_short_term_messages: int = Field(default=20, description="短期记忆最大消息数")
    enable_long_term_memory: bool = Field(default=True, description="是否启用长期记忆")
    long_term_memory_top_k: int = Field(default=3, description="长期记忆检索数量")
    
    # 安全配置
    enable_input_guardrails: bool = Field(default=True, description="是否启用输入护栏")
    enable_output_audit: bool = Field(default=True, description="是否启用输出审计")
    dangerous_patterns: List[str] = Field(
        default_factory=lambda: [
            r"rm\s+-rf\s+/",
            r"del\s+/[sS]",
            r"format\s+[cC]:",
            r"DROP\s+DATABASE",
            r"DROP\s+TABLE"
        ],
        description="危险操作模式列表"
    )
    allowed_paths: List[str] = Field(
        default_factory=lambda: ["/tmp", "./workspace"],
        description="允许访问的路径白名单"
    )
    
    # 工具权限配置
    tool_permissions: Dict[str, ToolPermission] = Field(
        default_factory=dict,
        description="工具权限映射"
    )
    require_human_confirmation: bool = Field(
        default=True,
        description="敏感工具是否需要人工确认"
    )
    
    # 可观测性配置
    enable_logging: bool = Field(default=True, description="是否启用日志")
    log_level: str = Field(default="INFO", description="日志级别")
    enable_callbacks: bool = Field(default=True, description="是否启用回调")
    
    # 系统提示
    system_prompt: str = Field(
        default="""You are a helpful AI assistant with access to tools.
You can think step by step and use tools to accomplish tasks.

When you need to use a tool, respond with:
Tool Call: {"name": "tool_name", "arguments": {"arg1": "value1"}}

When you have the final answer, respond with:
Final Answer: [your answer here]

Think carefully and break down complex problems into steps.""",
        description="系统提示词"
    )
    
    class Config:
        use_enum_values = True


# 默认配置实例
default_config = AgentConfig()
