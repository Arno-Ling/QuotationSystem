# Design Document: ExceptionAgent Development

## Overview

The ExceptionAgent is an AI-driven intelligent agent designed to analyze quality exceptions in a mold outsourcing procurement system. It follows the same architectural pattern as the QuotationAgent, integrating with the Harness framework and using specialized Skills for different analysis tasks.

### Purpose

The ExceptionAgent provides intelligent analysis of quality exceptions including:
- Root cause determination
- Responsibility assignment (internal, supplier, or material vendor)
- Solution recommendations with cost and time estimates
- Historical case matching using RAG (Retrieval-Augmented Generation)

### Design Principles

1. **Consistency**: Follow the same architectural pattern as QuotationAgent
2. **Modularity**: Each capability implemented as an independent Skill
3. **Extensibility**: Easy to add new Skills or modify existing ones
4. **Observability**: Comprehensive logging and callback support
5. **Reliability**: Graceful error handling and fallback mechanisms

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Endpoint                          │
│              POST /api/exception/analyze                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    ExceptionAgent                            │
│  - Orchestrates exception analysis workflow                 │
│  - Manages Skills execution sequence                         │
│  - Synthesizes final analysis report                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Harness Framework                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  AgentLoop   │  │ ToolRegistry │  │    Memory    │     │
│  │  (ReAct)     │  │  (Skills)    │  │  (ChromaDB)  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Skills Layer                              │
│  ┌──────────────────────┐  ┌──────────────────────────┐    │
│  │ ExceptionAnalysis    │  │ Responsibility           │    │
│  │ Skill                │  │ DeterminationSkill       │    │
│  └──────────────────────┘  └──────────────────────────┘    │
│  ┌──────────────────────┐  ┌──────────────────────────┐    │
│  │ SolutionRecommend    │  │ RAGSkill                 │    │
│  │ ationSkill           │  │ (Historical Cases)       │    │
│  └──────────────────────┘  └──────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  MySQL DB    │  │  ChromaDB    │  │  Redis Cache │     │
│  │ (Exceptions) │  │ (RAG Vector) │  │  (Optional)  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### Component Interaction Flow

```mermaid
sequenceDiagram
    participant API as FastAPI Endpoint
    participant Agent as ExceptionAgent
    participant Loop as AgentLoop
    participant Skills as Skills (Tools)
    participant Memory as LongTermMemory
    participant DB as MySQL Database

    API->>Agent: analyze_exception(exception_data)
    Agent->>Loop: run(task_description)
    
    Loop->>Skills: ExceptionAnalysisSkill.execute()
    Skills-->>Loop: analysis_result
    
    Loop->>Memory: search(exception_type)
    Memory-->>Loop: historical_cases
    
    Loop->>Skills: ResponsibilityDeterminationSkill.execute()
    Skills-->>Loop: responsibility_result
    
    Loop->>Skills: SolutionRecommendationSkill.execute()
    Skills-->>Loop: solution_result
    
    Loop-->>Agent: final_answer
    Agent->>DB: update exception record
    Agent-->>API: analysis_report
```

## Components and Interfaces

### 1. ExceptionAgent Class

**Location**: `backend/ai_modules/agents/exception_agent.py`

**Responsibilities**:
- Initialize agent configuration and dependencies
- Orchestrate exception analysis workflow
- Manage Skills execution sequence
- Synthesize final analysis report
- Handle errors and edge cases

**Key Methods**:

