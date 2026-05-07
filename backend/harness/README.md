# AgentHarness - AI Agent 控制框架

> 一个为大型语言模型（LLM）设计的操作系统层（Harness），让模型从只能生成文本的静态状态，变成一个能自主思考、调用工具、管理记忆、规划并执行长程任务的AI智能体（Agent）。

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 📋 目录

- [特性](#特性)
- [架构](#架构)
- [快速开始](#快速开始)
- [安装](#安装)
- [使用指南](#使用指南)
- [核心组件](#核心组件)
- [示例](#示例)
- [API 文档](#api-文档)
- [开发指南](#开发指南)
- [常见问题](#常见问题)

---

## ✨ 特性

### 七大核心层

1. **推理执行层 (Reasoning & Execution)**
   - 实现 ReAct 模式：Think → Act → Observe
   - 异步执行循环
   - 支持最大步数限制

2. **工具接入层 (Tool Integration)**
   - 工具注册表
   - 装饰器自动注册
   - 工具执行和异常捕获
   - JSON Schema 自动生成

3. **记忆管理层 (Memory Management)**
   - 短期记忆：对话历史管理
   - 长期记忆：ChromaDB 向量检索
   - 上下文窗口管理

4. **规划与任务分解层 (Planning & Decomposition)**
   - Plan-and-Execute 模式
   - 反思步骤 (Reflection)
   - 任务分解

5. **安全防护层 (Security & Permissions)**
   - 输入护栏：检测恶意输入
   - 输出审计：过滤危险操作
   - 工具权限分级
   - 路径白名单

6. **可观测性层 (Observability)**
   - 结构化日志 (JSON)
   - 实时回调接口
   - 完整执行跟踪

7. **多智能体编排层 (Multi-Agent Orchestration)**
   - 多 Agent 注册
   - 任务路由
   - Agent 协作

---

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────────┐
│                    AgentLoop (核心循环)                  │
│              Think → Act → Observe → Repeat             │
└─────────────────────────────────────────────────────────┘
         ↓                ↓                ↓
┌────────────────┐ ┌────────────┐ ┌──────────────────┐
│  LLM 调用       │ │ 工具执行    │ │  记忆管理         │
│  (litellm)     │ │ (Registry) │ │  (Short/Long)    │
└────────────────┘ └────────────┘ └──────────────────┘
         ↓                ↓                ↓
┌─────────────────────────────────────────────────────────┐
│                    安全防护层                            │
│          输入护栏 | 输出审计 | 权限管理                  │
└─────────────────────────────────────────────────────────┘
         ↓                ↓                ↓
┌─────────────────────────────────────────────────────────┐
│                    可观测性层                            │
│          结构化日志 | 回调系统 | 执行跟踪                │
└─────────────────────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

**requirements.txt**:
```
litellm>=1.0.0
chromadb>=0.4.0
pydantic>=2.0.0
```

### 2. 设置环境变量

```bash
# .env 文件
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. 运行示例

```bash
cd backend
python main.py
```

### 4. 基础使用

```python
import asyncio
from harness import AgentLoop, AgentConfig, ToolRegistry, tool

# 定义工具
@tool(description="计算器工具")
def calculator(expression: str) -> str:
    return str(eval(expression))

# 创建配置
config = AgentConfig(
    model_name="gpt-4",
    max_steps=10
)

# 创建 Agent
from harness.tools import registry
agent = AgentLoop(
    config=config,
    tool_registry=registry
)

# 运行任务
async def main():
    result = await agent.run("计算 15 + 27 的结果")
    print(result)

asyncio.run(main())
```

---

## 📦 安装

### 方式 1: 从源码安装

```bash
git clone <repository_url>
cd backend
pip install -r requirements.txt
```

### 方式 2: 作为包安装

```bash
pip install -e ./backend/harness
```

### 依赖说明

| 依赖 | 版本 | 用途 |
|------|------|------|
| litellm | ≥1.0.0 | 统一 LLM 调用接口 |
| chromadb | ≥0.4.0 | 向量数据库（长期记忆） |
| pydantic | ≥2.0.0 | 数据验证 |
| python | ≥3.10 | 运行环境 |

---

## 📖 使用指南

### 创建和注册工具

#### 方式 1: 使用装饰器（推荐）

```python
from harness import tool, sensitive_tool, readonly_tool

@tool(description="搜索引擎工具")
def search(query: str) -> str:
    """搜索信息"""
    return f"搜索结果: {query}"

@sensitive_tool(description="删除文件")
def delete_file(path: str) -> str:
    """删除文件（需要人工确认）"""
    import os
    os.remove(path)
    return f"已删除: {path}"

@readonly_tool(description="读取文件")
def read_file(path: str) -> str:
    """读取文件内容"""
    with open(path, 'r') as f:
        return f.read()
```

#### 方式 2: 手动注册

```python
from harness import ToolRegistry

registry = ToolRegistry()

def my_tool(arg1: str, arg2: int) -> str:
    return f"Result: {arg1} {arg2}"

registry.register(
    name="my_tool",
    function=my_tool,
    description="我的工具",
    permission="read_only"
)
```

### 配置 Agent

```python
from harness import AgentConfig, ToolPermission

config = AgentConfig(
    # LLM 配置
    model_name="gpt-4",
    temperature=0.7,
    max_tokens=2000,
    
    # 执行配置
    max_steps=10,
    reflection_interval=3,
    enable_planning=True,
    
    # 记忆配置
    max_short_term_messages=20,
    enable_long_term_memory=True,
    long_term_memory_top_k=3,
    
    # 安全配置
    enable_input_guardrails=True,
    enable_output_audit=True,
    require_human_confirmation=True,
    
    # 工具权限
    tool_permissions={
        "delete_file": ToolPermission.SENSITIVE,
        "search": ToolPermission.READ_ONLY,
    }
)
```

### 使用记忆

#### 短期记忆

```python
from harness import ShortTermMemory

memory = ShortTermMemory(max_messages=20)

# 添加消息
memory.add_message(role="user", content="你好")
memory.add_message(role="assistant", content="你好！有什么可以帮助你的？")

# 获取消息
messages = memory.get_messages()
print(f"共有 {len(memory)} 条消息")
```

#### 长期记忆

```python
from harness import LongTermMemory

long_memory = LongTermMemory(
    collection_name="my_agent_memory",
    persist_directory="./chroma_db"
)

# 添加记忆
long_memory.add(
    content="用户喜欢使用 Python 编程",
    metadata={"category": "preference"}
)

# 搜索相关记忆
results = long_memory.search(
    query="用户的编程偏好",
    top_k=3
)

for result in results:
    print(f"- {result['content']}")
```

### 使用回调

```python
from harness import ConsoleCallback, CallbackManager

# 创建回调管理器
callback_manager = CallbackManager()

# 添加控制台回调
console_callback = ConsoleCallback(verbose=True)
callback_manager.add_callback(console_callback)

# 在 Agent 执行时触发回调
callback_manager.on_agent_start(task="示例任务", config={})
callback_manager.on_step_start(step=1)
callback_manager.on_llm_call(step=1, input_messages=[], output="思考中...")
callback_manager.on_agent_complete(final_answer="完成", total_steps=5)
```

### 多 Agent 编排

```python
from harness import Orchestrator, AgentLoop, AgentConfig

# 创建编排器
orchestrator = Orchestrator()

# 注册多个 Agent
agent1 = AgentLoop(config=AgentConfig(model_name="gpt-4"), tool_registry=registry)
agent2 = AgentLoop(config=AgentConfig(model_name="gpt-3.5-turbo"), tool_registry=registry)

orchestrator.register_agent(
    agent_id="expert_agent",
    name="专家 Agent",
    description="处理复杂任务",
    capabilities=["analysis", "planning"],
    agent_instance=agent1
)

orchestrator.register_agent(
    agent_id="simple_agent",
    name="简单 Agent",
    description="处理简单任务",
    capabilities=["search", "calculation"],
    agent_instance=agent2
)

# 路由任务
result = await orchestrator.route_task("分析这个复杂问题")
print(f"由 {result['agent_name']} 处理: {result['result']}")
```

---

## 🧩 核心组件

### AgentLoop

核心执行循环，实现 ReAct 模式。

```python
agent = AgentLoop(
    config=config,
    tool_registry=registry,
    short_term_memory=memory,
    long_term_memory=long_memory
)

result = await agent.run(task="你的任务", context={"key": "value"})
```

**关键方法**:
- `run(task, context)`: 运行任务
- `get_state()`: 获取当前状态
- `stop()`: 停止执行

### ToolRegistry

工具注册表，管理所有可用工具。

```python
registry = ToolRegistry()

# 注册工具
registry.register(name="tool_name", function=func, description="描述")

# 执行工具
result = registry.execute(name="tool_name", arguments={"arg": "value"})

# 列出工具
tools = registry.list_tools()
```

### SecurityManager

安全管理器，提供输入护栏和输出审计。

```python
from harness import SecurityManager

security = SecurityManager(config)

# 验证输入
safe_input = security.validate_input(user_input)

# 审计工具调用
audit_result = security.audit_tool_call(
    tool_name="delete_file",
    arguments={"path": "/tmp/file.txt"},
    tool_permission=ToolPermission.SENSITIVE
)

if audit_result["allowed"]:
    # 执行工具
    pass
```

### Planner

规划器，支持 Plan-and-Execute 模式。

```python
from harness import Planner

planner = Planner(llm_caller=llm_function)

# 生成计划
plan = await planner.generate_plan(goal="完成复杂任务")

# 查看计划
print(f"计划包含 {len(plan.tasks)} 个任务")
for task in plan.tasks:
    print(f"- {task.description}")

# 反思进度
reflection = await planner.reflect_on_progress(plan, execution_history)
```

---

## 💡 示例

### 示例 1: 简单计算器 Agent

```python
import asyncio
from harness import AgentLoop, AgentConfig, tool
from harness.tools import registry

@tool(description="计算器")
def calculator(expression: str) -> str:
    return str(eval(expression))

async def main():
    config = AgentConfig(model_name="gpt-4", max_steps=5)
    agent = AgentLoop(config=config, tool_registry=registry)
    
    result = await agent.run("计算 (15 + 27) * 3")
    print(result)

asyncio.run(main())
```

### 示例 2: 搜索 + 分析 Agent

```python
@tool(description="搜索引擎")
def search(query: str) -> str:
    # 实际应该调用真实搜索 API
    return f"搜索结果: {query}"

@tool(description="文本分析")
def analyze_text(text: str) -> str:
    return f"分析结果: 文本长度 {len(text)} 字符"

async def main():
    agent = AgentLoop(config=AgentConfig(), tool_registry=registry)
    
    result = await agent.run(
        "搜索关于 Python 的信息，然后分析搜索结果"
    )
    print(result)

asyncio.run(main())
```

### 示例 3: 带安全防护的 Agent

```python
from harness import SecurityManager, GuardrailViolation

security = SecurityManager(config)

try:
    # 验证用户输入
    safe_input = security.validate_input(user_input)
    
    # 运行 Agent
    result = await agent.run(safe_input)
    
except GuardrailViolation as e:
    print(f"输入被拒绝: {e}")
```

---

## 📚 API 文档

### AgentConfig

| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| model_name | str | "gpt-4" | LLM 模型名称 |
| temperature | float | 0.7 | 生成温度 |
| max_tokens | int | 2000 | 最大 token 数 |
| max_steps | int | 10 | 最大执行步数 |
| enable_long_term_memory | bool | True | 是否启用长期记忆 |
| enable_input_guardrails | bool | True | 是否启用输入护栏 |
| enable_output_audit | bool | True | 是否启用输出审计 |

### ToolPermission

工具权限级别：

- `READ_ONLY`: 只读操作
- `READ_WRITE`: 读写操作
- `SENSITIVE`: 敏感操作，需要人工确认

---

## 🛠️ 开发指南

### 项目结构

```
harness/
├── __init__.py              # 包入口
├── config/                  # 配置管理
│   ├── __init__.py
│   └── agent_config.py
├── core/                    # 核心模块
│   ├── __init__.py
│   ├── agent_loop.py        # Agent 循环
│   └── parser.py            # 输出解析器
├── tools/                   # 工具模块
│   ├── __init__.py
│   ├── registry.py          # 工具注册表
│   └── decorators.py        # 装饰器
├── memory/                  # 记忆模块
│   ├── __init__.py
│   ├── short_term.py        # 短期记忆
│   └── long_term.py         # 长期记忆
├── security/                # 安全模块
│   ├── __init__.py
│   └── guardrails.py        # 护栏
├── observability/           # 可观测性
│   ├── __init__.py
│   ├── logger.py            # 日志
│   └── callback.py          # 回调
├── planning/                # 规划模块
│   ├── __init__.py
│   └── planner.py           # 规划器
├── orchestration/           # 编排模块
│   ├── __init__.py
│   └── orchestrator.py      # 编排器
└── README.md                # 文档
```

### 添加新功能

1. **添加新工具**:
   - 在 `tools/` 目录创建新文件
   - 使用 `@tool` 装饰器注册

2. **扩展记忆**:
   - 在 `memory/` 目录添加新的记忆类型
   - 继承基类并实现接口

3. **自定义回调**:
   - 继承 `BaseCallback`
   - 实现所有抽象方法

### 测试

```bash
# 运行所有测试
pytest tests/

# 运行特定测试
pytest tests/test_agent_loop.py

# 查看覆盖率
pytest --cov=harness tests/
```

---

## ❓ 常见问题

### Q: 如何更换 LLM 模型？

A: 修改 `AgentConfig` 中的 `model_name`:

```python
config = AgentConfig(model_name="gpt-3.5-turbo")  # 或其他模型
```

litellm 支持多种模型：
- OpenAI: `gpt-4`, `gpt-3.5-turbo`
- Anthropic: `claude-3-opus`, `claude-3-sonnet`
- Ollama: `ollama/llama2`, `ollama/mistral`

### Q: 如何禁用长期记忆？

A: 设置配置参数:

```python
config = AgentConfig(enable_long_term_memory=False)
```

### Q: 如何添加自定义安全规则？

A: 修改配置中的 `dangerous_patterns`:

```python
config = AgentConfig(
    dangerous_patterns=[
        r"rm\s+-rf\s+/",
        r"DROP\s+DATABASE",
        # 添加你的模式
    ]
)
```

### Q: Agent 执行失败怎么办？

A: 检查以下几点：
1. 确认 `OPENAI_API_KEY` 已设置
2. 检查网络连接
3. 查看日志输出
4. 增加 `max_steps` 限制

### Q: 如何保存和加载 Agent 状态？

A: 使用长期记忆功能，或手动保存短期记忆:

```python
# 保存
messages = agent.short_term_memory.get_messages()
with open('state.json', 'w') as f:
    json.dump(messages, f)

# 加载
with open('state.json', 'r') as f:
    messages = json.load(f)
for msg in messages:
    agent.short_term_memory.add_message(**msg)
```

---

## 📄 许可证

MIT License

---

## 🤝 贡献

欢迎贡献！请提交 Pull Request 或创建 Issue。

---

## 📧 联系方式

如有问题或建议，请联系项目维护者。

---

**AgentHarness** - 让 AI 从文本生成器变成智能助手 🚀
