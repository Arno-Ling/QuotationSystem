# Requirements Document

## Introduction

Harness Workflow Engine 是在现有 Harness AI Agent 框架基础上扩展的**有向无环图（DAG）工作流编排引擎**，用于支持"图纸上传 → Agent 分析 → 建议生成 → 人工审批 → 自动执行"这类跨 Agent、跨 Skill、跨人工环节的长程业务流程。

本文档基于已批准的 `design.md` 派生出完整的功能性与非功能性需求。需求组织方式为：按业务/技术领域分组，每组按优先级标注 **P0（必须）**、**P1（重要）**、**P2（可选）**。所有验收标准遵循 EARS（Easy Approach to Requirements Syntax）语法，每条需求必须可验证、可追溯。

需求分组总览：

| 分组 | 编号范围 | 优先级 | 说明 |
|------|----------|--------|------|
| 引擎核心 API | REQ-001 ~ REQ-005 | P0 | 引擎门面对外契约 |
| 工作流定义与加载 | REQ-006 ~ REQ-010 | P0 | YAML/JSON/Python 声明式定义 |
| 节点类型 | REQ-011 ~ REQ-017 | P0/P2 | 五类核心节点 |
| 状态管理 | REQ-018 ~ REQ-020 | P0 | 状态机转换约束 |
| 持久化与恢复 | REQ-021 ~ REQ-026 | P0 | 断点恢复、幂等、租约 |
| 审批系统 | REQ-027 ~ REQ-034 | P0 | 12 种动作、3 种处理人 |
| Harness 集成 | REQ-035 ~ REQ-038 | P0 | 复用现有能力 |
| 监控与告警 | REQ-039 ~ REQ-043 | P1 | WebSocket 实时推送 |
| API 接口 | REQ-044 ~ REQ-048 | P0 | FastAPI 路由 |
| 错误处理 | REQ-049 ~ REQ-053 | P0 | 重试、超时、降级 |
| 安全 | REQ-054 ~ REQ-058 | P0 | 鉴权、沙箱、审计 |
| 业务场景 | REQ-059 | P0 | 异常分析工作流验证 |
| 正确性属性 | REQ-060 ~ REQ-070 | P0 | P1–P11 对应需求 |
| 非功能性需求 | REQ-071 ~ REQ-075 | P1 | 性能、可观测性、兼容性 |

---

## Glossary

- **Workflow_Engine**：引擎门面，对外提供工作流注册、启动、挂起、恢复、取消、查询能力（对应 `harness.workflow.engine.WorkflowEngine`）。
- **Workflow_Loader**：工作流加载器，从 YAML/JSON/dict/Python 对象加载定义并做语法与无环性校验（对应 `harness.workflow.loader.WorkflowLoader`）。
- **DAG_Executor**：DAG 调度器，负责拓扑排序、节点调度、上下文传递与失败处理（对应 `harness.workflow.executor.DAGExecutor`）。
- **State_Machine**：状态机，执行工作流级与节点级状态转换校验（对应 `harness.workflow.state_machine.StateMachine`）。
- **Persistence_Manager**：持久化管理器，负责所有 MySQL 读写、租约、断点恢复（对应 `harness.workflow.persistence.PersistenceManager`）。
- **Approval_Manager**：审批管理器，处理 12 种审批动作、处理人解析、超时与升级（对应 `harness.workflow.approval.manager.ApprovalManager`）。
- **Workflow_Monitor**：监控器，发布状态事件、维护 WebSocket 订阅、汇总指标（对应 `harness.workflow.monitor.WorkflowMonitor`）。
- **Task_Node**：任务节点，通过 `call_kind` 调用 Tool/Agent/Skill。
- **Decision_Node**：决策节点，按条件选择一个后继分支。
- **Parallel_Node**：并行节点，使用 `asyncio.gather` 并发执行多个子节点。
- **Approval_Node**：审批节点，挂起工作流等待外部审批事件。
- **Loop_Node**：循环节点，按迭代器或条件重复执行子节点集。
- **Workflow_Definition**：声明式工作流定义（`key + version` 唯一）。
- **Workflow_Instance**：工作流运行时实例，由 `start()` 创建。
- **Workflow_Context**：贯穿整个执行的数据总线，包含 `inputs`、`outputs`、`variables`、`node_statuses` 等字段。
- **Execution_ID**：节点执行的唯一幂等键（对应 `workflow_node_executions.execution_id`）。
- **Assignee_Spec**：审批处理人规范，包含 `type`（USER/SHARED_ACCOUNT/ROLE）与 `identifier`。
- **Approval_Action**：12 种审批动作枚举（SAVE/SUBMIT/RETRIEVE/APPROVE/REJECT_RETURN/REJECT/WITHDRAW/READ/ACK/DELEGATE/FORWARD/CUSTOM）。
- **Lease**：实例租约（`lease_owner` + `lease_expires_at`），保证同一实例在同一时刻至多一个进程执行。
- **EARS**：Easy Approach to Requirements Syntax，需求描述的六种规范模式。
- **PBT**：Property-Based Testing（基于 Hypothesis 的属性测试）。
- **终态**：工作流的 COMPLETED / FAILED / CANCELLED；节点的 COMPLETED / FAILED / SKIPPED。

---

## Requirements

## 一、引擎核心 API（P0）

### REQ-001: 注册工作流定义

**User Story:** As a 采购委外系统开发者, I want 通过 `WorkflowEngine.register_definition()` 注册一个工作流定义, so that 该定义能被后续启动调用并按版本唯一追加。

#### Acceptance Criteria

1. WHEN 调用方以合法的 `WorkflowDefinition` 调用 `register_definition`, THE Workflow_Engine SHALL 将定义持久化到 `workflow_definitions` 表并返回 `definition_id > 0`。
2. WHEN 注册的 `(key, version)` 已存在于 `workflow_definitions` 表, THE Workflow_Engine SHALL 拒绝注册并抛出 `DuplicateDefinitionError`。
3. IF 传入的 `WorkflowDefinition` 未通过 `Workflow_Loader.validate()`（含无环性校验）, THEN THE Workflow_Engine SHALL 抛出对应的校验异常并不写入任何 DB 记录。
4. WHEN 注册成功, THE Workflow_Engine SHALL 在 `workflow_definitions.spec_hash` 写入定义 JSON 的 SHA-256 值以支持去重查询。
5. THE Workflow_Engine SHALL 支持对同一 `key` 追加新的 `version`，且新旧版本共存（旧版本不被覆盖）。

### REQ-002: 启动工作流实例

**User Story:** As a 采购委外系统开发者, I want 通过 `start(workflow_key, inputs)` 创建并启动一个工作流实例, so that 业务流程能从 `start_node` 开始执行。

#### Acceptance Criteria

1. WHEN 调用方传入存在的 `workflow_key` 且 `version` 为 `None`, THE Workflow_Engine SHALL 选取 `is_active=1` 的最新版本作为运行定义。
2. IF 传入 `workflow_key` 在 `workflow_definitions` 表不存在或无活跃版本, THEN THE Workflow_Engine SHALL 抛出 `DefinitionNotFoundError`。
3. IF 传入 `inputs` 未通过定义的 `input_schema` JSON Schema 校验, THEN THE Workflow_Engine SHALL 抛出 `SchemaValidationError` 且不创建实例。
4. WHEN 启动成功, THE Workflow_Engine SHALL 在 `workflow_instances` 表创建一行状态为 PENDING 或 RUNNING 的记录，`context.inputs` 等于传入的 `inputs`。
5. WHEN 启动成功, THE Workflow_Engine SHALL 向 `workflow_state_events` 追加一条 `event_type='workflow_started'` 事件。
6. THE Workflow_Engine SHALL 在调用链中复用现有 `StructuredLogger` 记录启动日志，包含 `instance_id`、`workflow_key`、`trigger_user`。

### REQ-003: 挂起、恢复、取消工作流实例

**User Story:** As a 运维工程师, I want 通过 API 主动挂起/恢复/取消运行中的实例, so that 在发现问题时能及时介入。

#### Acceptance Criteria

