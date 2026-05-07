# Implementation Plan: Harness Workflow Engine

## Overview

本实现计划按 **MVP 优先 + 逐层增量** 的策略推进：

1. **Phase A–C** 先打通 "YAML 加载 → DAG 校验 → 线性 Task 节点 → 持久化 → 查询" 的最小闭环。
2. **Phase D–E** 逐步补齐 Decision / Parallel / Approval / Loop 节点。
3. **Phase F–G** 接入现有 Harness 组件（ToolRegistry / AgentLoop / Memory / Security / Callback）并暴露 HTTP + WebSocket API。
4. **Phase H** 以端到端异常分析工作流验证并补全性能和属性覆盖。

**集成约束**：整个引擎作为**新增的 `backend/harness/workflow/` 子模块**，不修改 `harness/core`、`harness/memory`、`harness/security`、`harness/observability`、`harness/tools`、`harness/orchestration` 的公共接口，不破坏 `ExceptionAgent` / `QuotationAgent` 现有路径。所有新 API 路由集中到 `backend/api/routes/workflow.py`。

**测试约定**：
- 使用 `pytest` + `pytest-asyncio` + `hypothesis`
- 每条正确性属性（P1–P11）**一个独立测试文件**，命名 `test_property_p{N}_{slug}.py`
- 属性测试 / 性能测试均为**可选**子任务（`*` 标记，可跳过以快速出 MVP）

## Tasks

### Phase A: 基础数据结构（Foundations）

- [x] 1. 创建 workflow 模块目录结构
  - 新建 `backend/harness/workflow/` 主目录
  - 新建子目录 `approval/`、`nodes/`
  - 创建所有 `__init__.py` 占位文件
  - 不修改现有 `harness/` 其他子模块
  - _Requirements: REQ-075_

- [x] 2. 定义枚举与常量类型
  - [x] 2.1 在 `models.py` 定义工作流与节点状态枚举
    - `WorkflowStatus`: PENDING / RUNNING / WAITING_APPROVAL / EXECUTING / COMPLETED / FAILED / SUSPENDED / CANCELLED
    - `NodeStatus`: PENDING / RUNNING / COMPLETED / FAILED / SKIPPED / WAITING_APPROVAL
    - `NodeType`: TASK / DECISION / PARALLEL / APPROVAL / LOOP
    - `ErrorStrategy`: FAIL_WORKFLOW / SKIP / RETRY / GO_TO
    - _Requirements: REQ-018, REQ-019, REQ-049_

  - [x] 2.2 在 `models.py` 定义审批相关枚举
    - `AssigneeType`: USER / SHARED_ACCOUNT / ROLE
    - `ApprovalAction`: 12 种（SAVE / SUBMIT / RETRIEVE / APPROVE / REJECT_RETURN / REJECT / WITHDRAW / READ / ACK / DELEGATE / FORWARD / CUSTOM）
    - _Requirements: REQ-027, REQ-028_

- [x] 3. 定义异常类层次
  - 在 `errors.py` 定义基类 `WorkflowError`
  - 定义 DAG 定义错误：`CyclicGraphError`、`InvalidNodeRefError`、`SchemaValidationError`、`DuplicateDefinitionError`
  - 定义节点执行错误：`NodeExecutionError`、`ToolNotFoundError`、`AgentNotFoundError`、`SkillLoadError`、`NoMatchingBranchError`
  - 定义状态错误：`IllegalTransitionError`
  - 定义审批错误：`PermissionError`、`IllegalActionError`
  - 定义持久化错误：`DatabaseError`、`InstanceLockedError`、`InstanceNotFoundError`、`DefinitionNotFoundError`
  - 定义模板错误：`TemplateRenderError`
  - _Requirements: REQ-053_

- [x] 4. 定义节点声明式模型（Pydantic v2）
  - [x] 4.1 定义 `RetryPolicy` 和 `Edge` 模型
    - `RetryPolicy`：max_attempts / backoff_seconds / backoff_multiplier / retry_on
    - `Edge`：from / to / condition（支持 Pydantic alias `from_` ↔ `from`）
    - _Requirements: REQ-049, REQ-050_

  - [x] 4.2 定义 `TaskNodeDef`、`DecisionNodeDef`、`DecisionBranch`
    - TaskNodeDef 含 `call_kind` Literal["tool","agent","skill"] 和 `target`
    - DecisionNodeDef 含 `branches` 列表与 `default_next`
    - _Requirements: REQ-011, REQ-012, REQ-013, REQ-014_

  - [x] 4.3 定义 `ParallelNodeDef`、`ApprovalNodeDef`、`LoopNodeDef`
    - ParallelNodeDef 含 `join_strategy`（all/any/majority）与 `fail_fast`
    - ApprovalNodeDef 含 `assignees` / `allowed_actions` / `on_timeout` / `escalate_to` / `next_on_approve` / `next_on_reject`
    - LoopNodeDef 含 `iterator_expr` / `condition_expr` / `max_iterations`（默认 100）
    - 将 `NodeDef` 定义为 Union 类型
    - _Requirements: REQ-015, REQ-016, REQ-017_

  - [x] 4.4 定义 `WorkflowDefinition` 顶层模型
    - 字段：key / version / name / description / input_schema / output_schema / nodes / edges / start_node / end_nodes / global_timeout_seconds / max_concurrent_nodes（默认 8）
    - _Requirements: REQ-006, REQ-010, REQ-071_