```python
class ExceptionAgent:
    def __init__(
        self,
        model_name: str = "gpt-4",
        enable_callbacks: bool = True,
        enable_long_term_memory: bool = True
    ):
        """Initialize ExceptionAgent with configuration"""
        
    async def analyze_exception(
        self,
        exception_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze quality exception
        
        Args:
            exception_data: {
                "exception_id": str,
                "exception_type": str,  # 尺寸偏差, 表面缺陷, 材料问题, 组装问题
                "description": str,
                "related_entity_id": str,  # part_id or order_id
                "entity_type": str,  # part or order
                "project_id": str,
                "supplier_id": str (optional),
                "material": str (optional),
                "process_type": str (optional),
                "severity": str (optional)  # critical, major, minor
            }
            
        Returns:
            {
                "success": bool,
                "exception_data": Dict,
                "analysis": {
                    "root_cause": str,
                    "severity": str,
                    "impact_scope": str,
                    "contributing_factors": List[str]
                },
                "historical_cases": List[Dict],
                "responsibility": {
                    "responsible_party": str,  # internal, supplier, material_vendor
                    "confidence_score": float,  # 0-100
                    "evidence": List[str],
                    "requires_review": bool
                },
                "solutions": List[{
                    "solution_type": str,  # rework, replacement, temporary_acceptance, design_modification
                    "description": str,
                    "cost_impact": float,
                    "time_impact": int,  # days
                    "feasibility_score": float,  # 0-100
                    "implementation_steps": List[str]
                }],
                "analysis_report": str,  # Full text report
                "timestamp": str,
                "agent_steps": int
            }
        """
        
    def _build_analysis_task(
        self,
        exception_data: Dict[str, Any]
    ) -> str:
        """Build task description for AgentLoop"""
        
    def _parse_analysis_result(
        self,
        result: str,
        exception_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse and structure the analysis result"""
        
    def get_state(self) -> Dict[str, Any]:
        """Get current agent state"""
```

**Configuration**:

```python
config = AgentConfig(
    model_name="gpt-4",
    temperature=0.2,  # Low temperature for consistent analysis
    max_steps=15,
    max_tokens=3000,
    enable_long_term_memory=True,
    system_prompt=self._create_system_prompt()
)
```

**System Prompt**:

The system prompt defines the agent's role, workflow, and output format:

```
你是一个专业的质量异常分析助手，擅长分析异常原因、判定责任方、推荐解决方案。

你的职责：
1. 分析异常的根本原因、严重程度和影响范围
2. 从知识库检索相似的历史案例
3. 判定责任方（内部、供应商、材料商）并提供证据
4. 推荐解决方案并评估成本和时间影响

可用工具：
- analyze_exception: 分析异常原因和影响
- search_exception_cases: 检索历史案例
- determine_responsibility: 判定责任方
- recommend_solution: 推荐解决方案

工作流程：
1. 使用 analyze_exception 分析异常
2. 使用 search_exception_cases 检索历史案例
3. 使用 determine_responsibility 判定责任
4. 使用 recommend_solution 推荐方案
5. 综合所有信息，生成完整分析报告

输出格式：
Final Answer:
【异常分析报告】
一、基本信息
二、异常分析
三、历史案例
四、责任判定
五、解决方案
六、综合建议
```

### 2. ExceptionAnalysisSkill

**Location**: `backend/ai_modules/skills/exception/exception_analysis.py`

**Purpose**: Analyze exception root cause, severity, and impact

**Tool Signature**:

```python
@tool(
    description="分析质量异常的根本原因、严重程度和影响范围",
    permission="read_only"
)
def analyze_exception(
    exception_type: str,
    description: str,
    entity_type: str,
    material: str = None,
    process_type: str = None
) -> Dict[str, Any]:
    """
    Analyze quality exception
    
    Returns:
        {
            "root_cause": str,  # 根本原因
            "severity": str,  # critical, major, minor
            "impact_scope": str,  # single_part, batch, entire_order
            "contributing_factors": List[str],
            "analysis_summary": str
        }
    """
```

**Analysis Logic**:

1. **Root Cause Analysis**:
   - Parse exception description
   - Map exception type to common causes
   - Consider material and process factors
   - Identify primary root cause

2. **Severity Assessment**:
   - Critical: Safety risk, complete failure, cannot be used
   - Major: Significant defect, requires rework, affects function
   - Minor: Cosmetic issue, does not affect function

3. **Impact Scope Evaluation**:
   - Single part: Isolated defect
   - Batch: Multiple parts affected
   - Entire order: Systematic issue

4. **Contributing Factors**:
   - Material quality
   - Process control
   - Design specifications
   - Environmental conditions
   - Human factors

### 3. ResponsibilityDeterminationSkill

**Location**: `backend/ai_modules/skills/exception/responsibility_determination.py`

**Purpose**: Determine which party is responsible for the exception

**Tool Signature**:

```python
@tool(
    description="判定质量异常的责任方（内部、供应商、材料商）",
    permission="read_only"
)
def determine_responsibility(
    exception_type: str,
    root_cause: str,
    supplier_id: str,
    material: str = None,
    historical_cases: List[Dict] = None
) -> Dict[str, Any]:
    """
    Determine responsibility for exception
    
    Returns:
        {
            "responsible_party": str,  # internal, supplier, material_vendor
            "confidence_score": float,  # 0-100
            "evidence": List[str],
            "requires_review": bool,  # True if confidence < 70
            "reasoning": str
        }
    """
```

**Determination Logic**:

1. **Exception Type Mapping**:
   - 尺寸偏差 (Dimensional deviation) → Usually supplier (processing)
   - 表面缺陷 (Surface defect) → Supplier or material vendor
   - 材料问题 (Material issue) → Material vendor
   - 组装问题 (Assembly issue) → Internal or supplier

2. **Evidence Collection**:
   - Exception description keywords
   - Root cause analysis
   - Supplier history
   - Material specifications
   - Historical case patterns

3. **Confidence Scoring**:
   - High confidence (80-100): Clear evidence, consistent with history
   - Medium confidence (60-79): Some evidence, needs verification
   - Low confidence (<60): Insufficient evidence, requires human review

4. **Review Flagging**:
   - Flag for human review if confidence < 70
   - Flag if conflicting evidence
   - Flag if high-value order

### 4. SolutionRecommendationSkill

**Location**: `backend/ai_modules/skills/exception/solution_recommendation.py`

**Purpose**: Recommend solutions with cost and time estimates

**Tool Signature**:

```python
@tool(
    description="推荐异常解决方案并评估成本和时间影响",
    permission="read_only"
)
def recommend_solution(
    exception_type: str,
    severity: str,
    root_cause: str,
    responsible_party: str,
    quantity_affected: int = 1
) -> Dict[str, Any]:
    """
    Recommend solutions for exception
    
    Returns:
        {
            "solutions": List[{
                "solution_type": str,  # rework, replacement, temporary_acceptance, design_modification
                "description": str,
                "cost_impact": float,
                "time_impact": int,  # days
                "feasibility_score": float,  # 0-100
                "implementation_steps": List[str],
                "pros": List[str],
                "cons": List[str]
            }],
            "recommended_solution": str,  # Best solution
            "recommendation_summary": str
        }
    """
```

**Solution Types**:

1. **Rework (返工)**:
   - When: Defect can be corrected
   - Cost: Medium (labor + materials)
   - Time: 3-7 days
   - Feasibility: High for minor/major defects

2. **Replacement (更换)**:
   - When: Defect cannot be corrected
   - Cost: High (new parts + disposal)
   - Time: 7-14 days (re-manufacturing)
   - Feasibility: High for critical defects

3. **Temporary Acceptance (临时让步接收)**:
   - When: Defect is minor and doesn't affect function
   - Cost: Low (documentation only)
   - Time: 1-2 days
   - Feasibility: Only for minor defects with customer approval

4. **Design Modification (修改设计)**:
   - When: Systematic issue, design flaw
   - Cost: Very high (redesign + re-tooling)
   - Time: 14-30 days
   - Feasibility: Low, last resort

**Recommendation Logic**:

1. **Severity-Based Selection**:
   - Critical → Replacement or rework
   - Major → Rework or replacement
   - Minor → Temporary acceptance or rework

2. **Cost-Benefit Analysis**:
   - Calculate total cost for each solution
   - Consider time impact on project schedule
   - Evaluate feasibility based on resources

3. **Ranking**:
   - Rank solutions by feasibility score
   - Consider cost, time, and quality trade-offs
   - Recommend best solution

### 5. RAGSkill for Exception Cases

**Location**: `backend/ai_modules/skills/exception/rag_skill.py`

**Purpose**: Retrieve similar historical exception cases from vector database

**Tool Signature**:

```python
@tool(
    description="从知识库检索相似的历史异常案例",
    permission="read_only"
)
def search_exception_cases(
    query: str,
    exception_type: str = None,
    top_k: int = 5
) -> Dict[str, Any]:
    """
    Search historical exception cases
    
    Returns:
        {
            "cases": List[{
                "case_id": str,
                "exception_type": str,
                "description": str,
                "responsible_party": str,
                "resolution": str,
                "outcome": str,
                "resolution_date": str,
                "similarity_score": float
            }],
            "summary": str,
            "total_found": int
        }
    """
```