1. WHEN 调用 `suspend(instance_id, reason)` 且实例状态为 RUNNING 或 EXECUTING, THE Workflow_Engine SHALL 将 `status` 置为 SUSPENDED、持久化 `context`、记录 `reason`。
2. WHEN 调用 `resume(instance_id)` 且实例状态 ∈ {SUSPENDED, WAITING_APPROVAL}, THE Workflow_Engine SHALL 按 §算法 4 重建 `ready_queue` 并继续调度。
3. IF 调用 `resume(instance_id)` 且实例当前状态 ∉ {SUSPENDED, WAITING_APPROVAL, RUNNING（崩溃遗留）}, THEN THE Workflow_Engine SHALL 抛出 `IllegalTransitionError` 且不修改状态。
4. WHEN 调用 `cancel(instance_id, reason)` 且实例非终态, THE Workflow_Engine SHALL 将 `status` 置为 CANCELLED、设置 `ended_at`、取消所有运行中 asyncio Task（发出 `CancelledError`）。
5. IF 调用 `cancel(instance_id, reason)` 且实例已处于终态（COMPLETED/FAILED/CANCELLED）, THEN THE Workflow_Engine SHALL 抛出 `IllegalTransitionError`。
6. WHEN 挂起/恢复/取消发生, THE Workflow_Engine SHALL 向 `workflow_state_events` 追加对应事件并通过 Workflow_Monitor 推送到已订阅的 WebSocket。

### REQ-004: 查询工作流实例状态

**User Story:** As a 运维工程师, I want 通过 `get_status(instance_id)` 查询实例的当前状态与节点快照, so that 能够了解当前进度。

#### Acceptance Criteria

1. WHEN 调用 `get_status(instance_id)`, THE Workflow_Engine SHALL 返回包含 `status`、`current_nodes`、每个节点 `node_status`、`started_at`、`ended_at`、`error_message` 的视图对象。
2. IF 传入 `instance_id` 不存在, THEN THE Workflow_Engine SHALL 抛出 `InstanceNotFoundError`。
3. THE Workflow_Engine SHALL 保证 `get_status` 的返回值来自 `workflow_instances` 与 `workflow_node_executions` 两张表的一致性视图（单次查询事务或读一致性快照）。

### REQ-005: DAG 调度执行

**User Story:** As a 采购委外系统开发者, I want DAG_Executor 根据依赖关系自动调度节点, so that 可并行的节点并行执行、受并发上限约束。

#### Acceptance Criteria

1. WHEN DAG_Executor 开始执行实例, THE DAG_Executor SHALL 通过 Kahn 拓扑排序计算初始就绪队列（入度为 0 的节点集合）。
2. WHILE 就绪队列非空且运行中任务数 < `definition.max_concurrent_nodes`, THE DAG_Executor SHALL 从就绪队列取节点、标记 RUNNING、创建 asyncio.Task 并持久化 `workflow_node_executions`。
3. WHEN 一个节点完成, THE DAG_Executor SHALL 基于其后继边（含 DecisionNode 条件求值结果）计算新就绪节点并入队。
4. THE DAG_Executor SHALL 保证同时运行的节点数不超过 `definition.max_concurrent_nodes`。
5. WHEN 所有可达节点都处于 {COMPLETED, SKIPPED}, THE DAG_Executor SHALL 将实例置为 COMPLETED 并返回。
6. IF 某节点状态变为 FAILED 且其 `on_error = FAIL_WORKFLOW`, THEN THE DAG_Executor SHALL 取消其余运行中任务并将实例置为 FAILED。
7. WHEN 任一节点状态变为 WAITING_APPROVAL, THE DAG_Executor SHALL flush `context`、将实例状态置为 WAITING_APPROVAL 并让出协程直到被唤醒。

---

## 二、工作流定义与加载（P0）

### REQ-006: 声明式 YAML/JSON 工作流定义

**User Story:** As a 业务分析师, I want 用 YAML 或 JSON 声明工作流, so that 不写 Python 代码即可描述业务流程。

#### Acceptance Criteria

1. WHEN 调用 `WorkflowLoader.from_yaml_file(path)`, THE Workflow_Loader SHALL 将 YAML 文件解析为 `WorkflowDefinition` 对象。
2. WHEN 调用 `WorkflowLoader.from_json_file(path)` 或 `from_dict(dict)`, THE Workflow_Loader SHALL 产生与 YAML 等价的 `WorkflowDefinition` 对象。
3. IF YAML/JSON 内容不满足 `WorkflowDefinition` Pydantic 模型, THEN THE Workflow_Loader SHALL 抛出 `SchemaValidationError`，异常信息包含具体字段路径。
4. FOR ALL 合法 `WorkflowDefinition` 对象, 序列化为 YAML 后再反序列化 SHALL 产生语义等价的定义（round-trip 属性）。
5. THE Workflow_Loader SHALL 支持 Python API 方式直接构造 `WorkflowDefinition`（用于动态定义场景）。

### REQ-007: DAG 无环性校验

**User Story:** As a 测试工程师, I want 工作流加载时立即发现环, so that 避免运行时死循环。

#### Acceptance Criteria

1. WHEN `WorkflowLoader.validate()` 运行, THE Workflow_Loader SHALL 对 `nodes + edges` 执行 Kahn 拓扑排序。
2. IF DAG 含有任何环（含自环）, THEN THE Workflow_Loader SHALL 抛出 `CyclicGraphError`，异常携带至少一个环的节点列表。
3. IF `edges` 中某条边的 `from` 或 `to` 不在 `nodes` 集合, THEN THE Workflow_Loader SHALL 抛出 `InvalidNodeRefError`。
4. WHEN 校验通过, THE Workflow_Loader SHALL 返回合法的拓扑序列（节点 id 列表）且列表长度等于 `|nodes|`。
5. THE Workflow_Loader SHALL 不把 `LoopNode` 的循环体视为环（`LoopNode` 是显式受控循环）。

### REQ-008: 输入输出 Schema 校验

**User Story:** As a 业务分析师, I want 为工作流声明 `input_schema` 和 `output_schema`, so that 非法输入在启动前就被拒绝。

#### Acceptance Criteria

1. WHEN `input_schema` 非空且启动实例, THE Workflow_Engine SHALL 使用 `jsonschema` 库校验 `inputs` 符合 `input_schema`。
2. IF `inputs` 不满足 `input_schema`, THEN THE Workflow_Engine SHALL 抛出 `SchemaValidationError` 且不创建实例。
3. WHEN 工作流到达 `end_nodes` 且 `output_schema` 非空, THE Workflow_Engine SHALL 校验最终 `context.outputs` 符合 `output_schema`，不符合则将实例置为 FAILED。
4. THE Workflow_Engine SHALL 允许 `input_schema` 或 `output_schema` 为空对象（表示不做校验）。

### REQ-009: 参数模板求值

**User Story:** As a 业务分析师, I want 在节点 `params` 中用 `{{ outputs.xxx.field }}` 引用上游输出, so that 节点间数据传递不需要硬编码。

#### Acceptance Criteria

1. WHEN 节点开始执行, THE DAG_Executor SHALL 使用 Jinja2 `SandboxedEnvironment` 渲染 `params` 中的模板表达式。
2. THE expressions 模块 SHALL 禁用 Jinja2 的 `extends`、`import`、`include` 语句及对内建函数 `os`、`__import__`、`open` 的访问。
3. WHEN 模板引用的 context key 不存在, THE expressions 模块 SHALL 抛出 `TemplateRenderError` 而不是静默返回 `None` 或 `Undefined`。
4. IF 模板表达式执行过程中抛出任何异常, THEN THE expressions 模块 SHALL 将其包装为 `TemplateRenderError` 并作为节点执行错误处理。
5. THE expressions 模块 SHALL 仅支持 `{{ }}` 表达式语法，禁用 `{% %}` 语句标签。

### REQ-010: 工作流定义版本管理

**User Story:** As a 运维工程师, I want 同一工作流可以迭代多个版本共存, so that 升级时不影响正在运行的旧版本实例。

#### Acceptance Criteria

1. WHEN 注册新版本定义, THE Workflow_Engine SHALL 保持旧版本的 `is_active=1` 不变，除非调用方显式设置旧版本 `is_active=0`。
2. WHEN 一个实例启动后, THE Workflow_Engine SHALL 把 `definition_id` 写入 `workflow_instances.definition_id` 并在整个生命周期内始终使用该版本的定义。
3. THE Workflow_Engine SHALL 禁止通过 UPDATE 修改已注册的 `spec_json`（防止运行时语义漂移）。
4. THE Workflow_Engine SHALL 支持软删除（`is_active=0`）但禁止物理删除 `workflow_definitions` 行。

---

## 三、节点类型（P0 / P2）

### REQ-011: TaskNode — Tool 调用（P0）

**User Story:** As a 采购委外系统开发者, I want `TaskNode` 通过 `call_kind='tool'` 调用 `ToolRegistry` 中注册的工具, so that 现有工具函数可直接被工作流复用。

#### Acceptance Criteria

