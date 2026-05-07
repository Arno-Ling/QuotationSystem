# Requirements Document: ExceptionAgent Development

## Introduction

The ExceptionAgent is an AI-driven intelligent agent for handling quality exceptions in a mold outsourcing procurement system. It analyzes quality exceptions (defects found during inspection, assembly issues, etc.) and provides intelligent analysis including root cause determination, responsibility assignment, solution recommendations, and historical case matching using RAG (Retrieval-Augmented Generation).

This agent follows the same architectural pattern as the existing QuotationAgent, integrating with the Harness framework and using specialized Skills for different analysis tasks.

## Glossary

- **ExceptionAgent**: The AI-driven intelligent agent responsible for analyzing quality exceptions and providing recommendations
- **Harness**: The orchestration framework that manages agent execution, tool registration, and memory management
- **Skill**: A specialized capability registered as a tool that the agent can invoke to perform specific tasks
- **RAG (Retrieval-Augmented Generation)**: A technique that retrieves relevant historical data from a vector database to enhance AI analysis
- **Exception**: A quality issue or defect discovered during inspection, assembly, or production
- **Responsible_Party**: The entity accountable for an exception (internal team, supplier, or material vendor)
- **Resolution_Plan**: The recommended solution for addressing an exception
- **ChromaDB**: The vector database used for storing and retrieving historical exception cases
- **LangChain**: The AI framework used for building the agent and managing LLM interactions
- **FastAPI**: The web framework used for exposing agent functionality via REST endpoints
- **Tool_Registry**: The central registry where all Skills are registered using the @tool decorator

## Requirements

### Requirement 1: Exception Analysis Capability

**User Story:** As a quality inspector, I want the ExceptionAgent to analyze quality exceptions, so that I can understand the root cause and impact of defects.

#### Acceptance Criteria

1. WHEN an exception is submitted with type, description, and context, THE ExceptionAgent SHALL analyze the root cause
2. WHEN analyzing an exception, THE ExceptionAgent SHALL assess the severity level (critical, major, minor)
3. WHEN analyzing an exception, THE ExceptionAgent SHALL evaluate the impact scope (single part, batch, entire order)
4. THE ExceptionAgent SHALL identify contributing factors from the exception description
5. WHEN the analysis is complete, THE ExceptionAgent SHALL generate a structured analysis report containing root cause, severity, impact, and contributing factors

### Requirement 2: Responsibility Determination Capability

**User Story:** As a quality manager, I want the ExceptionAgent to determine which party is responsible for exceptions, so that I can assign accountability correctly.

#### Acceptance Criteria

1. WHEN an exception analysis is complete, THE ExceptionAgent SHALL determine the responsible party
2. THE ExceptionAgent SHALL classify responsibility as one of: internal, supplier, or material_vendor
3. WHEN determining responsibility, THE ExceptionAgent SHALL provide evidence supporting the determination
4. WHEN determining responsibility, THE ExceptionAgent SHALL calculate a confidence score (0-100)
5. IF the confidence score is below 70, THEN THE ExceptionAgent SHALL flag the determination as requiring human review
6. THE ExceptionAgent SHALL consider exception type, description, supplier history, and material specifications when determining responsibility

### Requirement 3: Solution Recommendation Capability

**User Story:** As a quality manager, I want the ExceptionAgent to recommend solutions for exceptions, so that I can resolve issues efficiently.

#### Acceptance Criteria

1. WHEN an exception is analyzed, THE ExceptionAgent SHALL recommend one or more solutions
2. THE ExceptionAgent SHALL support solution types: rework, replacement, temporary_acceptance, and design_modification
3. WHEN recommending a solution, THE ExceptionAgent SHALL estimate the cost impact
4. WHEN recommending a solution, THE ExceptionAgent SHALL estimate the time impact in days
5. WHEN multiple solutions are available, THE ExceptionAgent SHALL rank them by feasibility score
6. THE ExceptionAgent SHALL provide implementation steps for each recommended solution

### Requirement 4: Historical Case Matching via RAG

**User Story:** As a quality manager, I want the ExceptionAgent to find similar historical cases, so that I can learn from past resolutions.

#### Acceptance Criteria

1. WHEN analyzing an exception, THE ExceptionAgent SHALL retrieve similar historical cases from the vector database
2. THE ExceptionAgent SHALL retrieve the top 5 most similar historical cases based on semantic similarity
3. WHEN retrieving historical cases, THE ExceptionAgent SHALL include case metadata: exception type, responsible party, resolution, and outcome
4. THE ExceptionAgent SHALL calculate similarity scores (0-1) for each retrieved case
5. IF no similar cases exist with similarity score above 0.6, THEN THE ExceptionAgent SHALL indicate no relevant historical cases found
6. THE ExceptionAgent SHALL use historical case resolutions to inform current recommendations