**RAG Implementation**:

1. **Vector Database**: ChromaDB
   - Collection name: `exception_cases`
   - Persist directory: `./chroma_db/exception_agent`

2. **Embedding Strategy**:
   - Embed exception description + resolution details
   - Use semantic similarity search
   - Filter by exception type if specified

3. **Retrieval Process**:
   - Convert query to embedding
   - Search top K similar cases
   - Calculate similarity scores
   - Return cases with metadata

4. **Case Storage**:
   ```python
   {
       "content": "Exception description + resolution details",
       "metadata": {
           "exception_type": str,
           "responsible_party": str,
           "resolution_plan": str,
           "outcome": str,
           "resolution_date": str,
           "cost": float,
           "time_days": int
       }
   }
   ```

## Data Models

### Exception Data Input

```python
{
    "exception_id": "EXC001",
    "exception_type": "尺寸偏差",  # 尺寸偏差, 表面缺陷, 材料问题, 组装问题
    "description": "轴承座内径尺寸超差0.5mm，超出公差范围",
    "related_entity_id": "PART001",
    "entity_type": "part",
    "project_id": "PROJ001",
    "supplier_id": "SUP001",
    "material": "钢",
    "process_type": "数控加工",
    "severity": "major",  # Optional, will be determined by agent
    "quantity_affected": 50,
    "report_by": "USER001",
    "report_at": "2024-01-15 10:30:00"
}
```

### Analysis Report Output

```python
{
    "success": True,
    "exception_data": {...},  # Original input
    "analysis": {
        "root_cause": "加工设备精度不足或刀具磨损",
        "severity": "major",
        "impact_scope": "batch",
        "contributing_factors": [
            "设备精度",
            "刀具状态",
            "工艺参数"
        ]
    },
    "historical_cases": [
        {
            "case_id": "CASE123",
            "exception_type": "尺寸偏差",
            "description": "类似的内径超差问题",
            "responsible_party": "supplier",
            "resolution": "返工处理",
            "outcome": "成功解决",
            "similarity_score": 0.85
        }
    ],
    "responsibility": {
        "responsible_party": "supplier",
        "confidence_score": 85.0,
        "evidence": [
            "异常类型为尺寸偏差，通常由加工方负责",
            "历史案例显示该供应商有类似问题",
            "材料符合规格，排除材料问题"
        ],
        "requires_review": False,
        "reasoning": "基于异常类型和历史数据，判定为供应商加工问题"
    },
    "solutions": [
        {
            "solution_type": "rework",
            "description": "对超差零件进行返工加工，修正内径尺寸",
            "cost_impact": 2500.0,
            "time_impact": 5,
            "feasibility_score": 90.0,
            "implementation_steps": [
                "1. 将超差零件退回供应商",
                "2. 供应商重新加工修正尺寸",
                "3. 重新检验确认尺寸合格",
                "4. 合格后重新交付"
            ],
            "pros": ["成本相对较低", "可以修复"],
            "cons": ["需要额外时间", "可能影响交期"]
        },
        {
            "solution_type": "replacement",
            "description": "重新制造新零件替换超差零件",
            "cost_impact": 5000.0,
            "time_impact": 10,
            "feasibility_score": 75.0,
            "implementation_steps": [
                "1. 下达新的加工订单",
                "2. 供应商重新生产",
                "3. 检验新零件",
                "4. 交付新零件"
            ],
            "pros": ["质量有保证", "不影响原零件"],
            "cons": ["成本较高", "时间较长"]
        }
    ],
    "recommended_solution": "rework",
    "analysis_report": "【完整的文本分析报告】...",
    "timestamp": "2024-01-15 11:00:00",
    "agent_steps": 8
}
```

### Database Schema Updates

**exceptions table**:

```sql
ALTER TABLE exceptions ADD COLUMN ai_analysis_report JSON;
ALTER TABLE exceptions ADD COLUMN ai_confidence_score FLOAT;
ALTER TABLE exceptions ADD COLUMN ai_analysis_timestamp DATETIME;
```