1. WHEN `TaskNode.call_kind = 'tool'` 且节点执行, THE Task_Node SHALL 通过 `ToolRegistry.execute(target, rendered_params)` 调用对应工具。
2. IF `target` 对应的工具在 `ToolRegistry` 不存在, THEN THE Task_Node SHALL 抛出 `ToolNotFoundError` 并按 `on_error` 策略处理。
3. WHEN 工具返回成功, THE Task_Node SHALL 将返回值写入 `context.outputs[node.output_key or node.id]`。
4. WHEN 工具执行时间超过 `timeout_seconds`, THE Task_Node SHALL 抛出 `asyncio.TimeoutError` 并按 `retry_policy` / `on_error` 处理。

### REQ-012: TaskNode — Agent 调用（P0）

**User Story:** As a 采购委外系统开发者, I want `TaskNode` 通过 `call_kind='agent'` 调用注册在 `Orchestrator` 的 Agent（如 `ExceptionAgent`）, so that 工作流能编排多 Agent 协作。

#### Acceptance Criteria

1. WHEN `TaskNode.call_kind = 'agent'` 且节点执行, THE Task_Node SHALL 通过 `Orchestrator` 查找 `target` 对应的 `AgentLoop` 并调用其 `run(task, context)` 方法。
2. IF `target` 对应的 Agent 不存在, THEN THE Task_Node SHALL 抛出 `AgentNotFoundError` 并按 `on_error` 策略处理。
3. THE Task_Node SHALL 将 Agent 的 ReAct 循环结果作为节点输出写入 `context.outputs`。
4. THE Task_Node SHALL 复用现有 `AgentLoop` 的内部机制而不修改其 ReAct 实现。

### REQ-013: TaskNode — Skill 调用（P0）

**User Story:** As a 采购委外系统开发者, I want `TaskNode` 通过 `call_kind='skill'` 以 `module:ClassName` 格式直接调用 Skill 类, so that 细粒度能力可被精准复用。

#### Acceptance Criteria

1. WHEN `TaskNode.call_kind = 'skill'` 且节点执行, THE Task_Node SHALL 解析 `target` 格式 `"module.path:ClassName"` 并导入类后调用其 `execute()` 方法。
2. IF `target` 格式不合法或类不存在, THEN THE Task_Node SHALL 抛出 `SkillLoadError`。
3. THE Task_Node SHALL 把 `rendered_params` 作为关键字参数传给 Skill 的 `execute()` 方法。
4. THE Task_Node SHALL 将 Skill 返回值写入 `context.outputs`。

### REQ-014: DecisionNode 条件分支（P0）

**User Story:** As a 业务分析师, I want `DecisionNode` 按条件选择后继路径, so that 工作流能实现分支决策。

#### Acceptance Criteria

1. WHEN `DecisionNode` 执行, THE Decision_Node SHALL 按 `branches` 列表顺序逐个求值 Jinja2 条件表达式，取第一个为 `True` 的分支的 `next`。
2. WHEN 所有 `branches.condition` 均为 `False` 且 `default_next` 非空, THE Decision_Node SHALL 选择 `default_next` 作为后继。
3. IF 所有分支均不匹配且 `default_next` 为 `None`, THEN THE Decision_Node SHALL 抛出 `NoMatchingBranchError`。
4. THE Decision_Node SHALL 对同一 `context` 的多次求值返回相同结果（引用透明性）。
5. THE Decision_Node SHALL 将选中的后继节点 id 写入 `context.outputs[node.id] = {"next": next_node_id}`。

### REQ-015: ParallelNode 并行执行（P0）

**User Story:** As a 业务分析师, I want `ParallelNode` 并发执行多个子节点, so that 独立的分析任务可同时进行。

#### Acceptance Criteria

1. WHEN `ParallelNode` 执行, THE Parallel_Node SHALL 通过 `asyncio.gather` 并发调度 `branches` 中的所有子节点。
2. WHERE `join_strategy = 'all'`, THE Parallel_Node SHALL 当且仅当所有子节点状态为 COMPLETED 时变为 COMPLETED。
3. WHERE `join_strategy = 'any'`, THE Parallel_Node SHALL 当至少一个子节点 COMPLETED 时变为 COMPLETED。
4. WHERE `join_strategy = 'majority'`, THE Parallel_Node SHALL 当 COMPLETED 子节点数 > `|branches| / 2` 时变为 COMPLETED。
5. IF `fail_fast = true` 且任一子节点 FAILED, THEN THE Parallel_Node SHALL 对其余运行中的子节点发出 `CancelledError`。
6. WHERE `fail_fast = false`, THE Parallel_Node SHALL 等待所有子节点结束（不论成败）再根据 `join_strategy` 判定自身状态。

### REQ-016: ApprovalNode 人工审批节点（P0）

**User Story:** As a 审批人, I want 工作流执行到审批节点时挂起, so that 人工审批后再继续后续步骤。

#### Acceptance Criteria

1. WHEN `ApprovalNode` 开始执行, THE Approval_Node SHALL 调用 `ApprovalManager.request_approval()` 创建待办任务、返回 `asyncio.Event` 并将节点状态置为 WAITING_APPROVAL。
2. WHEN 节点进入 WAITING_APPROVAL, THE Approval_Node SHALL 触发 DAG_Executor 将实例状态置为 WAITING_APPROVAL 并让出协程。
3. WHEN 审批事件被 `take_action()` 触发, THE Approval_Node SHALL 从 DB 读取审批结果写入 `context.outputs[node.id] = {approved: bool, record_id: UUID}`。
4. THE Approval_Node SHALL 支持 `next_on_approve` 与 `next_on_reject` 两种后继路径，通过 edge.condition 引用 `outputs.{node_id}.approved`。
5. IF `timeout_seconds` 设置且超时发生, THEN THE Approval_Node SHALL 按 `on_timeout` 策略（auto_approve/auto_reject/escalate/fail）处理。

### REQ-017: LoopNode 循环节点（P2）

**User Story:** As a 业务分析师, I want 使用 `LoopNode` 对集合或条件循环执行一组节点, so that 能表达批量处理逻辑。

#### Acceptance Criteria

1. WHEN `LoopNode.iterator_expr` 非空, THE Loop_Node SHALL 对 Jinja2 表达式求值得到的列表的每个元素，执行 `body` 节点集一次。
2. WHEN `LoopNode.condition_expr` 非空, THE Loop_Node SHALL 在 `condition_expr` 求值为 `True` 时循环执行 `body`，直到为 `False` 或达到 `max_iterations`。
3. THE Loop_Node SHALL 保证迭代次数不超过 `max_iterations`（默认 100），达到上限时节点标记为 FAILED。
4. THE Loop_Node SHALL 在每次迭代将当前迭代值写入 `context.variables['$loop_item']` 和迭代序号写入 `context.variables['$loop_index']`。

---

## 四、状态管理（P0）

### REQ-018: 工作流级状态机

**User Story:** As a 测试工程师, I want 工作流状态转换严格遵守状态机, so that 非法转换被立即拒绝。

#### Acceptance Criteria

1. THE State_Machine SHALL 按 design.md §状态机转换中的 `WORKFLOW_TRANSITIONS` 表定义合法转换集。
2. IF 请求从状态 `s` 经事件 `e` 转换到状态 `s'` 且 `s' ∉ WORKFLOW_TRANSITIONS[s]`, THEN THE State_Machine SHALL 抛出 `IllegalTransitionError`。
3. THE State_Machine SHALL 将 COMPLETED、FAILED、CANCELLED 作为终态，不允许从终态向其他任何状态转换。
4. THE State_Machine SHALL 是纯函数：不读写数据库，不产生副作用。

### REQ-019: 节点级状态机

**User Story:** As a 测试工程师, I want 节点状态转换严格遵守状态机, so that 节点生命周期可预测。

#### Acceptance Criteria

1. THE State_Machine SHALL 按 design.md §状态机转换中的 `NODE_TRANSITIONS` 表定义合法节点转换集。
2. IF 请求节点从状态 `s` 经事件 `e` 转换到 `s'` 且 `s' ∉ NODE_TRANSITIONS[s]`, THEN THE State_Machine SHALL 抛出 `IllegalTransitionError`。
3. THE State_Machine SHALL 将节点的 COMPLETED、FAILED、SKIPPED 作为终态。
4. WHEN 一个 FAILED 节点被重试, THE Persistence_Manager SHALL 新增一条 `workflow_node_executions` 记录（`attempt` 递增）而不修改旧记录。

### REQ-020: 状态事件发布

