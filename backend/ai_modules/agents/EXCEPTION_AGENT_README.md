# ExceptionAgent - Quality Exception Analysis Agent

## Overview

The ExceptionAgent is an AI-powered agent designed to analyze quality exceptions in the mold procurement system. It provides comprehensive analysis including root cause identification, responsibility determination, solution recommendations, and retrieval of similar historical cases.

## Architecture

The ExceptionAgent follows the same architectural pattern as QuotationAgent, integrating with the Harness framework and using specialized Skills for different analysis tasks.

### Components

```
ExceptionAgent
├── ExceptionAnalysisSkill      # Root cause, severity, impact analysis
├── ResponsibilityDeterminationSkill  # Determine responsible party
├── SolutionRecommendationSkill # Generate solution recommendations
└── RAGSkill                    # Retrieve similar historical cases
```

### Workflow

1. **Exception Analysis**: Analyze root cause, severity, and impact scope
2. **Historical Case Retrieval**: Search for similar cases using RAG
3. **Responsibility Determination**: Determine responsible party with confidence score
4. **Solution Recommendation**: Generate and rank solution options

## Skills

### 1. ExceptionAnalysisSkill

**Purpose**: Analyze quality exceptions to identify root causes, assess severity, and evaluate impact scope.

**Function**: `analyze_exception(exception_type, description, entity_type, material, process_type)`

**Input Parameters**:
- `exception_type` (str): Type of exception (尺寸偏差, 表面缺陷, 材料问题, 组装问题)
- `description` (str): Detailed description of the exception
- `entity_type` (str): Entity type (part, order)
- `material` (str, optional): Material type
- `process_type` (str, optional): Process type

**Output**:
```python
{
    "root_cause": str,              # Root cause analysis
    "severity": str,                # critical, major, minor
    "impact_scope": str,            # single_part, batch, entire_order
    "contributing_factors": List[str],  # Contributing factors
    "analysis_summary": str         # Analysis summary
}
```

**Example**:
```python
result = analyze_exception(
    exception_type="尺寸偏差",
    description="注塑件外径尺寸偏大0.5mm，超出公差范围±0.2mm",
    entity_type="part",
    material="ABS塑料",
    process_type="注塑成型"
)
```

### 2. ResponsibilityDeterminationSkill

**Purpose**: Determine the responsible party for quality exceptions with confidence scoring.

**Function**: `determine_responsibility(exception_type, root_cause, supplier_id, material, historical_cases)`

**Input Parameters**:
- `exception_type` (str): Type of exception
- `root_cause` (str): Root cause from analysis
- `supplier_id` (str, optional): Supplier ID
- `material` (str, optional): Material type
- `historical_cases` (List[Dict], optional): Historical cases for pattern analysis

**Output**:
```python
{
    "responsible_party": str,       # internal, supplier, material_vendor
    "confidence_score": float,      # 0-100
    "evidence": List[str],          # Evidence supporting determination
    "requires_review": bool,        # True if confidence < 70
    "reasoning": str                # Reasoning summary
}
```

**Responsibility Mapping**:
- **尺寸偏差** → supplier (processing issues)
- **表面缺陷** → supplier or material_vendor (depends on root cause)
- **材料问题** → material_vendor
- **组装问题** → internal or supplier (depends on context)

### 3. SolutionRecommendationSkill

**Purpose**: Generate and rank solution recommendations based on feasibility.

**Function**: `recommend_solution(exception_type, severity, root_cause, responsible_party, quantity_affected)`

**Input Parameters**:
- `exception_type` (str): Type of exception
- `severity` (str): Severity level (critical, major, minor)
- `root_cause` (str): Root cause from analysis
- `responsible_party` (str): Responsible party
- `quantity_affected` (int, optional): Quantity affected

**Output**:
```python
{
    "solutions": List[Dict],        # List of solution options
    "recommended_solution": Dict,   # Highest feasibility solution
    "summary": str                  # Recommendation summary
}
```