- [x] 5. 定义运行时模型
  - [x] 5.1 定义 `WorkflowContext`
    - 字段：instance_id / workflow_key / version / inputs / outputs / variables / node_statuses / node_attempts / current_nodes / created_at / updated_at
    - 提供 `model_dump()` 和 `model_validate()` 互为逆（round-trip）
    - _Requirements: REQ-022_

  - [x] 5.2 定义 `NodeResult`、`AssigneeSpec`、`ApprovalRecord`、`InstanceStatusView`
    - NodeResult：node_id / status / output / error / attempt / started_at / ended_at
    - AssigneeSpec：type / identifier / display_name
    - ApprovalRecord：id / instance_id / node_id / action / actor_id / assignee_snapshot / comment / delegate_to / metadata / created_at
    - _Requirements: REQ-028, REQ-031, REQ-034_

- [x] 6. Checkpoint 1 — Phase A 验收
  - Ensure all tests pass, ask the user if questions arise.
  - 确认 `backend/harness/workflow/` 可被正常 import，Pydantic 模型校验正常
  - 未修改任何现有 Harness 模块

---

### Phase B: 持久化层（Persistence）

- [x] 7. 数据库 schema 迁移
  - [x] 7.1 编写 SQL 脚本创建 6 张表
    - 文件：`backend/database/migrations/002_add_workflow_tables.sql`
    - 表：`workflow_definitions`、`workflow_instances`、`workflow_node_executions`、`workflow_approval_records`、`workflow_approval_tasks`、`workflow_state_events`
    - 包含所有 UNIQUE / INDEX / FOREIGN KEY 约束（见 design.md §数据库表结构）
    - 注意：`workflow_node_executions.execution_id` 必须 UNIQUE（幂等基础）
    - _Requirements: REQ-021, REQ-024_

  - [x] 7.2 编写 Python 迁移执行脚本
    - 文件：`backend/database/migrations/run_workflow_migration.py`
    - 复用 `backend/database/db_utils.py` 的连接方式
    - 支持幂等执行（检查表是否已存在再建表）
    - _Requirements: REQ-021_

- [x] 8. 实现 PersistenceManager 基础
  - [x] 8.1 创建 `persistence.py` 骨架与连接复用
    - 基于 `backend/database/db_utils.py` 的 `get_db_connection()` context manager
    - 所有 SQL 使用 `%s` 参数化占位符，禁止字符串拼接
    - _Requirements: REQ-021, REQ-057_

  - [x] 8.2 实现定义 CRUD
    - `save_definition(definition) -> int`（计算 SHA-256 写入 spec_hash）
    - `load_definition(definition_id) -> WorkflowDefinition`
    - `load_definition_by_key(key, version=None) -> WorkflowDefinition`（version=None 取最新 active）
    - `deactivate_definition(definition_id)`（软删除）
    - 捕获 UNIQUE 冲突抛 `DuplicateDefinitionError`
    - _Requirements: REQ-001, REQ-010, REQ-026_

  - [x] 8.3 实现实例 CRUD
    - `create_instance(definition_id, inputs, trigger_source, trigger_user) -> UUID`
    - `load_instance(instance_id) -> WorkflowInstance`
    - `update_instance_status(instance_id, status, error=None)`
    - `update_instance_context(instance_id, context_json)`（节点粒度 flush）
    - `find_resumable_instances() -> list[UUID]`（状态 ∈ {RUNNING, WAITING_APPROVAL, SUSPENDED} 且租约过期）
    - _Requirements: REQ-002, REQ-022, REQ-023_

- [x] 9. 实现租约机制
  - [x] 9.1 实现 `try_acquire_lease` / `renew_lease` / `release_lease`
    - `try_acquire_lease(instance_id, owner, ttl_seconds) -> bool` 基于乐观锁 UPDATE WHERE (lease_owner IS NULL OR lease_expires_at < NOW())
    - `renew_lease(instance_id, owner, ttl_seconds)` 续约
    - `release_lease(instance_id, owner)` 释放（仅持有者可释放）
    - _Requirements: REQ-025_

  - [ ]* 9.2 Write property test for P11: 租约互斥
    - **Property 11: 同一 instance_id 在任意时刻至多一个 owner 持有合法租约**
    - **Validates: REQ-025, REQ-070**
    - 文件：`backend/tests/workflow/properties/test_property_p11_lease_mutex.py`
    - 使用 `hypothesis` + `asyncio.gather` 模拟多进程并发 acquire，断言 成功数 ≤ 1
    - _Requirements: REQ-070_