The `ai_analysis_report` JSON structure:

```json
{
    "analysis": {...},
    "responsibility": {...},
    "solutions": [...],
    "historical_cases": [...]
}
```

## Error Handling

### Error Handling Strategy

1. **Skill Execution Failures**:
   - Log error with full stack trace
   - Continue with remaining Skills
   - Note failure in final report
   - Return partial results

2. **LLM API Failures**:
   - Retry up to 3 times with exponential backoff
   - Backoff: 1s, 2s, 4s
   - If all retries fail, return error response
   - Log all retry attempts

3. **Vector Database Unavailable**:
   - Proceed without historical case retrieval
   - Note limitation in report
   - Don't block analysis

4. **Invalid Input Data**:
   - Validate input schema
   - Return clear error messages
   - HTTP 400 Bad Request

5. **Timeout Handling**:
   - Set 120-second timeout for entire workflow
   - If timeout, return partial results
   - Log timeout event

### Error Response Format

```python
{
    "success": False,
    "error": "Error message",
    "error_type": "LLM_API_ERROR | SKILL_EXECUTION_ERROR | VALIDATION_ERROR | TIMEOUT_ERROR",
    "partial_results": {...},  # If available
    "timestamp": "2024-01-15 11:00:00"
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property Reflection

After analyzing all acceptance criteria, I identified the following testable properties. Some properties were combined to eliminate redundancy:

- Properties 1.1-1.5 all test the completeness and validity of exception analysis output → Combined into Property 1
- Properties 2.1-2.2 both test responsibility classification → Combined into Property 2
- Properties 3.1-3.6 all test solution recommendation completeness → Combined into Property 5
- Properties 4.2-4.4 all test historical case retrieval validity → Combined into Property 7

### Property 1: Exception Analysis Completeness

*For any* valid exception input (with exception_type, description, and context), the ExceptionAgent SHALL produce a complete analysis containing:
- A non-empty root_cause
- A severity level in {critical, major, minor}
- An impact_scope in {single_part, batch, entire_order}
- A non-empty list of contributing_factors

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**

### Property 2: Responsibility Classification Validity

*For any* exception analysis, the determined responsible_party SHALL be one of {internal, supplier, material_vendor}, and SHALL include:
- A non-empty evidence list
- A confidence_score in the range [0, 100]

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

### Property 3: Low Confidence Review Flagging

*For any* exception analysis where confidence_score < 70, the requires_review flag SHALL be set to True.

**Validates: Requirement 2.5**

### Property 4: Solution Recommendation Non-Empty

*For any* analyzed exception, the ExceptionAgent SHALL recommend at least one solution (solutions list is non-empty).

**Validates: Requirement 3.1**

### Property 5: Solution Completeness and Validity

*For any* recommended solution, it SHALL have:
- A solution_type in {rework, replacement, temporary_acceptance, design_modification}
- A cost_impact >= 0
- A time_impact > 0
- A feasibility_score in [0, 100]
- A non-empty implementation_steps list

**Validates: Requirements 3.2, 3.3, 3.4, 3.6**

### Property 6: Solution Ranking by Feasibility

*For any* exception with multiple solutions, the solutions SHALL be ordered by feasibility_score in descending order (highest feasibility first).

**Validates: Requirement 3.5**

### Property 7: Historical Case Retrieval Validity

*For any* exception analysis that retrieves historical cases:
- At most 5 cases SHALL be returned
- Each case SHALL have required metadata (exception_type, responsible_party, resolution, outcome)
- Each case SHALL have a similarity_score in [0, 1]

**Validates: Requirements 4.2, 4.3, 4.4**

### Property 8: Low Similarity Case Handling

*For any* exception analysis where all retrieved historical cases have similarity_score < 0.6, the system SHALL indicate "no relevant historical cases found" in the summary.

**Validates: Requirement 4.5**

### Property-Based Testing Implementation

Each property will be implemented as a property-based test using a Python PBT library (e.g., Hypothesis). Each test will:

1. **Run minimum 100 iterations** to ensure comprehensive coverage
2. **Generate random exception data** with varying:
   - Exception types (尺寸偏差, 表面缺陷, 材料问题, 组装问题)
   - Descriptions (various lengths and content)
   - Materials (钢, 铝, 铜, 塑料, etc.)
   - Process types (数控加工, 精密加工, etc.)
   - Quantities (1-10000)
3. **Tag each test** with the property it validates:
   ```python
   # Feature: exception-agent-development, Property 1: Exception Analysis Completeness
   ```

### Example Property Test Structure

```python
from hypothesis import given, strategies as st
import pytest