**Solution Types**:
1. **Rework**: Repair defective parts (3-7 days, moderate cost)
2. **Replacement**: Replace with new parts (7-14 days, higher cost)
3. **Temporary Acceptance**: Accept with documentation (1-2 days, low cost, minor defects only)
4. **Design Modification**: Modify design specifications (14-30 days, very high cost, systematic issues)

**Solution Structure**:
```python
{
    "solution_type": str,
    "description": str,
    "cost_impact": float,
    "time_impact": int,             # days
    "feasibility_score": float,     # 0-100
    "implementation_steps": List[str],
    "pros": List[str],
    "cons": List[str]
}
```

### 4. RAGSkill

**Purpose**: Retrieve similar historical exception cases using semantic search.

**Function**: `search_exception_cases(query, exception_type, top_k)`

**Input Parameters**:
- `query` (str): Search query (exception description)
- `exception_type` (str, optional): Filter by exception type
- `top_k` (int, optional): Number of results to return (default: 5)

**Output**:
```python
{
    "cases": List[Dict],            # Retrieved cases
    "summary": str,                 # Summary of findings
    "total_found": int              # Total cases found
}
```

**Case Structure**:
```python
{
    "case_id": str,
    "exception_type": str,
    "description": str,
    "root_cause": str,
    "responsible_party": str,
    "resolution": str,
    "outcome": str,
    "similarity_score": float,      # 0-1
    "resolution_date": str,
    "cost_impact": float,
    "time_impact_days": int
}
```

**Low Similarity Handling**: If all similarity scores < 0.6, returns "no relevant historical cases found"

## ExceptionAgent Class

### Initialization

```python
from ai_modules.agents.exception_agent import ExceptionAgent

agent = ExceptionAgent(
    model_name="gpt-4",
    enable_callbacks=True,
    enable_long_term_memory=True
)
```

**Configuration**:
- `model_name` (str): LLM model to use (default: "gpt-4")
- `temperature` (float): 0.2 (lower than QuotationAgent for deterministic analysis)
- `max_steps` (int): 15 (maximum reasoning steps)
- `enable_callbacks` (bool): Enable observability callbacks
- `enable_long_term_memory` (bool): Enable long-term memory with ChromaDB

### Usage

```python
# Prepare exception data
exception_data = {
    "exception_id": "EXC-2024-001",
    "exception_type": "尺寸偏差",
    "description": "注塑件外径尺寸偏大0.5mm，超出公差范围±0.2mm。检测发现整批50件均存在此问题。",
    "entity_type": "part",
    "material": "ABS塑料",
    "process_type": "注塑成型",
    "supplier_id": "SUP-001",
    "quantity_affected": 50
}

# Analyze exception
result = agent.analyze_exception(exception_data)

# Result structure
{
    "success": bool,
    "exception_id": str,
    "analysis": {
        "root_cause": str,
        "severity": str,
        "impact_scope": str,
        "contributing_factors": List[str],
        "analysis_summary": str
    },
    "responsibility": {
        "responsible_party": str,
        "confidence_score": float,
        "evidence": List[str],
        "requires_review": bool,
        "reasoning": str
    },
    "solutions": {
        "solutions": List[Dict],
        "recommended_solution": Dict,
        "summary": str
    },
    "historical_cases": {
        "cases": List[Dict],
        "summary": str,
        "total_found": int
    },
    "timestamp": str,
    "agent_steps": int
}
```

### Error Handling

The agent implements robust error handling:
- **Retry Logic**: 3 retries with exponential backoff for LLM API calls
- **Timeout**: 120 seconds maximum execution time
- **Graceful Degradation**: Returns partial results if one Skill fails
- **Comprehensive Logging**: All errors logged with stack traces

## API Endpoint

### POST /api/exception/analyze

Analyze a quality exception and return comprehensive analysis report.