- [x] 10. 实现节点执行、审批、事件 CRUD
  - [x] 10.1 实现 `workflow_node_executions` 读写
    - `save_node_execution(instance_id, node_id, execution_id, status, ...)` 捕获 UNIQUE 冲突视为"已由其他进程写入"
    - `update_node_execution(execution_id, status, output, error, ended_at)`
    - `list_node_executions(instance_id) -> list[NodeExecution]`
    - _Requirements: REQ-024, REQ-050_

  - [x] 10.2 实现 `workflow_approval_records` / `workflow_approval_tasks` 读写
    - `insert_approval_record(...)`（只追加，禁止 UPDATE/DELETE）
    - `upsert_approval_task(...)`
    - `list_approval_tasks(assignee_type, assignee_id, status)` 走组合索引
    - `find_timed_out_tasks(now)` 走 `(status, due_at)` 索引
    - _Requirements: REQ-029, REQ-030, REQ-031, REQ-033_

  - [x] 10.3 实现 `workflow_state_events` 读写
    - `append_state_event(instance_id, node_id, event_type, from_status, to_status, payload)`
    - `list_state_events(instance_id, event_type=None) -> list[StateEvent]`
    - 禁止 DELETE / UPDATE（仅追加）
    - _Requirements: REQ-020, REQ-042, REQ-058_

  - [ ]* 10.4 Write property test for P3: 节点执行幂等性
    - **Property 3: ∀ execution_id, COUNT(workflow_node_executions WHERE execution_id = ?) ≤ 1**
    - **Validates: REQ-024, REQ-062**
    - 文件：`backend/tests/workflow/properties/test_property_p3_execution_idempotency.py`
    - 生成随机 execution_id 序列（含重复）并发插入，断言 DB 最多 1 行

- [x] 11. Checkpoint 2 — Phase B 验收
  - Ensure all tests pass, ask the user if questions arise.
  - 运行迁移脚本验证 6 张表建好
  - 单元测试覆盖所有 PersistenceManager 方法

---

### Phase C: 核心引擎（Core Engine）

- [x] 12. 实现 StateMachine
  - [x] 12.1 在 `state_machine.py` 定义转换表与核心函数
    - 按 design.md §状态机转换 定义 `WORKFLOW_TRANSITIONS` 和 `NODE_TRANSITIONS`
    - `transition_workflow(current, event) -> WorkflowStatus`，非法转换抛 `IllegalTransitionError`
    - `transition_node(current, event) -> NodeStatus`
    - 保证纯函数：不访问 DB，不产生副作用
    - _Requirements: REQ-018, REQ-019_

  - [ ]* 12.2 Write property test for P2: 状态转换合法性
    - **Property 2: ∀ history produced by StateMachine, ∀ i, sᵢ₊₁ ∈ TRANSITIONS[sᵢ]；终态吸收**
    - **Validates: REQ-018, REQ-019, REQ-061**
    - 文件：`backend/tests/workflow/properties/test_property_p2_state_transitions.py`
    - Hypothesis 生成随机事件序列，断言每步要么合法要么抛 `IllegalTransitionError`；进入终态后任何事件抛异常
    - _Requirements: REQ-061_

- [x] 13. 实现 WorkflowContext 序列化与表达式求值
  - [x] 13.1 在 `context.py` 实现 WorkflowContext 的增量 diff 序列化
    - `to_json()` / `from_json()` 保证 round-trip
    - `apply_node_output(node_id, output)` 更新 outputs + node_statuses
    - 大 context（> 1MB）做增量 diff（对比上次快照）
    - _Requirements: REQ-022_

  - [x] 13.2 在 `expressions.py` 实现 Jinja2 沙箱渲染
    - 使用 `jinja2.sandbox.SandboxedEnvironment`
    - 禁用 `extends` / `import` / `include` 语句，仅支持 `{{ }}` 表达式
    - 禁止访问 `os`、`sys`、`subprocess`、`__import__`、`open`、`eval`、`exec`、`__class__`、`__mro__`
    - 引用不存在的 key 抛 `TemplateRenderError`（不静默返回 None）
    - 包装函数 `render_params(params_dict, context) -> dict`
    - 包装函数 `render_bool(expr, context) -> bool`
    - _Requirements: REQ-009, REQ-054, REQ-055_

  - [ ]* 13.3 Write property test for P9: 参数模板求值安全性
    - **Property 9: 所有恶意模板抛异常，引用不存在 key 抛 TemplateRenderError，无文件/网络副作用**
    - **Validates: REQ-054, REQ-068_**
    - 文件：`backend/tests/workflow/properties/test_property_p9_template_sandbox.py`
    - Hypothesis 生成含 `os.system` / `__import__` / `{"".__class__}` / 不存在 key 的模板，断言全部抛异常
    - _Requirements: REQ-068_

  - [ ]* 13.4 Write property test for P4: 持久化-内存一致性（context 部分）
    - **Property 4: parse_obj(model_dump(ctx)) == ctx（round-trip）**
    - **Validates: REQ-022, REQ-063**
    - 文件：`backend/tests/workflow/properties/test_property_p4_context_roundtrip.py`
    - 用 Hypothesis 生成随机 WorkflowContext，验证序列化 round-trip 保持相等
    - _Requirements: REQ-063_