@given(
    exception_type=st.sampled_from(['尺寸偏差', '表面缺陷', '材料问题', '组装问题']),
    description=st.text(min_size=10, max_size=500),
    material=st.sampled_from(['钢', '铝', '铜', '塑料', '不锈钢']),
    process_type=st.sampled_from(['数控加工', '精密加工', '普通加工']),
    quantity=st.integers(min_value=1, max_value=10000)
)
def test_property_1_exception_analysis_completeness(
    exception_type, description, material, process_type, quantity
):
    """
    Feature: exception-agent-development
    Property 1: Exception Analysis Completeness
    
    For any valid exception input, the analysis SHALL contain
    root_cause, severity, impact_scope, and contributing_factors.
    """
    # Arrange
    exception_data = {
        "exception_type": exception_type,
        "description": description,
        "material": material,
        "process_type": process_type,
        "quantity": quantity,
        # ... other required fields
    }
    
    # Act
    result = analyze_exception_skill.execute(**exception_data)
    
    # Assert
    assert result['root_cause'] is not None and len(result['root_cause']) > 0
    assert result['severity'] in ['critical', 'major', 'minor']
    assert result['impact_scope'] in ['single_part', 'batch', 'entire_order']
    assert isinstance(result['contributing_factors'], list)
    assert len(result['contributing_factors']) > 0