**User Story:** As a 运维工程师, I want 每次状态变更都记录为事件, so that 审计链完整。

#### Acceptance Criteria

1. WHEN 工作流或节点发生状态转换, THE DAG_Executor SHALL 向 `workflow_state_events` 追加一条带 `occurred_at`（毫秒精度）、`from_status`、`to_status`、`payload_json` 的事件。
2. THE Persistence_Manager SHALL 禁止物理删除 `workflow_state_events` 中的任何行。
3. WHEN 状态事件落库成功, THE Workflow_Monitor SHALL 向已订阅该 `instance_id` 的 WebSocket 客户端推送事件。

---

## 五、持久化与恢复（P0）

### REQ-021: MySQL 持久化表结构

**User Story:** As a 采购委外系统开发者, I want 所有工作流数据持久化在 MySQL, so that 与现有系统统一数据栈。

#### Acceptance Criteria

1. THE Persistence_Manager SHALL 使用 design.md §数据库表结构定义的 6 张表（`workflow_definitions`、`workflow_instances`、`workflow_node_executions`、`workflow_approval_records`、`workflow_approval_tasks`、`workflow_state_events`）。
2. THE Persistence_Manager SHALL 对 `workflow_node_executions.execution_id` 建立 UNIQUE 约束。
3. THE Persistence_Manager SHALL 对 `workflow_definitions` 的 `(key, version)` 建立 UNIQUE 约束。
4. THE Persistence_Manager SHALL 复用 `backend/database/db_utils.py` 中的 `pymysql` 参数化查询模式。
5. THE Persistence_Manager SHALL 在所有 JSON 字段中存储由 Pydantic `model_dump_json()` 产出的内容。

### REQ-022: 上下文持久化

**User Story:** As a 测试工程师, I want `WorkflowContext` 能完整序列化与反序列化, so that 断点恢复后语义等价。

#### Acceptance Criteria

1. WHEN 任一节点完成, THE DAG_Executor SHALL 将最新 `context` 持久化到 `workflow_instances.context_json`（节点粒度 flush）。
2. FOR ALL 合法的 `WorkflowContext` 对象, `parse_obj(model_dump(ctx)) == ctx` SHALL 成立（round-trip 属性）。
3. THE Persistence_Manager SHALL 对大 `context`（> 1MB）使用增量 diff 持久化以减少写入量。
4. WHEN 节点完成且 `context_json` 持久化成功, THE Persistence_Manager SHALL 保证下游节点读取时能看到该输出（读后写一致性）。

### REQ-023: 断点恢复

**User Story:** As a 运维工程师, I want 进程崩溃后自动恢复未完成的实例, so that 长程流程不因故障重来。

#### Acceptance Criteria

1. WHEN 进程启动, THE Workflow_Engine SHALL 调用 `find_resumable_instances()` 扫描状态 ∈ {RUNNING, WAITING_APPROVAL, SUSPENDED} 且租约过期或无租约的实例。
2. WHEN 恢复一个实例, THE Workflow_Engine SHALL 按 design.md §算法 4 重建 `ready_queue`（跳过已 COMPLETED/SKIPPED 节点，重跑崩溃遗留的 RUNNING 节点）。
3. WHEN 恢复的实例上次卡在 `ApprovalNode`, THE Approval_Manager SHALL 重新创建 `asyncio.Event`；若 DB 中对应审批已终结，则立刻触发 `event.set()`。
4. FOR ALL 可恢复实例, 执行 `resume()` 多次 SHALL 产生相同的终态（幂等性）。

### REQ-024: 节点级幂等性（Execution ID 保护）

**User Story:** As a 测试工程师, I want 节点级别的幂等保护, so that 断点恢复重复执行不产生重复副作用。

#### Acceptance Criteria

1. WHEN 节点开始执行, THE DAG_Executor SHALL 为该次执行分配唯一 `execution_id`（UUID v4）。
2. FOR ALL `execution_id`, `workflow_node_executions` 表中记录数 SHALL 不超过 1（UNIQUE 约束保证）。
3. WHEN 断点恢复后重复执行同一节点, THE DAG_Executor SHALL 使用新的 `execution_id` 创建新记录；旧的崩溃遗留记录由 `resume` 时清理为 FAILED 或保留。
4. WHEN 同一 `execution_id` 因并发写入重复, THE Persistence_Manager SHALL 捕获唯一约束冲突并将该次执行视为"已由其他进程完成"，读取原结果。

### REQ-025: 租约互斥

**User Story:** As a 运维工程师, I want 同一实例在多进程部署下由单一进程执行, so that 避免数据竞争。

#### Acceptance Criteria

1. WHEN 一个进程尝试执行某实例, THE Persistence_Manager SHALL 通过 `try_acquire_lease(instance_id, owner, ttl)` 在 `workflow_instances.lease_owner` 与 `lease_expires_at` 上使用乐观锁抢占。
2. IF 租约已被其他进程持有且未过期, THEN THE Persistence_Manager SHALL 返回抢占失败；调用方抛出 `InstanceLockedError`。
3. THE Workflow_Engine SHALL 在执行期间定期（< ttl / 2）续期租约以防过期。
4. WHEN 执行结束（成功、失败或挂起）, THE Workflow_Engine SHALL 调用 `release_lease()` 清空 `lease_owner` 与 `lease_expires_at`。
5. FOR ALL 时刻, 同一 `instance_id` 的合法租约持有者数量 SHALL ≤ 1。

### REQ-026: 工作流定义软删除

**User Story:** As a 运维工程师, I want 下线旧版本工作流定义而不影响历史实例, so that 升级平滑。

#### Acceptance Criteria

1. WHEN 调用方将 `workflow_definitions.is_active` 置为 0, THE Workflow_Engine SHALL 拒绝以该版本启动新实例，但允许继续执行已运行的实例。
2. THE Persistence_Manager SHALL 禁止物理删除 `workflow_definitions`、`workflow_instances`、`workflow_node_executions`、`workflow_approval_records`、`workflow_state_events` 行。

---

## 六、审批系统（P0）

### REQ-027: 12 种审批动作

**User Story:** As a 审批人, I want 执行 12 种不同的审批动作, so that 能覆盖企业审批场景。

#### Acceptance Criteria

1. THE Approval_Manager SHALL 支持以下 12 种 `ApprovalAction`: `SAVE`、`SUBMIT`、`RETRIEVE`、`APPROVE`、`REJECT_RETURN`、`REJECT`、`WITHDRAW`、`READ`、`ACK`、`DELEGATE`、`FORWARD`、`CUSTOM`。
2. WHEN 执行 `APPROVE` 动作, THE Approval_Manager SHALL 把节点状态置为 COMPLETED、写入 `outputs.{node_id} = {approved: true, record_id}`、调用 `event.set()` 唤醒引擎。
3. WHEN 执行 `REJECT` 动作, THE Approval_Manager SHALL 把节点置为 COMPLETED、写入 `outputs.{node_id} = {approved: false, record_id}`、唤醒引擎。
4. WHEN 执行 `REJECT_RETURN` 动作, THE Approval_Manager SHALL 把节点置为 COMPLETED 并使引擎按退回路径（如前一审批节点或起草人）前进。
5. WHEN 执行 `WITHDRAW` 动作且 `actor_id == instance.trigger_user`, THE Approval_Manager SHALL 把实例置为 CANCELLED 并唤醒所有等待中的节点。
6. WHEN 执行 `DELEGATE` 动作, THE Approval_Manager SHALL 在 `workflow_approval_tasks` 创建指向 `delegate_to` 的新任务、当前任务置 `delegated`；节点保持 WAITING_APPROVAL。
7. WHEN 执行 `FORWARD` 动作, THE Approval_Manager SHALL 在 `workflow_approval_tasks` 创建指向 `delegate_to` 的新并列任务；节点保持 WAITING_APPROVAL。
8. WHEN 执行 `SAVE` 动作, THE Approval_Manager SHALL 仅持久化审批草稿（comment 与元数据），不改变节点状态且不唤醒引擎。
9. WHEN 执行 `RETRIEVE` 动作且无任何任务处于 `claimed` 状态, THE Approval_Manager SHALL 把所有待办任务置回 `pending`，节点保持 WAITING_APPROVAL。
10. WHEN 执行 `READ` 或 `ACK` 动作, THE Approval_Manager SHALL 仅记录审批历史，不改变节点状态。
11. THE Approval_Manager SHALL 为 `CUSTOM` 动作预留扩展位，允许业务系统在 `metadata_json` 写入自定义语义。
12. IF 传入的 `action ∉ node.allowed_actions`, THEN THE Approval_Manager SHALL 抛出 `IllegalActionError`。