- [x] 14. 实现 WorkflowLoader
  - [x] 14.1 实现 YAML/JSON/dict 加载
    - `from_yaml_file(path) -> WorkflowDefinition`
    - `from_json_file(path) -> WorkflowDefinition`
    - `from_dict(spec) -> WorkflowDefinition`
    - 捕获 Pydantic ValidationError 包装为 `SchemaValidationError`（异常信息含字段路径）
    - _Requirements: REQ-006_

  - [x] 14.2 实现 DAG 无环性校验（Kahn 算法）
    - `validate_dag_acyclic(nodes, edges) -> list[str]`（返回拓扑序）
    - 含环抛 `CyclicGraphError`（异常携带至少一个环的节点列表，用 DFS 定位）
    - 边引用不存在的节点抛 `InvalidNodeRefError`
    - `LoopNode` 的循环体不视为环（显式标记）
    - _Requirements: REQ-007_

  - [x] 14.3 实现 `WorkflowLoader.validate()` 顶层校验
    - 调用 DAG 校验 + 校验 start_node 存在 + 推断 end_nodes
    - 校验 `input_schema` / `output_schema` 本身是合法 JSON Schema
    - _Requirements: REQ-006, REQ-008_

  - [ ]* 14.4 Write property test for P1: DAG 无环性
    - **Property 1: WorkflowLoader.load 成功 ⟺ 定义是 DAG（与独立 DFS 环检测器对拍）**
    - **Validates: REQ-007, REQ-060_**
    - 文件：`backend/tests/workflow/properties/test_property_p1_dag_acyclic.py`
    - Hypothesis 生成随机节点+边，与独立实现的 DFS 环检测器对比结果
    - _Requirements: REQ-060_

- [x] 15. 实现 DAGExecutor 基础框架
  - [x] 15.1 实现调度器骨架与就绪队列
    - `DAGExecutor.execute(instance, context)` 主循环（见 design.md §算法 1 主循环）
    - `_compute_initial_ready_nodes(context)` 入度 0 节点
    - `_resolve_successors(node_id, context)` 处理普通边 + DecisionNode 条件边
    - 仅支持 TaskNode 调用的占位（实际 TaskNode 实现在 Phase D）
    - 未实现 Parallel / Approval / Loop（返回 NotImplementedError 占位）
    - _Requirements: REQ-005_

  - [x] 15.2 实现节点粒度持久化与状态事件
    - 每个节点完成后调用 `PersistenceManager.update_instance_context()` flush
    - 每次状态转换写 `workflow_state_events`
    - 保证 "flush 完成后下游读到" 的读后写一致性
    - _Requirements: REQ-020, REQ-022, REQ-058_

  - [x] 15.3 实现 `max_concurrent_nodes` 限流
    - 主循环中用 `asyncio.wait(..., return_when=FIRST_COMPLETED)` 控制并发
    - 同时运行的节点数 ≤ `definition.max_concurrent_nodes`
    - _Requirements: REQ-005, REQ-071_

- [x] 16. Checkpoint 3 — Phase C 验收
  - Ensure all tests pass, ask the user if questions arise.
  - 能加载 YAML 定义、校验 DAG、在内存中打印拓扑序
  - StateMachine 所有合法/非法转换单元测试通过

---

### Phase D: 节点类型（Nodes）

- [ ] 17. 实现 BaseNode 抽象基类
  - 在 `nodes/base.py` 定义 `BaseNode`（Pydantic BaseModel + ABC 混合）
  - 抽象方法 `async run(ctx: WorkflowContext) -> NodeResult`
  - 抽象方法 `validate() -> None`
  - 公共字段：id / type / name / depends_on / retry_policy / timeout_seconds / on_error
  - 实现公共的重试循环与超时包装（见 design.md §算法 1）
  - _Requirements: REQ-049, REQ-050, REQ-051, REQ-072_

- [ ] 18. 实现 TaskNode 三种调用路径
  - [ ] 18.1 实现 TaskNode - Tool 路径
    - 在 `nodes/task.py` 实现 `call_kind="tool"`：通过 `ToolRegistry.execute(target, rendered_params)` 调用
    - 工具不存在抛 `ToolNotFoundError`
    - 渲染 params 用 Jinja2 沙箱
    - 结果写入 `context.outputs[output_key or node.id]`
    - _Requirements: REQ-011, REQ-035_

  - [ ] 18.2 实现 TaskNode - Agent 路径
    - 实现 `call_kind="agent"`：通过 `Orchestrator` 查找 agent_id 并调用 `AgentLoop.run(task, context)`
    - Agent 不存在抛 `AgentNotFoundError`
    - 不修改现有 AgentLoop 的 ReAct 实现
    - 复用现有 Memory 实例（不新建）
    - _Requirements: REQ-012, REQ-035, REQ-036_

  - [ ] 18.3 实现 TaskNode - Skill 路径
    - 实现 `call_kind="skill"`：解析 `"module.path:ClassName"` 格式，import 后调用 `execute(**rendered_params)`
    - 格式非法或类不存在抛 `SkillLoadError`
    - _Requirements: REQ-013, REQ-035_

  - [ ] 18.4 集成 SecurityManager 权限审计
    - 节点执行前调用 `SecurityManager` 对 `target` 审计
    - SENSITIVE 目标非 ApprovalNode 前置保护则抛 `PermissionError`
    - 审计事件写入 `workflow_state_events`
    - _Requirements: REQ-037_

  - [ ]* 18.5 Write unit tests for TaskNode 三种路径
    - 使用 mock ToolRegistry / Orchestrator 验证三种 call_kind
    - 覆盖异常分支（工具/Agent/Skill 不存在、超时、渲染失败）
    - _Requirements: REQ-011, REQ-012, REQ-013_