**Request Body**:
```json
{
    "exception_id": "EXC-2024-001",
    "exception_type": "尺寸偏差",
    "description": "注塑件外径尺寸偏大0.5mm，超出公差范围±0.2mm",
    "entity_type": "part",
    "material": "ABS塑料",
    "process_type": "注塑成型",
    "supplier_id": "SUP-001",
    "quantity_affected": 50
}
```

**Response** (200 OK):
```json
{
    "success": true,
    "exception_id": "EXC-2024-001",
    "analysis": { ... },
    "responsibility": { ... },
    "solutions": { ... },
    "historical_cases": { ... },
    "timestamp": "2024-03-20T10:30:00Z",
    "agent_steps": 8
}
```

**Error Responses**:
- **400 Bad Request**: Invalid input data
- **500 Internal Server Error**: Analysis failure

## Database Integration

After successful analysis, the agent updates the exception record in the database:

**Updated Fields**:
- `ai_analysis_report` (JSON): Complete analysis report
- `responsible_party` (str): Determined responsible party
- `resolution_plan` (TEXT): Recommended solution
- `status` (str): Updated to "待确认" (pending confirmation)
- `ai_confidence_score` (float): Confidence score from responsibility determination
- `ai_analysis_timestamp` (datetime): Analysis timestamp

**Migration Script**: `backend/database/migrations/001_add_ai_analysis_columns.sql`

## RAG Knowledge Base

### Initialization

Initialize the ChromaDB knowledge base with sample historical cases:

```bash
cd backend
python initialize_rag_knowledge_base.py
```

This script:
1. Creates ChromaDB collection "exception_cases"
2. Loads 12 sample historical cases covering diverse exception types
3. Generates embeddings for semantic search
4. Verifies collection with test queries

**ChromaDB Path**: `./chroma_db/exception_agent` (configurable via `CHROMA_DB_PATH`)

### Adding New Cases

Use the `store_case()` function in RAGSkill to add resolved cases:

```python
from ai_modules.skills.exception.rag_skill import store_case

store_case(
    case_id="case_013",
    exception_type="尺寸偏差",
    description="...",
    resolution="...",
    metadata={
        "root_cause": "...",
        "responsible_party": "supplier",
        "outcome": "...",
        "resolution_date": "2024-03-20",
        "cost_impact": 5000.0,
        "time_impact_days": 4
    }
)
```

## Configuration

### Environment Variables

Add to `.env` file:

```bash
# Exception Agent Configuration
EXCEPTION_AGENT_MODEL=gpt-4
EXCEPTION_AGENT_TEMPERATURE=0.2
EXCEPTION_AGENT_MAX_STEPS=15
CHROMA_DB_PATH=./chroma_db/exception_agent
EXCEPTION_AGENT_RAG_TOP_K=5
```

### Configuration Loading

Configuration is loaded via `backend/config.py`:

```python
from config import settings

model = settings.EXCEPTION_AGENT_MODEL
temperature = settings.EXCEPTION_AGENT_TEMPERATURE
max_steps = settings.EXCEPTION_AGENT_MAX_STEPS
chroma_path = settings.CHROMA_DB_PATH
rag_top_k = settings.EXCEPTION_AGENT_RAG_TOP_K
```

## Testing Strategy

### Dual Testing Approach

1. **Property-Based Testing** (using Hypothesis):
   - Tests universal correctness properties
   - 100+ iterations per property
   - 8 correctness properties defined

2. **Example-Based Unit Testing**:
   - Tests specific scenarios and edge cases
   - Tests boundary conditions
   - Tests error handling

### Property Tests

**Property 1: Exception Analysis Completeness**
- Validates: All required fields present and non-empty
- Validates: Severity and impact_scope are valid enum values

**Property 2: Responsibility Classification Validity**
- Validates: responsible_party in {internal, supplier, material_vendor}
- Validates: evidence list non-empty
- Validates: confidence_score in [0, 100]