### REQ-028: 3 种处理人类型

**User Story:** As a 审批人, I want 能以单账号、账号共享、角色共享三种方式被指派, so that 覆盖不同组织结构。

#### Acceptance Criteria

1. THE Approval_Manager SHALL 支持 `AssigneeType` 枚举值 `USER`（单账号）、`SHARED_ACCOUNT`（账号共享）、`ROLE`（角色共享）。
2. WHEN `AssigneeSpec.type = USER`, THE Approval_Manager SHALL 将 `identifier` 视为唯一用户 ID，仅该用户可操作。
3. WHEN `AssigneeSpec.type = SHARED_ACCOUNT`, THE Approval_Manager SHALL 允许共享该账号的多个实际用户任一人执行动作；记录实际操作 `actor_id`。
4. WHEN `AssigneeSpec.type = ROLE`, THE Approval_Manager SHALL 允许该角色代码下所有成员任一人操作；记录 `actor_id` 与角色快照。
5. IF `actor_id` 不属于节点 `assignees` 解析出的实际用户集合（含委托链）, THEN THE Approval_Manager SHALL 抛出 `PermissionError`。

### REQ-029: 审批超时处理

**User Story:** As a 运维工程师, I want 审批超时按策略自动处理, so that 流程不会无限期等待。

#### Acceptance Criteria

1. WHEN `ApprovalNodeDef.timeout_seconds` 设置且节点等待时长超过该值, THE Approval_Manager SHALL 按 `on_timeout` 策略处理。
2. WHERE `on_timeout = 'auto_approve'`, THE Approval_Manager SHALL 自动追加 APPROVE 记录（`actor_id = 'system'`）并唤醒引擎。
3. WHERE `on_timeout = 'auto_reject'`, THE Approval_Manager SHALL 自动追加 REJECT 记录并唤醒引擎。
4. WHERE `on_timeout = 'escalate'` 且 `escalate_to` 非空, THE Approval_Manager SHALL 为 `escalate_to` 创建新的待办任务，保持节点 WAITING_APPROVAL。
5. WHERE `on_timeout = 'fail'`, THE Approval_Manager SHALL 将节点置为 FAILED 并按 `on_error` 策略传播。
6. THE Approval_Manager SHALL 通过后台任务 `check_timeouts()` 每分钟扫描 `workflow_approval_tasks.due_at < now` 且 `status = 'pending'` 的任务。

### REQ-030: 待办查询

**User Story:** As a 审批人, I want 查询"我的待办"列表, so that 了解需要处理的审批任务。

#### Acceptance Criteria

1. WHEN 调用 `list_pending_tasks(assignee_type, assignee_id)`, THE Approval_Manager SHALL 返回该处理人所有 `status = 'pending'` 的任务视图列表。
2. THE Approval_Manager SHALL 通过 `workflow_approval_tasks` 表的索引 `(assignee_type, assignee_id, status)` 实现快速查询。
3. WHEN `assignee_type = ROLE`, THE Approval_Manager SHALL 解析角色成员并返回该角色下所有 pending 任务。
4. THE Approval_Manager SHALL 在视图中包含 `instance_id`、`node_id`、`workflow_key`、`workflow_name`、`due_at`、`created_at`、关键 context 摘要。

### REQ-031: 审批历史不可篡改

**User Story:** As a 合规审计员, I want 审批历史只追加不可修改, so that 满足审计要求。

#### Acceptance Criteria

1. THE Persistence_Manager SHALL 禁止对 `workflow_approval_records` 执行 UPDATE 和 DELETE 操作。
2. WHEN 任一审批动作执行, THE Approval_Manager SHALL 在同一 DB 事务内向 `workflow_approval_records` 插入新记录且不修改任何历史记录。
3. THE Approval_Manager SHALL 为每条审批记录写入 `actor_id`、`assignee_snapshot`、`action`、`created_at`、`comment`，提供完整追溯链。

### REQ-032: 审批节点终结保证

**User Story:** As a 测试工程师, I want 每个审批节点最终必到达终态, so that 流程可收敛。

#### Acceptance Criteria

1. FOR ALL 审批节点 `n` 在其生命周期内, 存在终结动作 ∈ {APPROVE, REJECT, REJECT_RETURN, WITHDRAW} 或超时处理 SHALL 使 `n.status` 最终变为 COMPLETED 或 SKIPPED。
2. THE Approval_Manager SHALL 不允许一个审批节点无限期停留在 WAITING_APPROVAL 且无任何动作或超时配置。

### REQ-033: 事务性审批动作

**User Story:** As a 测试工程师, I want 审批动作在单事务内完成, so that 出现系统故障不产生部分写入。

#### Acceptance Criteria

1. WHEN 执行 `take_action()`, THE Approval_Manager SHALL 在单个 DB 事务内完成：(a) 插入 `workflow_approval_records`、(b) 更新 `workflow_approval_tasks`、(c) 更新 `workflow_state_events`、(d) 必要时更新 `workflow_instances` 状态。
2. IF 事务中任一步骤失败, THEN THE Approval_Manager SHALL 回滚整个事务并向调用方抛出错误。
3. THE Approval_Manager SHALL 仅在事务提交成功后调用 `asyncio.Event.set()` 唤醒引擎。

### REQ-034: 委托链追踪

**User Story:** As a 合规审计员, I want 追踪一个审批经过了多少次委托/直送, so that 审计签署人链路。

#### Acceptance Criteria

1. WHEN 执行 `DELEGATE` 或 `FORWARD` 动作, THE Approval_Manager SHALL 在 `workflow_approval_records.delegate_to` 写入目标人、在 `metadata_json` 写入原始 `assignee` 快照。
2. WHEN 终结动作（APPROVE/REJECT/REJECT_RETURN）发生, THE Approval_Manager SHALL 能通过查询 `workflow_approval_records` 按时间序重建完整的委托链。

---

## 七、Harness 集成（P0）

### REQ-035: TaskNode 调用路径适配

**User Story:** As a 采购委外系统开发者, I want `TaskNode` 作为适配器调用现有 Harness 能力, so that 不重复实现业务逻辑。

#### Acceptance Criteria

1. THE Task_Node SHALL 支持通过 `call_kind` ∈ {`tool`, `agent`, `skill`, `callable`} 调度到不同调用路径。
2. THE Task_Node SHALL 保证现有单 Agent ReAct 循环（`AgentLoop`）与单 Skill 调用路径行为不被修改。
3. THE Task_Node SHALL 复用现有 `ToolRegistry` 的工具注册机制，不要求用户重新注册已有工具。

### REQ-036: 复用 Memory 模块

**User Story:** As a 采购委外系统开发者, I want 工作流执行复用现有 `Memory` 模块, so that Agent 的短期记忆和长期记忆（ChromaDB）自动可用。

#### Acceptance Criteria

1. WHEN `TaskNode` 执行 Agent/Skill 且该 Agent 依赖 `Memory`, THE Task_Node SHALL 传入现有 `Memory` 实例而不自行创建新实例。
2. THE Workflow_Engine SHALL 不修改 `Memory` 模块的接口。

### REQ-037: 复用 SecurityManager

**User Story:** As a 采购委外系统开发者, I want 工具权限审计沿用 `SecurityManager`, so that 敏感操作由统一机制管控。

#### Acceptance Criteria

1. WHEN `TaskNode` 执行前, THE DAG_Executor SHALL 调用 `SecurityManager` 对 `target`（工具/Agent/Skill）进行权限审计。
2. IF `SecurityManager` 判定目标为 `SENSITIVE` 级别且当前节点非 `ApprovalNode` 前置保护, THEN THE DAG_Executor SHALL 拒绝执行并抛出 `PermissionError`。
3. THE DAG_Executor SHALL 记录 `SecurityManager` 的所有审计事件到 `workflow_state_events`。

### REQ-038: 复用 Callback 与 Logger

**User Story:** As a 运维工程师, I want 工作流所有事件走现有 `CallbackManager` 和 `StructuredLogger`, so that 观测栈统一。

#### Acceptance Criteria

1. WHEN 任一工作流事件发生（start/complete/fail/state_change）, THE Workflow_Engine SHALL 通过 `CallbackManager` 发布事件。
2. THE Workflow_Engine SHALL 使用现有 `StructuredLogger` 记录日志，日志字段至少包含 `instance_id`、`workflow_key`、`node_id`、`event_type`。

---

## 八、监控与告警（P1）

### REQ-039: WebSocket 实时推送