- [ ] 19. 实现 DecisionNode
  - [ ] 19.1 在 `nodes/decision.py` 实现决策节点
    - 按 branches 顺序求值 Jinja2 条件，取第一个 True 的分支 next（见 design.md §算法 2）
    - 全不匹配且 `default_next` 为空抛 `NoMatchingBranchError`
    - 写入 `context.outputs[node.id] = {"next": next_node_id}`
    - _Requirements: REQ-014_

  - [ ] 19.2 将 DecisionNode 接入 DAGExecutor 分支路由
    - `_resolve_successors` 读取 DecisionNode 输出决定就绪节点
    - _Requirements: REQ-005, REQ-014_

  - [ ]* 19.3 Write property test for P8: 决策节点确定性
    - **Property 8: 同 context 多次求值返回相同分支，按 branches 顺序短路**
    - **Validates: REQ-014, REQ-067_**
    - 文件：`backend/tests/workflow/properties/test_property_p8_decision_determinism.py`
    - Hypothesis 生成随机 branches + context，验证求值引用透明 & 第一个匹配者胜出
    - _Requirements: REQ-067_

- [ ] 20. 实现 ParallelNode
  - [ ] 20.1 在 `nodes/parallel.py` 实现并行节点
    - 使用 `asyncio.gather` 并发调度 branches
    - 实现三种 `join_strategy`：all / any / majority
    - 实现 `fail_fast=true` 时取消其他分支（发出 `CancelledError`）
    - _Requirements: REQ-015_

  - [ ] 20.2 将 ParallelNode 接入 DAGExecutor
    - 作为子 DAG 嵌套调度，不破坏 `max_concurrent_nodes` 总上限
    - _Requirements: REQ-005, REQ-015_

  - [ ]* 20.3 Write property test for P7: ParallelNode Join 正确性
    - **Property 7: join_strategy ∈ {all, any, majority} 的等价条件；fail_fast 触发 CancelledError**
    - **Validates: REQ-015, REQ-066_**
    - 文件：`backend/tests/workflow/properties/test_property_p7_parallel_join.py`
    - Hypothesis 生成随机成功/失败分支组合，断言 parallel_node.status 与 join_strategy 一致
    - _Requirements: REQ-066_

- [ ] 21. 实现 ApprovalNode（骨架）
  - 在 `nodes/approval.py` 实现审批节点骨架
  - `run()` 调用 `ApprovalManager.request_approval()` 获得 `asyncio.Event`，`await event.wait()` 挂起
  - 被唤醒后从 DB 读结果写 `context.outputs[node.id] = {approved, record_id}`
  - 实际 ApprovalManager 实现在 Phase E，此处先定义接口依赖
  - _Requirements: REQ-016_

- [ ] 22. 实现 LoopNode（可选，P2 优先级）
  - 在 `nodes/loop.py` 实现循环节点
  - 支持 `iterator_expr`（列表迭代）和 `condition_expr`（while）两种模式
  - 强制 `max_iterations` 上限（默认 100），超过则节点 FAILED
  - 每次迭代写 `$loop_item` 和 `$loop_index` 到 `context.variables`
  - _Requirements: REQ-017_

- [ ] 23. Checkpoint 4 — Phase D 验收
  - Ensure all tests pass, ask the user if questions arise.
  - 能执行 Task+Decision+Parallel 三类节点组合的线性 DAG
  - ApprovalNode 可挂起但唤醒机制依赖 Phase E

---

### Phase E: 审批系统（Approval Subsystem）

- [ ] 24. 实现 AssigneeResolver（3 种处理人类型）
  - 在 `approval/assignee.py` 实现 `resolve_assignees(assignees, delegate_chain) -> set[str]`
  - USER 类型：identifier 视为唯一用户 ID
  - SHARED_ACCOUNT 类型：展开共享账号的实际用户（复用现有用户体系；若无则先返回 `{identifier}` 并 TODO）
  - ROLE 类型：展开角色下所有成员（同上处理）
  - `check_permission(actor_id, node) -> bool` 用于 `take_action` 鉴权
  - _Requirements: REQ-028, REQ-056_

- [ ] 25. 实现 ApprovalManager 核心
  - [ ] 25.1 在 `approval/manager.py` 实现骨架
    - `request_approval(instance_id, node, context) -> asyncio.Event`：创建 pending task、返回 Event
    - 内存维护 `_events: dict[(instance_id, node_id), asyncio.Event]`
    - 断点恢复时由 `rebuild_approval_event` 重新创建 Event，若 DB 已有终结动作则立刻 `event.set()`
    - _Requirements: REQ-016, REQ-023_

  - [ ] 25.2 实现 `take_action` 入口（含事务）
    - 单 DB 事务内：插入 approval_records + 更新 approval_tasks + 写 state_events + 必要时更新 instance
    - 任一步失败回滚，只在提交后 `event.set()`
    - `action ∉ node.allowed_actions` 抛 `IllegalActionError`
    - `actor_id` 不在处理人集合抛 `PermissionError`
    - _Requirements: REQ-027, REQ-032, REQ-033, REQ-056_