### Requirement 5: Skills Implementation and Registration

**User Story:** As a developer, I want all ExceptionAgent capabilities implemented as Skills, so that they follow the established architectural pattern.

#### Acceptance Criteria

1. THE System SHALL implement ExceptionAnalysisSkill as a registered tool
2. THE System SHALL implement ResponsibilityDeterminationSkill as a registered tool
3. THE System SHALL implement SolutionRecommendationSkill as a registered tool
4. THE System SHALL implement RAGSkill for exception case retrieval as a registered tool
5. WHEN a Skill is implemented, THE System SHALL use the @tool decorator for registration
6. WHEN a Skill is registered, THE System SHALL specify permission level (read_only, read_write, or sensitive)
7. THE System SHALL register all Skills with the global Tool_Registry during module import

### Requirement 6: Agent Integration with Harness Framework

**User Story:** As a developer, I want the ExceptionAgent to integrate with the Harness framework, so that it follows the same pattern as QuotationAgent.

#### Acceptance Criteria

1. THE ExceptionAgent SHALL initialize with AgentConfig specifying model name, temperature, and max steps
2. THE ExceptionAgent SHALL use the global Tool_Registry to access registered Skills
3. THE ExceptionAgent SHALL create ShortTermMemory for conversation history management
4. THE ExceptionAgent SHALL create LongTermMemory using ChromaDB with collection name "exception_agent_memory"
5. THE ExceptionAgent SHALL create an AgentLoop instance for ReAct execution
6. WHEN processing an exception, THE ExceptionAgent SHALL execute the AgentLoop with a structured task description
7. THE ExceptionAgent SHALL use temperature 0.2 for consistent and deterministic analysis

### Requirement 7: Exception Processing Workflow

**User Story:** As a quality inspector, I want the ExceptionAgent to follow a systematic workflow, so that analysis is comprehensive and consistent.

#### Acceptance Criteria

1. WHEN processing an exception, THE ExceptionAgent SHALL execute Skills in the following order: ExceptionAnalysisSkill, RAGSkill, ResponsibilityDeterminationSkill, SolutionRecommendationSkill
2. THE ExceptionAgent SHALL pass exception data to ExceptionAnalysisSkill first
3. WHEN ExceptionAnalysisSkill completes, THE ExceptionAgent SHALL invoke RAGSkill to retrieve historical cases
4. WHEN historical cases are retrieved, THE ExceptionAgent SHALL invoke ResponsibilityDeterminationSkill with analysis and historical context
5. WHEN responsibility is determined, THE ExceptionAgent SHALL invoke SolutionRecommendationSkill with all prior context
6. THE ExceptionAgent SHALL synthesize all Skill outputs into a final comprehensive report
7. IF any Skill execution fails, THEN THE ExceptionAgent SHALL continue with remaining Skills and note the failure in the final report

### Requirement 8: FastAPI Endpoint Integration

**User Story:** As a frontend developer, I want to call the ExceptionAgent via REST API, so that I can integrate it into the web application.

#### Acceptance Criteria

1. THE System SHALL expose a POST endpoint at /api/exception/analyze
2. WHEN the endpoint receives a request, THE System SHALL validate the exception data schema
3. THE System SHALL accept exception data containing: exception_id, exception_type, description, related_entity_id, entity_type, project_id, and optional context fields
4. WHEN the endpoint is called, THE System SHALL invoke ExceptionAgent.analyze_exception with the provided data
5. WHEN analysis completes successfully, THE System SHALL return HTTP 200 with the analysis report
6. IF analysis fails, THEN THE System SHALL return HTTP 500 with error details
7. THE System SHALL log all API requests and responses for audit purposes

### Requirement 9: Database Integration for Exception Records

**User Story:** As a quality manager, I want exception analysis results saved to the database, so that I can track exception history.

#### Acceptance Criteria

1. WHEN ExceptionAgent analysis completes, THE System SHALL update the exceptions table with ai_analysis_report
2. THE System SHALL update the responsible_party field based on the agent's determination
3. THE System SHALL update the resolution_plan field with recommended solutions
4. THE System SHALL update the status field to "溯源中" (under investigation) when analysis starts
5. WHEN analysis completes, THE System SHALL update status to "待确认" (pending confirmation)
6. THE System SHALL preserve the original exception data (description, exception_type, report_by, report_at)
7. THE System SHALL record the timestamp of AI analysis completion in updated_at

### Requirement 10: RAG Knowledge Base Management

**User Story:** As a system administrator, I want historical exception cases stored in a vector database, so that the agent can learn from past cases.

#### Acceptance Criteria