**User Story:** As a 运维工程师, I want 通过 WebSocket 实时订阅某实例的状态变化, so that 前端能展示实时进度。

#### Acceptance Criteria

1. WHEN 客户端连接 `/api/workflow/{instance_id}/stream` WebSocket, THE Workflow_Monitor SHALL 将该连接加入该 `instance_id` 的订阅列表。
2. WHEN 任一 `workflow_state_events` 落库成功, THE Workflow_Monitor SHALL 向所有订阅该 `instance_id` 的 WebSocket 客户端推送事件 JSON。
3. THE Workflow_Monitor SHALL 订阅列表仅保存在内存中，不持久化到 DB。
4. WHEN WebSocket 客户端断开, THE Workflow_Monitor SHALL 从订阅列表移除该连接，不产生资源泄漏。

### REQ-040: 指标统计

**User Story:** As a 运维工程师, I want 查询工作流聚合指标, so that 了解系统整体运行状况。

#### Acceptance Criteria

1. THE Workflow_Monitor SHALL 维护以下指标：运行中实例数、每分钟启动数、每分钟完成数、每分钟失败数、平均执行时长。
2. THE Workflow_Monitor SHALL 提供 `/api/workflow/metrics` HTTP 接口返回上述指标（JSON 格式）。
3. THE Workflow_Monitor SHALL 对 `workflow_key` 维度聚合指标。

### REQ-041: 超时告警

**User Story:** As a 运维工程师, I want 工作流或审批超时触发告警, so that 及时介入处理。

#### Acceptance Criteria

1. WHEN 一个实例运行时长超过 `global_timeout_seconds`, THE Workflow_Monitor SHALL 通过日志（WARNING 级别）和 CallbackManager 发出告警事件。
2. WHEN 审批任务接近超时阈值（例如剩余 10%）, THE Workflow_Monitor SHALL 发出预警事件。

### REQ-042: 事件回放

**User Story:** As a 运维工程师, I want 重建某实例的历史状态链, so that 调试复杂流程问题。

#### Acceptance Criteria

1. WHEN 查询 `/api/workflow/{instance_id}/events`, THE Workflow_Monitor SHALL 返回该实例所有 `workflow_state_events` 按时间升序排列。
2. THE Workflow_Monitor SHALL 允许按 `event_type` 过滤事件列表。

### REQ-043: 健康检查

**User Story:** As a 运维工程师, I want 引擎提供健康检查接口, so that 接入监控系统。

#### Acceptance Criteria

1. THE Workflow_Engine SHALL 提供 `/api/workflow/health` HTTP 接口，在所有依赖（MySQL）可达时返回 200。
2. IF MySQL 连接失败, THEN THE Workflow_Engine SHALL 返回 503 并在响应 body 中注明不可用的组件。

---

## 九、API 接口（P0）

### REQ-044: 启动工作流 HTTP 接口

**User Story:** As a 采购委外系统开发者, I want 通过 HTTP POST 启动工作流实例, so that 前端或第三方系统可触发执行。

#### Acceptance Criteria

1. WHEN 客户端 POST `/api/workflow/start` 携带 `{workflow_key, inputs, user_id}`, THE Workflow_Engine SHALL 调用 `start()` 创建实例并返回 `{instance_id, status}` JSON 响应。
2. IF 请求体不满足 schema, THEN THE API SHALL 返回 HTTP 400 并包含字段校验错误。
3. IF `workflow_key` 不存在, THEN THE API SHALL 返回 HTTP 404。

### REQ-045: 审批动作 HTTP 接口

**User Story:** As a 审批人, I want 通过 HTTP POST 执行审批动作, so that 前端能触发审批流转。

#### Acceptance Criteria

1. WHEN 客户端 POST `/api/workflow/{instance_id}/approve` 携带 `{node_id, actor_id, action, comment, delegate_to}`, THE Workflow_Engine SHALL 调用 `ApprovalManager.take_action()` 并返回 `{record_id}` 响应。
2. IF `action ∉ node.allowed_actions` 或 `actor_id` 无权限, THEN THE API SHALL 返回 HTTP 403。
3. IF 实例状态非 WAITING_APPROVAL 或节点非 WAITING_APPROVAL, THEN THE API SHALL 返回 HTTP 409 并附 `IllegalTransitionError` 描述。

### REQ-046: 状态查询 HTTP 接口

**User Story:** As a 运维工程师, I want 通过 HTTP GET 查询实例状态, so that 前端能展示进度。

#### Acceptance Criteria

1. WHEN 客户端 GET `/api/workflow/{instance_id}`, THE Workflow_Engine SHALL 返回 `get_status()` 的完整视图（JSON）。
2. IF `instance_id` 不存在, THEN THE API SHALL 返回 HTTP 404。

### REQ-047: 待办列表接口

**User Story:** As a 审批人, I want 通过 HTTP GET 查询我的待办, so that 处理审批任务。

#### Acceptance Criteria

1. WHEN 客户端 GET `/api/workflow/tasks?assignee_type=USER&assignee_id=...`, THE Approval_Manager SHALL 返回该处理人的 pending 任务列表。
2. THE API SHALL 支持分页参数 `page` 和 `page_size`，默认返回前 50 条。

### REQ-048: 管理接口

**User Story:** As a 运维工程师, I want 通过 HTTP 接口挂起/恢复/取消实例, so that 介入运行中流程。

#### Acceptance Criteria

1. WHEN 客户端 POST `/api/workflow/{instance_id}/suspend`, THE Workflow_Engine SHALL 调用 `suspend()` 并返回 200。
2. WHEN 客户端 POST `/api/workflow/{instance_id}/resume`, THE Workflow_Engine SHALL 调用 `resume()` 并返回 200。
3. WHEN 客户端 POST `/api/workflow/{instance_id}/cancel`, THE Workflow_Engine SHALL 调用 `cancel()` 并返回 200。

---

## 十、错误处理（P0）

### REQ-049: 节点失败策略

**User Story:** As a 业务分析师, I want 为节点声明失败策略, so that 对不同类型的失败采用不同响应。

#### Acceptance Criteria

1. THE Task_Node SHALL 支持 `ErrorStrategy` 枚举值 `FAIL_WORKFLOW`、`SKIP`、`RETRY`、`GO_TO`。
2. WHERE `on_error = FAIL_WORKFLOW`, THE DAG_Executor SHALL 在节点失败时取消其他运行任务并将实例置为 FAILED。
3. WHERE `on_error = SKIP`, THE DAG_Executor SHALL 将该节点标记为 SKIPPED 并继续调度后继节点。
4. WHERE `on_error = RETRY`, THE DAG_Executor SHALL 按 `retry_policy` 重试该节点。
5. WHERE `on_error = GO_TO`, THE DAG_Executor SHALL 跳转到 `retry_policy.go_to_node`（或等价配置）指定的节点继续执行。

### REQ-050: 重试策略

**User Story:** As a 业务分析师, I want 为节点声明重试策略, so that 瞬时故障能自动恢复。

#### Acceptance Criteria

1. WHEN 节点失败且 `retry_policy` 非空, THE Task_Node SHALL 按 `max_attempts`、`backoff_seconds`、`backoff_multiplier` 执行指数退避重试。
2. IF `retry_policy.retry_on` 非空且异常类型名不在列表中, THEN THE Task_Node SHALL 不重试，直接按 `on_error` 处理。
3. THE Task_Node SHALL 保证重试次数不超过 `max_attempts`（上限 10）。
4. WHEN 每次重试, THE Persistence_Manager SHALL 新增一条 `workflow_node_executions` 记录（`attempt` 递增）。

### REQ-051: 节点超时

**User Story:** As a 测试工程师, I want 节点执行超过 `timeout_seconds` 时被强制终止, so that 避免卡死。

#### Acceptance Criteria

1. WHEN 节点执行时间超过 `timeout_seconds`, THE Task_Node SHALL 抛出 `asyncio.TimeoutError`。
2. IF 节点配置了 `retry_policy`, THEN 超时 SHALL 被视为可重试错误。
3. THE Task_Node SHALL 默认 `timeout_seconds = 300`（5 分钟）若未显式配置。

### REQ-052: 数据库错误降级

**User Story:** As a 运维工程师, I want DB 错误自动降级, so that 瞬时 DB 故障不引起整个流程失败。

#### Acceptance Criteria

1. WHEN `Persistence_Manager.flush()` 抛出 `pymysql.Error`, THE DAG_Executor SHALL 以指数退避（1s / 3s / 5s）重试最多 3 次。
2. IF 3 次重试全失败, THEN THE DAG_Executor SHALL 将实例置为 SUSPENDED 并发告警（WARNING 级别）。
3. WHEN DB 可用后, 调用方 SHALL 可通过 `resume(instance_id)` 手动恢复。