- [ ] 26. 实现 12 种审批动作处理器
  - [ ] 26.1 实现终结动作 APPROVE / REJECT / REJECT_RETURN / WITHDRAW
    - APPROVE：节点 COMPLETED，`outputs.{node_id} = {approved: true, record_id}`，唤醒
    - REJECT：节点 COMPLETED，`outputs.{node_id} = {approved: false, record_id}`，唤醒
    - REJECT_RETURN：节点 COMPLETED，引擎按退回路径前进（重开前一审批节点）
    - WITHDRAW：仅 `actor_id == instance.trigger_user` 可执行，实例 CANCELLED，唤醒所有等待节点
    - _Requirements: REQ-027_

  - [ ] 26.2 实现流转动作 DELEGATE / FORWARD / RETRIEVE / SAVE / SUBMIT
    - DELEGATE：新 task 指向 delegate_to，原任务置 delegated，节点保持 WAITING_APPROVAL
    - FORWARD：新增并列 task 给 delegate_to
    - RETRIEVE：仅无 claimed 任务时允许，把 pending tasks 重置为 draft
    - SAVE：仅持久化草稿，不改节点状态、不唤醒
    - SUBMIT：把草稿提交为 pending
    - _Requirements: REQ-027, REQ-034_

  - [ ] 26.3 实现阅示/扩展动作 READ / ACK / CUSTOM
    - READ、ACK：仅记录历史，不改节点状态
    - CUSTOM：预留扩展，`metadata_json` 承载业务语义
    - _Requirements: REQ-027_

  - [ ] 26.4 实现 `list_pending_tasks` 与视图对象
    - 返回包含 instance_id / node_id / workflow_key / workflow_name / due_at / created_at / context 摘要
    - 支持 ROLE 类型的成员展开
    - 分页参数（page / page_size，默认 50）
    - _Requirements: REQ-030, REQ-047_

- [ ] 27. 实现审批超时扫描
  - [ ] 27.1 实现 `check_timeouts()` 周期任务
    - 每分钟扫描 `due_at < now AND status = 'pending'` 的任务
    - 按 `on_timeout` 策略执行：auto_approve / auto_reject / escalate（新 task 给 escalate_to）/ fail
    - 写审批记录时 `actor_id = 'system'`
    - _Requirements: REQ-029_

  - [ ] 27.2 将 `check_timeouts` 接入 WorkflowEngine 启动流程
    - 后台 `asyncio.Task` 每 60s 触发
    - _Requirements: REQ-029_

- [ ]* 28. Write property test for P6: 审批流转完整性
  - **Property 6: ApprovalRecord 只追加、节点必达终态、actor_id 必在 resolve_assignees**
  - **Validates: REQ-027, REQ-031, REQ-032, REQ-065_**
  - 文件：`backend/tests/workflow/properties/test_property_p6_approval_integrity.py`
  - Hypothesis 生成随机审批动作序列（含无效动作），验证无效被拒、有效序列产生单调不减记录、节点终态一致
  - _Requirements: REQ-065_

- [ ] 29. Checkpoint 5 — Phase E 验收
  - Ensure all tests pass, ask the user if questions arise.
  - 能在线性 DAG 中插入 ApprovalNode 并通过 API 调用 `take_action` 唤醒后续执行
  - 所有 12 种动作有对应单元测试

---

### Phase F: 引擎门面与集成（Engine Facade & Integration）

- [ ] 30. 实现 WorkflowEngine 门面
  - [ ] 30.1 实现 `register_definition` / `start` / `get_status`
    - `register_definition` 调用 `WorkflowLoader.validate` + `PersistenceManager.save_definition`
    - `start` 用 jsonschema 校验 inputs、创建 instance、启动 DAGExecutor
    - `get_status` 返回 instance + node 快照一致性视图（单事务或读快照）
    - _Requirements: REQ-001, REQ-002, REQ-004, REQ-008_

  - [ ] 30.2 实现 `suspend` / `resume` / `cancel`
    - suspend：合法转换 RUNNING/EXECUTING → SUSPENDED，flush context
    - resume：重建 ready_queue 并继续调度（见 Task 31）
    - cancel：向所有运行中 asyncio.Task 发 CancelledError，置 CANCELLED
    - 所有操作写 `workflow_state_events`
    - _Requirements: REQ-003_

  - [ ] 30.3 实现 `WorkflowEngine.from_env` 装配
    - 内部装配 PersistenceManager / ApprovalManager / WorkflowMonitor / CallbackManager / StructuredLogger
    - 不修改现有 Harness 模块的公共接口
    - _Requirements: REQ-038, REQ-075_