```

### Non-Property Testing

The following requirements are NOT suitable for property-based testing and will use alternative testing strategies:

1. **Integration Requirements** (Req 5-10, 12-13):
   - Use integration tests with real/mocked dependencies
   - Test Harness integration, API endpoints, database updates
   - Test error handling with specific failure scenarios

2. **Configuration Requirements** (Req 11, 15):
   - Use example-based unit tests
   - Test with specific configuration values
   - Manual review of system prompts

3. **Infrastructure Requirements** (Req 10):
   - Use integration tests with ChromaDB
   - Test vector storage and retrieval
   - Test with sample historical cases

## Testing Strategy

### Dual Testing Approach

The ExceptionAgent testing strategy combines **property-based testing** for universal correctness properties with **example-based unit tests** for specific scenarios and edge cases.

#### Property-Based Tests (Primary)

**Purpose**: Verify universal properties hold across all valid inputs

**Implementation**:
- Use Hypothesis library for Python
- Minimum 100 iterations per property test
- Generate random exception data with varying types, descriptions, materials, processes
- Test the 8 correctness properties defined above

**Property Tests**:
1. Property 1: Exception Analysis Completeness
2. Property 2: Responsibility Classification Validity
3. Property 3: Low Confidence Review Flagging
4. Property 4: Solution Recommendation Non-Empty
5. Property 5: Solution Completeness and Validity
6. Property 6: Solution Ranking by Feasibility
7. Property 7: Historical Case Retrieval Validity
8. Property 8: Low Similarity Case Handling

**Test Configuration**:
```python
# pytest.ini or conftest.py
hypothesis_settings = {
    "max_examples": 100,  # Minimum iterations
    "deadline": None,  # No time limit per test
    "print_blob": True  # Print failing examples
}
```

**Test Tagging**:
Each property test MUST include a comment tag:
```python
# Feature: exception-agent-development, Property N: [Property Name]
```

#### Example-Based Unit Tests (Complementary)

**Purpose**: Test specific scenarios, edge cases, and error conditions

**Unit Tests by Skill**:

1. **ExceptionAnalysisSkill Tests**:
   - Specific exception type examples (尺寸偏差, 表面缺陷, etc.)
   - Edge cases: empty description, unknown material
   - Boundary cases: very long descriptions, special characters

2. **ResponsibilityDeterminationSkill Tests**:
   - Specific responsibility scenarios (clear supplier fault, clear internal fault)
   - Edge cases: conflicting evidence, no historical data
   - Boundary cases: confidence score exactly 70

3. **SolutionRecommendationSkill Tests**:
   - Specific severity-solution mappings
   - Edge cases: zero quantity, unknown exception type
   - Boundary cases: very high cost, very long time

4. **RAGSkill Tests**:
   - Mock ChromaDB with specific historical cases
   - Edge cases: empty database, all low similarity scores
   - Boundary cases: exactly 5 cases, similarity score exactly 0.6

#### Integration Tests

**Purpose**: Test end-to-end workflows and component interactions

1. **Complete Workflow Test**:
   - Test full exception analysis from input to output
   - Verify all Skills are called in correct order
   - Verify final report structure and completeness
   - Use mock LLM for deterministic testing

2. **FastAPI Endpoint Test**:
   - Test POST /api/exception/analyze with valid input
   - Test input validation (missing fields, invalid types)
   - Test response format and status codes
   - Test error handling (500 errors, timeouts)

3. **Database Integration Test**:
   - Test exception record creation and updates
   - Test ai_analysis_report JSON storage
   - Test transaction rollback on errors

4. **Harness Integration Test**:
   - Test AgentLoop execution
   - Test ToolRegistry integration
   - Test ShortTermMemory and LongTermMemory
   - Test callback system

#### Error Handling Tests

**Purpose**: Verify graceful degradation and error recovery

1. **Skill Failure Tests**:
   - Mock individual Skill execution failures
   - Verify agent continues with remaining Skills
   - Verify error is logged and included in report

2. **LLM Failure Tests**:
   - Mock LLM API failures (timeout, rate limit, invalid response)
   - Verify retry logic (3 retries with exponential backoff)
   - Verify final error response format

3. **ChromaDB Failure Tests**:
   - Mock ChromaDB unavailability
   - Verify agent proceeds without historical cases
   - Verify limitation is noted in report

4. **Timeout Tests**:
   - Mock long-running operations
   - Verify 120-second timeout is enforced
   - Verify partial results are returned

#### Test Coverage Goals

- **Overall Coverage**: Minimum 80% code coverage for exception agent module
- **Critical Paths**: 100% coverage for:
  - Responsibility determination logic
  - Solution recommendation logic
  - Confidence score calculation
  - Review flagging conditions
- **Property Tests**: 100% of defined correctness properties
- **Integration Tests**: All major workflows and error paths

#### Test Execution

```bash
# Run all tests
pytest backend/tests/test_exception_agent/

# Run only property-based tests
pytest backend/tests/test_exception_agent/ -m property

# Run only unit tests
pytest backend/tests/test_exception_agent/ -m unit

# Run only integration tests
pytest backend/tests/test_exception_agent/ -m integration

# Run with coverage
pytest backend/tests/test_exception_agent/ --cov=backend/ai_modules/agents/exception_agent --cov-report=html
```

#### Test Data Generators

**For Property-Based Tests**:
```python
from hypothesis import strategies as st

# Exception type strategy
exception_types = st.sampled_from([
    '尺寸偏差', '表面缺陷', '材料问题', '组装问题'
])

# Material strategy
materials = st.sampled_from([
    '钢', '铝', '铜', '塑料', '不锈钢', '合金'
])

# Process type strategy
process_types = st.sampled_from([
    '数控加工', '精密加工', '普通加工', '车削', '铣削', '磨削'
])

# Description strategy (realistic exception descriptions)
descriptions = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')),
    min_size=20,
    max_size=500
)