1. THE System SHALL store resolved exception cases in ChromaDB collection "exception_cases"
2. WHEN an exception is resolved, THE System SHALL add the case to the vector database
3. THE System SHALL store exception metadata: exception_type, responsible_party, resolution_plan, outcome, and resolution_date
4. THE System SHALL generate embeddings from exception description and resolution details
5. WHEN querying the vector database, THE System SHALL use semantic similarity search
6. THE System SHALL support retrieval of top K similar cases where K is configurable (default 5)
7. THE System SHALL persist the vector database to disk at ./chroma_db/exception_agent

### Requirement 11: System Prompt and Agent Behavior

**User Story:** As a developer, I want the ExceptionAgent to have a specialized system prompt, so that it behaves appropriately for exception analysis.

#### Acceptance Criteria

1. THE ExceptionAgent SHALL use a system prompt that defines its role as a quality exception analysis assistant
2. THE System_Prompt SHALL instruct the agent to analyze exceptions systematically using available Skills
3. THE System_Prompt SHALL specify the expected workflow: analyze → retrieve historical cases → determine responsibility → recommend solutions
4. THE System_Prompt SHALL define the output format for the final analysis report
5. THE System_Prompt SHALL instruct the agent to provide evidence-based reasoning
6. THE System_Prompt SHALL specify that the agent should flag low-confidence determinations for human review
7. THE System_Prompt SHALL be stored in the ExceptionAgent class initialization method

### Requirement 12: Error Handling and Resilience

**User Story:** As a system operator, I want the ExceptionAgent to handle errors gracefully, so that partial failures don't prevent analysis completion.

#### Acceptance Criteria

1. WHEN a Skill execution fails, THE ExceptionAgent SHALL log the error with full stack trace
2. WHEN a Skill execution fails, THE ExceptionAgent SHALL continue executing remaining Skills
3. WHEN the LLM API call fails, THE ExceptionAgent SHALL retry up to 3 times with exponential backoff
4. IF all retries fail, THEN THE ExceptionAgent SHALL return an error response with details
5. WHEN the vector database is unavailable, THE ExceptionAgent SHALL proceed without historical case retrieval and note the limitation
6. THE ExceptionAgent SHALL validate input data and return clear error messages for invalid inputs
7. THE ExceptionAgent SHALL set a timeout of 120 seconds for the entire analysis workflow

### Requirement 13: Observability and Logging

**User Story:** As a system operator, I want comprehensive logging of agent execution, so that I can debug issues and monitor performance.

#### Acceptance Criteria

1. THE ExceptionAgent SHALL log the start of each exception analysis with exception_id and timestamp
2. THE ExceptionAgent SHALL log each Skill invocation with skill name and arguments
3. THE ExceptionAgent SHALL log each Skill result with success status and execution time
4. THE ExceptionAgent SHALL log the final analysis report generation
5. THE ExceptionAgent SHALL log the total execution time and number of agent steps
6. WHEN callbacks are enabled, THE ExceptionAgent SHALL use CallbackManager for execution tracking
7. THE System SHALL support log levels: DEBUG, INFO, WARNING, ERROR

### Requirement 14: Testing and Validation

**User Story:** As a developer, I want comprehensive tests for the ExceptionAgent, so that I can ensure it works correctly.

#### Acceptance Criteria

1. THE System SHALL include unit tests for each Skill (ExceptionAnalysisSkill, ResponsibilityDeterminationSkill, SolutionRecommendationSkill, RAGSkill)
2. THE System SHALL include integration tests for the complete ExceptionAgent workflow
3. THE System SHALL include tests for the FastAPI endpoint /api/exception/analyze
4. THE System SHALL include tests for error handling scenarios (invalid input, LLM failure, database unavailable)
5. THE System SHALL include tests for RAG retrieval with mock historical cases
6. THE System SHALL include tests verifying database updates after analysis
7. THE System SHALL achieve at least 80% code coverage for the exception agent module

### Requirement 15: Configuration and Customization

**User Story:** As a system administrator, I want to configure ExceptionAgent behavior, so that I can tune it for different environments.

#### Acceptance Criteria

1. THE ExceptionAgent SHALL accept configuration for LLM model name (default: "gpt-4")
2. THE ExceptionAgent SHALL accept configuration for temperature (default: 0.2)
3. THE ExceptionAgent SHALL accept configuration for max_steps (default: 15)
4. THE ExceptionAgent SHALL accept configuration for enabling/disabling long-term memory
5. THE ExceptionAgent SHALL accept configuration for enabling/disabling callbacks
6. THE ExceptionAgent SHALL accept configuration for RAG retrieval top_k (default: 5)
7. THE System SHALL support environment variables for API keys and database paths