### REQ-053: 异常分类

**User Story:** As a 测试工程师, I want 引擎异常分类清晰, so that 错误处理有明确契约。

#### Acceptance Criteria

1. THE Workflow_Engine SHALL 定义以下异常类层次：
   - DAG 定义错误：`CyclicGraphError`、`InvalidNodeRefError`、`SchemaValidationError`、`DuplicateDefinitionError`
   - 节点执行错误：`NodeExecutionError`、`ToolNotFoundError`、`AgentNotFoundError`、`SkillLoadError`、`NoMatchingBranchError`
   - 状态转换错误：`IllegalTransitionError`
   - 审批错误：`PermissionError`、`IllegalActionError`
   - 持久化错误：`DatabaseError`、`InstanceLockedError`、`InstanceNotFoundError`、`DefinitionNotFoundError`
   - 模板错误：`TemplateRenderError`
2. THE Workflow_Engine SHALL 保证所有自定义异常继承自基类 `WorkflowError`。

---

## 十一、安全（P0）

### REQ-054: 模板沙箱

**User Story:** As a 采购委外系统开发者, I want Jinja2 模板运行在沙箱中, so that 恶意模板不能执行任意代码。

#### Acceptance Criteria

1. THE expressions 模块 SHALL 使用 Jinja2 `SandboxedEnvironment`。
2. THE expressions 模块 SHALL 禁用对 `os`、`sys`、`subprocess`、`__import__`、`open`、`eval`、`exec` 的访问。
3. WHEN 模板尝试访问被禁用的对象或属性, THE expressions 模块 SHALL 抛出 `SecurityError`（或包装为 `TemplateRenderError`）。
4. FOR ALL 模板字符串, 不可能引起文件、网络或系统命令的副作用。

### REQ-055: 输入校验

**User Story:** As a 安全审计员, I want 所有外部输入经过校验, so that 防止注入攻击。

#### Acceptance Criteria

1. WHEN 启动工作流, THE Workflow_Engine SHALL 通过 `jsonschema` 校验 `inputs` 符合 `input_schema`。
2. WHEN 审批动作传入 `comment`、`delegate_to`、`actor_id`, THE Approval_Manager SHALL 在 Pydantic 层做长度（`comment ≤ 4096`、`actor_id ≤ 128`）与字符集校验。

### REQ-056: 审批鉴权

**User Story:** As a 安全审计员, I want 审批操作必须经过鉴权, so that 非授权人无法越权操作。

#### Acceptance Criteria

1. WHEN 调用 `ApprovalManager.take_action()`, THE Approval_Manager SHALL 校验 `actor_id` 属于 `resolve_assignees(node.assignees, delegate_chain)` 的实际用户集合。
2. IF `actor_id` 不在授权集合, THEN THE Approval_Manager SHALL 抛出 `PermissionError`（对应 HTTP 403）。
3. THE FastAPI 路由 SHALL 在调用引擎前先完成身份认证（JWT 或 session），`actor_id` 必须来自已鉴权的身份而非请求体自报。

### REQ-057: SQL 注入防护

**User Story:** As a 安全审计员, I want 所有 DB 操作参数化, so that 杜绝 SQL 注入。

#### Acceptance Criteria

1. THE Persistence_Manager SHALL 使用 `pymysql` 的参数化查询（`%s` 占位符）执行所有 SQL。
2. THE Persistence_Manager SHALL 禁止使用字符串拼接构造 SQL 语句。

### REQ-058: 审计日志

**User Story:** As a 合规审计员, I want 所有关键事件落审计链, so that 支持合规审计。

#### Acceptance Criteria

1. THE Workflow_Engine SHALL 把以下事件写入 `workflow_state_events`：workflow_started / workflow_completed / workflow_failed / workflow_cancelled / workflow_suspended / workflow_resumed / node_started / node_completed / node_failed / node_skipped / approval_requested / approval_action。
2. THE Persistence_Manager SHALL 禁止对 `workflow_state_events` 和 `workflow_approval_records` 执行 DELETE 和 UPDATE。
3. FOR ALL 审计记录, 字段 SHALL 包含 `occurred_at` 毫秒精度时间戳。

---

## 十二、业务场景验证（P0）

### REQ-059: 异常分析工作流端到端验证

**User Story:** As a 采购委外系统开发者, I want 用异常分析工作流作为核心验证场景, so that 证明引擎覆盖真实业务需求。

#### Acceptance Criteria

1. THE Workflow_Engine SHALL 能够加载并执行 design.md §YAML/JSON 工作流示例 中定义的 `exception_analysis_v1` 工作流。
2. WHEN 执行该工作流, THE Workflow_Engine SHALL 成功调度以下节点序列：`validate_input` → `parallel_analyze`（含 `exception_analyze` + `rag_search`） → `responsibility` → `confidence_check`（Decision） → {`solution_recommend` | `human_review`} → `approval_1`（Approval） → {`execute_solution` → `update_db` | `mark_cancelled`}。
3. WHEN 审批通过后, THE Workflow_Engine SHALL 继续执行 `execute_solution` 和 `update_db` 节点，最终实例状态 = COMPLETED。
4. WHEN 审批拒绝后, THE Workflow_Engine SHALL 执行 `mark_cancelled` 节点，最终实例状态 = COMPLETED（业务上是"取消"，但工作流自身完成）。
5. THE Workflow_Engine SHALL 在 `exception_analyze` 节点通过 `AgentLoop` 调用现有 `ExceptionAgent`，不修改 `ExceptionAgent` 代码。
6. THE Workflow_Engine SHALL 在 `rag_search` 节点通过 `call_kind='skill'` 调用现有 `RAGSkill`。

---

## 十三、正确性属性需求（P0）

### REQ-060: P1 DAG 无环性属性

**User Story:** As a 测试工程师, I want 验证 Workflow_Loader 的无环性判定是正确的, so that 有环的定义永远被拒绝。

#### Acceptance Criteria

1. FOR ALL `WorkflowDefinition` 对象, IF `WorkflowLoader.load()` 成功返回, THEN 其 `nodes + edges` 组成的图 SHALL 不存在任何环（含自环）。
2. FOR ALL 含环的 `WorkflowDefinition`, `WorkflowLoader.load()` SHALL 抛出 `CyclicGraphError`。
3. THE Workflow_Loader SHALL 通过 Hypothesis 属性测试与独立 DFS 环检测器对拍验证（round-trip 式对比）。

### REQ-061: P2 状态转换合法性属性

**User Story:** As a 测试工程师, I want 验证状态机永远只按合法路径转换, so that 保证状态不变式。

#### Acceptance Criteria

1. FOR ALL 状态序列 `[s₀, s₁, ..., sₙ]` 由 State_Machine 产生, `∀ i: sᵢ₊₁ ∈ TRANSITIONS[sᵢ]` SHALL 成立。
2. FOR ALL 终态 `s* ∈ {COMPLETED, FAILED, CANCELLED}`, 一旦序列进入 `s*`，后续任何事件 SHALL 抛出 `IllegalTransitionError`。
3. THE State_Machine SHALL 通过 Hypothesis 属性测试覆盖随机事件序列。

### REQ-062: P3 节点执行幂等性属性

**User Story:** As a 测试工程师, I want 验证相同 execution_id 只产生一条记录, so that 副作用不重复。

#### Acceptance Criteria

1. FOR ALL `execution_id`, `SELECT COUNT(*) FROM workflow_node_executions WHERE execution_id = ?` SHALL ≤ 1。
2. FOR ALL 节点 `n` 在"执行 → 崩溃 → 恢复 → 再执行"流程中, `context.outputs[n.id]` SHALL 语义等价于单次执行结果。
3. THE Persistence_Manager SHALL 通过 Hypothesis 属性测试模拟随机崩溃时机验证该属性。

### REQ-063: P4 持久化-内存一致性属性

**User Story:** As a 测试工程师, I want 验证节点完成时 DB 与内存一致, so that 下游读到的是已提交数据。

#### Acceptance Criteria

1. FOR ALL 节点 `n` 状态为 COMPLETED, 下游节点启动时 `persistence.load_context(i.id)` SHALL 包含 `n.id ∈ node_statuses` 且 `outputs[n.id]` 已写入。
2. WHEN 节点 flush 完成, 下游节点读取 SHALL 看到该节点的输出（读后写一致性）。
3. THE Persistence_Manager SHALL 通过 Hypothesis 属性测试验证并发 N 个节点随机崩溃后 DB `outputs` 键集 == `node_statuses = COMPLETED` 的节点集。