- [ ] 31. 实现断点恢复（算法 4）
  - [ ] 31.1 实现 `resume_instance(instance_id)` 完整流程
    - 步骤：try_acquire_lease → load_instance → load_definition → 重建 ready_queue → executor.execute
    - 崩溃遗留的 RUNNING 节点标记为 PENDING 重新执行（由 execution_id 保证幂等）
    - 退出时 finally 释放租约
    - _Requirements: REQ-023, REQ-024, REQ-025_

  - [ ] 31.2 实现进程启动时扫描可恢复实例
    - `WorkflowEngine.start_background_tasks()` 调用 `find_resumable_instances`
    - 对每个实例尝试 acquire_lease，抢到者执行 resume，未抢到跳过
    - _Requirements: REQ-023_

  - [ ]* 31.3 Write property test for P5: 断点恢复幂等性
    - **Property 5: ∀ instance, resume k 次（k ∈ [1..5]）产生相同终态与输出**
    - **Validates: REQ-023, REQ-064_**
    - 文件：`backend/tests/workflow/properties/test_property_p5_resume_idempotency.py`
    - 构造状态快照，随机 resume 次数，断言最终 status / outputs 相同
    - _Requirements: REQ-064_

- [ ] 32. 实现错误处理与降级
  - [ ] 32.1 实现节点失败策略（FAIL_WORKFLOW / SKIP / RETRY / GO_TO）
    - 在 DAGExecutor 的 `_on_node_failed` 分发到对应策略
    - RETRY 按 retry_policy 指数退避，每次重试新增一条 workflow_node_executions 记录
    - GO_TO 跳转到指定节点继续
    - _Requirements: REQ-049, REQ-050_

  - [ ] 32.2 实现 DB 错误降级
    - `PersistenceManager.flush` 失败时指数退避（1s/3s/5s）重试最多 3 次
    - 3 次全失败置实例 SUSPENDED 并通过 CallbackManager 发 WARNING 告警
    - _Requirements: REQ-052_

  - [ ] 32.3 实现节点超时
    - `asyncio.wait_for` 包装节点执行，默认 `timeout_seconds=300`
    - 超时视为可重试错误（若 retry_policy 允许）
    - _Requirements: REQ-051_

- [ ] 33. 集成 CallbackManager 和 StructuredLogger
  - 所有工作流级事件（workflow_started/completed/failed/cancelled/suspended/resumed）通过 `CallbackManager.publish`
  - 所有节点级事件（node_started/completed/failed/skipped/approval_requested/approval_action）同样发布
  - `StructuredLogger` 日志含 instance_id / workflow_key / node_id / event_type / correlation_id
  - 不修改 CallbackManager 和 StructuredLogger 的接口
  - _Requirements: REQ-038, REQ-058, REQ-073_

- [ ] 34. Checkpoint 6 — Phase F 验收
  - Ensure all tests pass, ask the user if questions arise.
  - 能完整跑通："注册 → 启动 → 审批挂起 → 进程重启 → resume → 完成"
  - 现有 ExceptionAgent / QuotationAgent 路径不受影响（回归测试通过）

---

### Phase G: 监控与 API（Monitoring & API）

- [ ] 35. 实现 WorkflowMonitor
  - [ ] 35.1 实现指标聚合
    - 内存维护运行中实例数 / 每分钟启动数 / 完成数 / 失败数 / 平均执行时长
    - 按 workflow_key 维度聚合
    - _Requirements: REQ-040, REQ-073_

  - [ ] 35.2 实现超时告警
    - 实例运行时长 > `global_timeout_seconds` 时通过 CallbackManager 发 WARNING
    - 审批任务接近超时（剩余 10%）时发预警
    - _Requirements: REQ-041_

- [ ] 36. 实现 WebSocket 实时推送
  - [ ] 36.1 实现订阅管理
    - 内存字典 `_subscriptions: dict[UUID, set[WebSocket]]`
    - `subscribe(instance_id, websocket)` / `unsubscribe(websocket)`（断开时自动清理）
    - 不持久化订阅列表
    - _Requirements: REQ-039_

  - [ ] 36.2 实现状态事件推送
    - 监听 `workflow_state_events` 新增，推送给订阅者
    - 每个 instance 独立通道
    - _Requirements: REQ-020, REQ-039_

- [ ] 37. 实现 FastAPI 路由
  - [ ] 37.1 创建 `backend/api/routes/workflow.py` 基础路由
    - `POST /api/workflow/start`
    - `GET  /api/workflow/{instance_id}`
    - `POST /api/workflow/{instance_id}/approve`
    - `GET  /api/workflow/tasks`（待办查询，支持 page / page_size）
    - 所有参数用 Pydantic request models 校验
    - _Requirements: REQ-044, REQ-045, REQ-046, REQ-047_

  - [ ] 37.2 实现管理接口（挂起 / 恢复 / 取消）
    - `POST /api/workflow/{instance_id}/suspend`
    - `POST /api/workflow/{instance_id}/resume`
    - `POST /api/workflow/{instance_id}/cancel`
    - 异常映射：IllegalTransitionError → 409、PermissionError → 403、InstanceNotFoundError → 404
    - _Requirements: REQ-003, REQ-048_

  - [ ] 37.3 实现监控接口
    - `GET  /api/workflow/metrics`（JSON 指标）
    - `GET  /api/workflow/{instance_id}/events?event_type=...`（事件回放）
    - `GET  /api/workflow/health`（MySQL 可达 → 200，否则 503）
    - `WS   /api/workflow/{instance_id}/stream`
    - _Requirements: REQ-040, REQ-042, REQ-043_

  - [ ] 37.4 在 `backend/main.py` 挂载 workflow router
    - 仅新增 `app.include_router(workflow.router)`，不修改现有路由
    - 确保现有 `/api/...` 端点行为不变
    - _Requirements: REQ-075_