# Quantity strategy
quantities = st.integers(min_value=1, max_value=10000)
```

**For Example-Based Tests**:
```python
# Sample exception data
SAMPLE_EXCEPTIONS = [
    {
        "exception_type": "尺寸偏差",
        "description": "轴承座内径尺寸超差0.5mm，超出公差范围",
        "material": "钢",
        "process_type": "数控加工",
        "expected_severity": "major",
        "expected_responsible_party": "supplier"
    },
    {
        "exception_type": "表面缺陷",
        "description": "零件表面有明显划痕和氧化",
        "material": "铝",
        "process_type": "精密加工",
        "expected_severity": "minor",
        "expected_responsible_party": "supplier"
    },
    # ... more examples
]
```

## Deployment Considerations

### Dependencies

```python
# requirements.txt additions
litellm>=1.0.0
chromadb>=0.4.0
langchain>=0.1.0
pydantic>=2.0.0
```

### Environment Variables

```bash
# .env additions
OPENAI_API_KEY=your_api_key
EXCEPTION_AGENT_MODEL=gpt-4
EXCEPTION_AGENT_TEMPERATURE=0.2
EXCEPTION_AGENT_MAX_STEPS=15
CHROMA_DB_PATH=./chroma_db/exception_agent
```

### Initialization

1. **Create Skills directory structure**:
   ```
   backend/ai_modules/skills/exception/
   ├── __init__.py
   ├── exception_analysis.py
   ├── responsibility_determination.py
   ├── solution_recommendation.py
   └── rag_skill.py
   ```

2. **Initialize ChromaDB**:
   - Create collection `exception_cases`
   - Load initial historical cases (if available)

3. **Register Skills**:
   - Skills auto-register via @tool decorator
   - Verify registration in ToolRegistry

4. **Test Agent**:
   - Run integration tests
   - Verify all Skills are accessible
   - Test with sample exception data

### Monitoring and Logging

1. **Structured Logging**:
   - Log all agent executions
   - Log Skill invocations and results
   - Log LLM API calls and responses
   - Log errors with stack traces

2. **Metrics**:
   - Track analysis success rate
   - Track average execution time
   - Track Skill execution times
   - Track confidence scores distribution

3. **Alerts**:
   - Alert on high error rate (>10%)
   - Alert on slow response time (>60s)
   - Alert on low confidence scores (<50%)

---

## Appendix A: Comparison with QuotationAgent

| Aspect | QuotationAgent | ExceptionAgent |
|--------|----------------|----------------|
| **Purpose** | Analyze supplier quotations | Analyze quality exceptions |
| **Skills** | QuotationAnalysis, HistoricalComparison, PriceNegotiation, RAG | ExceptionAnalysis, ResponsibilityDetermination, SolutionRecommendation, RAG |
| **Temperature** | 0.3 | 0.2 |
| **Max Steps** | 15 | 15 |
| **RAG Collection** | quotation_knowledge | exception_cases |
| **Output** | Quotation analysis report | Exception analysis report |
| **Key Decision** | Accept/Reject/Negotiate | Responsibility + Solution |

## Appendix B: File Structure

```
backend/
├── ai_modules/
│   ├── agents/
│   │   ├── quotation_agent.py  ✅ Existing
│   │   └── exception_agent.py  🆕 To be created
│   └── skills/
│       ├── quotation/  ✅ Existing
│       │   ├── quotation_analysis.py
│       │   ├── historical_comparison.py
│       │   ├── price_negotiation.py
│       │   └── rag_skill.py
│       └── exception/  🆕 To be created
│           ├── __init__.py
│           ├── exception_analysis.py
│           ├── responsibility_determination.py
│           ├── solution_recommendation.py
│           └── rag_skill.py
├── api/
│   └── routes/
│       ├── quotation.py  ✅ Existing
│       └── exception.py  🆕 To be created
└── harness/  ✅ Existing (Framework)
    ├── core/
    ├── tools/
    ├── memory/
    └── config/
```

## Appendix C: Implementation Checklist

- [ ] Create exception Skills directory structure
- [ ] Implement ExceptionAnalysisSkill
- [ ] Implement ResponsibilityDeterminationSkill
- [ ] Implement SolutionRecommendationSkill
- [ ] Implement RAGSkill for exceptions
- [ ] Implement ExceptionAgent class
- [ ] Create FastAPI endpoint /api/exception/analyze
- [ ] Write unit tests for each Skill
- [ ] Write integration tests for ExceptionAgent
- [ ] Write API endpoint tests
- [ ] Initialize ChromaDB collection
- [ ] Load sample historical cases
- [ ] Update database schema (ai_analysis_report column)
- [ ] Configure environment variables
- [ ] Test end-to-end workflow
- [ ] Deploy and monitor

---

**Document Version**: 1.0  
**Last Updated**: 2024-01-15  
**Status**: Draft - Ready for Review