**Property 3: Low Confidence Review Flagging**
- Validates: requires_review = True when confidence_score < 70

**Property 4: Solution Recommendation Non-Empty**
- Validates: solutions list has at least one element

**Property 5: Solution Completeness and Validity**
- Validates: solution_type in valid set
- Validates: cost_impact >= 0, time_impact > 0
- Validates: feasibility_score in [0, 100]

**Property 6: Solution Ranking by Feasibility**
- Validates: solutions ordered by feasibility_score descending

**Property 7: Historical Case Retrieval Validity**
- Validates: at most 5 cases returned
- Validates: each case has required metadata
- Validates: similarity_score in [0, 1]

**Property 8: Low Similarity Case Handling**
- Validates: "no relevant historical cases found" when all scores < 0.6

### Running Tests

```bash
# Run all tests
cd backend
pytest

# Run with coverage
pytest --cov=ai_modules/agents --cov=ai_modules/skills/exception

# Run specific test types
pytest -m property  # Property-based tests only
pytest -m unit      # Unit tests only
pytest -m integration  # Integration tests only
```

## Deployment Steps

1. **Install Dependencies**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Run Database Migration**:
   ```bash
   mysql -u root -p mold_procurement < database/migrations/001_add_ai_analysis_columns.sql
   ```

4. **Initialize RAG Knowledge Base**:
   ```bash
   python initialize_rag_knowledge_base.py
   ```

5. **Start Application**:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

6. **Verify Endpoint**:
   ```bash
   curl -X POST http://localhost:8000/api/exception/analyze \
     -H "Content-Type: application/json" \
     -d '{"exception_id": "TEST-001", "exception_type": "尺寸偏差", ...}'
   ```

## Monitoring and Observability

The agent supports comprehensive observability through callbacks:

- `on_agent_start`: Triggered when analysis begins
- `on_agent_complete`: Triggered when analysis completes
- `on_error`: Triggered on errors
- `on_tool_start`: Triggered before each Skill execution
- `on_tool_complete`: Triggered after each Skill execution

All events are logged with detailed context for debugging and monitoring.

## Performance Considerations

- **Temperature**: Set to 0.2 for consistent, deterministic analysis
- **Max Steps**: Limited to 15 to prevent excessive reasoning loops
- **Timeout**: 120 seconds maximum execution time
- **RAG Top-K**: Default 5 cases to balance relevance and performance
- **Caching**: Consider implementing response caching for identical queries

## Comparison with QuotationAgent

| Aspect | ExceptionAgent | QuotationAgent |
|--------|----------------|----------------|
| Temperature | 0.2 | 0.3 |
| Purpose | Quality exception analysis | Quotation analysis |
| Skills | 4 (Analysis, Responsibility, Solution, RAG) | 4 (Analysis, Comparison, Negotiation, RAG) |
| RAG Collection | exception_cases | quotation_cases |
| Max Steps | 15 | 15 |
| Timeout | 120s | 120s |

## Troubleshooting

### Common Issues

1. **ChromaDB Not Found**:
   - Run `python initialize_rag_knowledge_base.py`
   - Check `CHROMA_DB_PATH` in `.env`

2. **LLM API Errors**:
   - Verify `OPENAI_API_KEY` in `.env`
   - Check API rate limits and quotas

3. **Database Connection Errors**:
   - Verify database credentials in `.env`
   - Ensure database migration has been run

4. **Low Confidence Scores**:
   - Review exception description quality
   - Add more historical cases to RAG knowledge base
   - Check if exception type is well-defined

## Future Enhancements

- [ ] Multi-language support for international suppliers
- [ ] Image analysis integration for visual defects
- [ ] Predictive analytics for exception prevention
- [ ] Integration with supplier quality management systems
- [ ] Automated resolution workflow triggers
- [ ] Real-time monitoring dashboard

## License

Internal use only - Mold Procurement System

## Contact

For questions or issues, contact the development team.