- [ ] 38. Checkpoint 7 — Phase G 验收
  - Ensure all tests pass, ask the user if questions arise.
  - 所有 HTTP + WebSocket 接口通过 httpx TestClient 集成测试
  - 现有接口回归测试通过

---

### Phase H: 测试与验证（Testing & Verification）

- [ ] 39. 创建异常分析工作流 YAML
  - 新建 `backend/workflows/` 目录
  - 创建 `backend/workflows/exception_analysis_v1.yaml`（严格按 design.md §YAML/JSON 工作流示例）
  - 节点：validate_input / parallel_analyze / exception_analyze / rag_search / responsibility / confidence_check / solution_recommend / human_review / approval_1 / execute_solution / update_db / mark_cancelled
  - 注册所需的 tool（validate_exception_input / create_human_review_task / execute_approved_solution / update_exception_record）到 ToolRegistry
  - _Requirements: REQ-059_

- [ ] 40. 编写端到端集成测试
  - [ ] 40.1 异常分析工作流 - 审批通过路径
    - 文件：`backend/tests/workflow/integration/test_exception_analysis_approve_path.py`
    - 启动工作流 → 执行到 approval_1 → 调用审批 API APPROVE → 验证最终状态 COMPLETED + update_db 执行
    - 使用 stub Agent/Skill 避免依赖真实 LLM
    - _Requirements: REQ-059_

  - [ ] 40.2 异常分析工作流 - 审批拒绝路径
    - 文件：`backend/tests/workflow/integration/test_exception_analysis_reject_path.py`
    - 启动 → 审批 REJECT → 验证 mark_cancelled 执行、实例 COMPLETED（业务取消）
    - _Requirements: REQ-059_

  - [ ] 40.3 低置信度路径
    - 置信度 < 70% 触发 human_review 分支，后续同样进入 approval_1
    - _Requirements: REQ-014, REQ-059_

- [ ] 41. 编写断点恢复集成测试
  - 文件：`backend/tests/workflow/integration/test_crash_recovery.py`
  - 场景 1：节点执行中 kill 进程 → 重启 → 验证 resume 后结果一致
  - 场景 2：WAITING_APPROVAL 时 kill → 重启 → 重新创建 Event → 审批后继续
  - 场景 3：多进程并发 resume 同一实例 → 只有一个成功
  - _Requirements: REQ-023, REQ-025_

- [ ]* 42. Write property test for P10: 资源上限
  - **Property 10: ∀ 实例任意时刻 同时运行节点数 ≤ max_concurrent_nodes；∀ LoopNode 迭代次数 ≤ max_iterations**
  - **Validates: REQ-017, REQ-069_**
  - 文件：`backend/tests/workflow/properties/test_property_p10_resource_limits.py`
  - Hypothesis 生成含大量可并行节点的 DAG，插桩记录并发峰值，断言 ≤ max_concurrent_nodes
  - _Requirements: REQ-069_

- [ ]* 43. 性能测试
  - 文件：`backend/tests/workflow/performance/test_workflow_performance.py`
  - 并发启动 100 个简单 10 节点工作流，断言 10 秒内全部进入 RUNNING
  - 单实例 50 并行节点，断言平均节点调度延迟 ≤ 100ms
  - context ≤ 1MB 时 flush 耗时 ≤ 50ms
  - 10 万量级 pending tasks 的待办查询 ≤ 200ms
  - _Requirements: REQ-071_

- [ ]* 44. 编写覆盖率补全单元测试
  - 对 `executor.py` / `state_machine.py` 补充缺失分支覆盖（目标 ≥ 95%）
  - 对 `approval/manager.py` 补充 12 种动作的边界测试
  - _Requirements: REQ-027_

- [ ] 45. Checkpoint 8 — 最终验收
  - Ensure all tests pass, ask the user if questions arise.
  - 异常分析工作流 YAML 能端到端通过（审批通过 + 拒绝 + 低置信度 三条路径）
  - 现有 ExceptionAgent / QuotationAgent 单元与集成测试全部通过（REQ-075）
  - 数据库只新增 6 张 workflow_* 表，未修改现有表
  - FastAPI 现有路由的 schema 与行为不变

---

## Notes

- 带 `*` 的任务为**可选**（主要是属性测试与性能测试），跳过不影响 MVP 功能，但影响 P1–P11 正确性属性的覆盖。
- 属性测试一律使用 `hypothesis` + `pytest-asyncio`，放在 `backend/tests/workflow/properties/`。
- 集成测试放在 `backend/tests/workflow/integration/`。
- 所有新代码集中在 `backend/harness/workflow/`、`backend/api/routes/workflow.py`、`backend/workflows/`、`backend/database/migrations/002_add_workflow_tables.sql`、`backend/tests/workflow/`。
- Phase A–C 完成后可完整演示"YAML → DAG → 线性 Task → 持久化 → 查询"MVP；Phase F 完成后完整流程（含审批与断点恢复）可用。
- 检查点（Checkpoint）是人工确认节点：请先运行已完成任务的测试，再推进下一阶段。