### REQ-064: P5 断点恢复幂等性属性

**User Story:** As a 测试工程师, I want 验证 resume 任意次终态一致, so that 恢复机制可信。

#### Acceptance Criteria

1. FOR ALL 实例 `i` 处于 {WAITING_APPROVAL, SUSPENDED, RUNNING（崩溃）} 状态, 执行 `resume(i.id)` k 次（k ∈ [1..5]）SHALL 产生相同的终态。
2. FOR ALL 节点, 多次 resume 产生的 output SHALL 等价。
3. FOR ALL 外部 API 调用次数, SHALL 由 `execution_id` 约束不产生副作用重复。

### REQ-065: P6 审批流转完整性属性

**User Story:** As a 测试工程师, I want 验证审批记录只追加且节点必达终态, so that 审计链可信。

#### Acceptance Criteria

1. FOR ALL `ApprovalRecord` r, r SHALL 不可被修改或删除（只追加）。
2. FOR ALL 审批节点 `n` 在其生命周期内, 存在终结动作或超时 SHALL 使 `n.status` 最终变为 COMPLETED 或 SKIPPED。
3. FOR ALL `actor a` 执行的动作 `act`, `a ∈ resolve_assignees(n.assignees, delegate_chain)` SHALL 成立；否则抛出 `PermissionError`。

### REQ-066: P7 并行节点 Join 正确性属性

**User Story:** As a 测试工程师, I want 验证 ParallelNode 按 join_strategy 正确判定状态, so that 并行逻辑可信。

#### Acceptance Criteria

1. FOR ALL `parallel_node p` with `branches=[b₁..bₖ]`, `join_strategy='all'`: `p.status = COMPLETED ⟺ ∀ i: bᵢ.status = COMPLETED`。
2. FOR ALL `p` with `join_strategy='any'`: `p.status = COMPLETED ⟺ ∃ i: bᵢ.status = COMPLETED`。
3. FOR ALL `p` with `join_strategy='majority'`: `p.status = COMPLETED ⟺ #{i: bᵢ.status = COMPLETED} > k/2`。
4. FOR ALL `p` with `fail_fast=true`, IF 存在 `bᵢ.status = FAILED`, THEN 其他运行中的 `bⱼ` SHALL 收到 `CancelledError`。

### REQ-067: P8 决策节点确定性属性

**User Story:** As a 测试工程师, I want 验证 DecisionNode 引用透明, so that 分支选择可预测。

#### Acceptance Criteria

1. FOR ALL `decision_node d` with `branches=[(c₁,n₁)..(cₖ,nₖ)]` 和固定 `context`, `evaluate_decision(d, context)` SHALL 返回 `nⱼ`，其中 `j = min {i : render_bool(cᵢ, context) = true}`（若无匹配则返回 `default_next` 或抛 `NoMatchingBranchError`）。
2. FOR ALL 固定 `context`, 多次求值 `DecisionNode` SHALL 返回相同结果。

### REQ-068: P9 参数模板求值安全性属性

**User Story:** As a 测试工程师, I want 验证沙箱阻止危险模板, so that 系统不被恶意输入破坏。

#### Acceptance Criteria

1. FOR ALL 模板字符串包含 `os.system`、`__import__`、`open`、`eval`、`exec`、`__class__`、`__mro__`, `render_params()` SHALL 抛出 `TemplateRenderError` 或 `SecurityError`。
2. FOR ALL 引用不存在 context key 的模板, `render_params()` SHALL 抛出 `TemplateRenderError`（不静默返回 None）。
3. FOR ALL 模板执行, SHALL 不触发文件、网络或系统命令副作用。

### REQ-069: P10 资源上限属性

**User Story:** As a 测试工程师, I want 验证并发和循环有硬上限, so that 资源不被耗尽。

#### Acceptance Criteria

1. FOR ALL 实例 `i` 的任意时刻 `t`, 同时运行的节点数 SHALL ≤ `definition.max_concurrent_nodes`。
2. FOR ALL `LoopNode l`, 迭代次数 SHALL ≤ `l.max_iterations`（达到上限后节点 FAILED）。
3. THE DAG_Executor SHALL 通过 Hypothesis 属性测试生成含大量并行分支的 DAG 验证并发上限。

### REQ-070: P11 租约互斥属性

**User Story:** As a 测试工程师, I want 验证租约保证单进程执行, so that 多实例部署无竞争。

#### Acceptance Criteria

1. FOR ALL 实例 `i` 的任意时刻 `t`, 持有合法（未过期）租约的进程数 SHALL ≤ 1。
2. FOR ALL 并发 `resume(instance_id)` 调用, 至多一个 SHALL 成功，其余 SHALL 抛出 `InstanceLockedError`。
3. THE Persistence_Manager SHALL 通过 Hypothesis 属性测试模拟多进程并发恢复验证该属性。

---

## 十四、非功能性需求（P1）

### REQ-071: 性能要求

**User Story:** As a 运维工程师, I want 引擎满足性能基线, so that 不成为业务瓶颈。

#### Acceptance Criteria

1. WHEN 并发启动 100 个简单工作流实例（10 节点内）, THE Workflow_Engine SHALL 在单进程、4 核、8GB 内存环境下于 10 秒内全部进入 RUNNING 状态。
2. WHEN 单实例有 50 个可并行节点, THE DAG_Executor SHALL 按 `max_concurrent_nodes` 限流且平均节点调度延迟 ≤ 100ms。
3. WHEN `context_json` ≤ 1MB, 节点粒度 flush 平均耗时 SHALL ≤ 50ms。
4. THE Approval_Manager SHALL 对"我的待办"查询在 10 万量级 pending 任务下响应时间 ≤ 200ms（依赖 `workflow_approval_tasks` 组合索引）。

### REQ-072: 可扩展性

**User Story:** As a 采购委外系统开发者, I want 轻松扩展新的节点类型, so that 支持未来业务需求。

#### Acceptance Criteria

1. THE Workflow_Engine SHALL 提供 `BaseNode` 抽象基类，业务可通过继承实现新节点类型并注册到 `NodeType` 枚举。
2. THE Workflow_Engine SHALL 对新节点类型不要求修改 `DAG_Executor` 核心调度逻辑（仅需要节点自身实现 `run()` 和 `validate()`）。

### REQ-073: 可观测性

**User Story:** As a 运维工程师, I want 完整的日志、指标、事件链, so that 快速定位问题。

#### Acceptance Criteria

1. THE Workflow_Engine SHALL 记录结构化日志，每条日志包含 `instance_id`、`node_id`（如适用）、`event_type`、`correlation_id`。
2. THE Workflow_Engine SHALL 把所有状态变更写入 `workflow_state_events`，支持按 `instance_id` 回放整个生命周期。
3. THE Workflow_Monitor SHALL 提供实时指标接口，覆盖启动率、完成率、失败率、审批等待时长分布。

### REQ-074: 依赖约束

**User Story:** As a 运维工程师, I want 不引入重型调度器, so that 部署简单、维护成本低。

#### Acceptance Criteria

1. THE Workflow_Engine SHALL 不依赖 Temporal、Airflow、Celery、Prefect、Dagster 中的任何一个。
2. THE Workflow_Engine SHALL 仅依赖 Python ≥ 3.10、pydantic ≥ 2.0、pymysql ≥ 1.0、jinja2 ≥ 3.0、pyyaml ≥ 6.0、jsonschema ≥ 4.0、hypothesis ≥ 6.0、fastapi ≥ 0.100。
3. THE Workflow_Engine SHALL 完全基于 `asyncio` 运行，同一进程内调度；多实例互斥通过 MySQL 行级锁 + 租约实现。

### REQ-075: 兼容性

**User Story:** As a 采购委外系统开发者, I want 引擎集成后不破坏现有功能, so that 升级零风险。

#### Acceptance Criteria

1. WHEN 引擎被集成到 `backend/` 项目, THE Workflow_Engine SHALL 不修改现有 `harness/core`、`harness/memory`、`harness/security`、`harness/observability`、`harness/tools`、`harness/orchestration` 模块的公共接口。
2. THE Workflow_Engine SHALL 使现有的 `ExceptionAgent`、`QuotationAgent`、`exception_analysis.py`、`rag_skill.py` 等业务代码无需任何修改即可被工作流调用。
3. THE Workflow_Engine SHALL 使现有的单 Agent ReAct 调用路径（`api/routes` 中的端点）保持完全不变。
