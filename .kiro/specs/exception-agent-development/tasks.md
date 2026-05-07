# Implementation Plan: ExceptionAgent Development

## Overview

This implementation plan breaks down the ExceptionAgent development into discrete, actionable coding tasks. The agent follows the same architectural pattern as QuotationAgent, integrating with the Harness framework and using specialized Skills for exception analysis, responsibility determination, solution recommendation, and historical case retrieval via RAG.

The implementation will be done in **Python**, following the existing codebase patterns and using the established Harness framework.

## Tasks

- [x] 1. Set up project structure for ExceptionAgent
  - Create `backend/ai_modules/skills/exception/` directory
  - Create `__init__.py` files for proper module imports
  - Create placeholder files for all four Skills
  - _Requirements: 5.1, 5.7_

- [x] 2. Implement ExceptionAnalysisSkill
  - [x] 2.1 Create exception_analysis.py with @tool decorator
    - Implement `analyze_exception()` function with proper type hints
    - Define input parameters: exception_type, description, entity_type, material, process_type
    - Define return structure with root_cause, severity, impact_scope, contributing_factors
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 5.1, 5.5, 5.6_
  
  - [x] 2.2 Implement root cause analysis logic
    - Create mapping from exception_type to common root causes
    - Parse description for keywords and patterns
    - Consider material and process_type factors
    - Generate root_cause string with reasoning
    - _Requirements: 1.1_
  
  - [x] 2.3 Implement severity assessment logic
    - Define severity classification rules (critical, major, minor)
    - Analyze exception description for severity indicators
    - Return severity level with justification
    - _Requirements: 1.2_
  
  - [x] 2.4 Implement impact scope evaluation logic
    - Determine impact_scope (single_part, batch, entire_order)
    - Consider quantity_affected and exception_type
    - Return impact_scope with reasoning
    - _Requirements: 1.3_
  
  - [x] 2.5 Implement contributing factors identification
    - Identify material quality factors
    - Identify process control factors
    - Identify design specification factors
    - Return list of contributing_factors
    - _Requirements: 1.4_
  
  - [x] 2.6 Generate analysis summary
    - Synthesize all analysis components into summary text
    - Return complete analysis result dictionary
    - _Requirements: 1.5_
  
  - [ ]* 2.7 Write property test for ExceptionAnalysisSkill
    - **Property 1: Exception Analysis Completeness**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**
    - Use Hypothesis to generate random exception data (100+ iterations)
    - Verify all required fields are present and non-empty
    - Verify severity and impact_scope are valid enum values
  
  - [ ]* 2.8 Write unit tests for ExceptionAnalysisSkill
    - Test specific exception types (尺寸偏差, 表面缺陷, 材料问题, 组装问题)
    - Test edge cases: empty description, unknown material
    - Test boundary cases: very long descriptions, special characters
    - _Requirements: 14.1_

- [x] 3. Checkpoint - Verify ExceptionAnalysisSkill
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement ResponsibilityDeterminationSkill
  - [x] 4.1 Create responsibility_determination.py with @tool decorator
    - Implement `determine_responsibility()` function with proper type hints
    - Define input parameters: exception_type, root_cause, supplier_id, material, historical_cases
    - Define return structure with responsible_party, confidence_score, evidence, requires_review
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 5.2, 5.5, 5.6_
  
  - [x] 4.2 Implement exception type to responsibility mapping
    - Create mapping rules for each exception_type
    - 尺寸偏差 → supplier (processing)
    - 表面缺陷 → supplier or material_vendor
    - 材料问题 → material_vendor
    - 组装问题 → internal or supplier
    - _Requirements: 2.1, 2.6_
  
  - [x] 4.3 Implement evidence collection logic
    - Extract keywords from exception description
    - Analyze root_cause for responsibility indicators
    - Consider supplier history patterns
    - Consider material specifications
    - Analyze historical_cases for patterns
    - Return list of evidence strings
    - _Requirements: 2.3, 2.6_
  
  - [x] 4.4 Implement confidence score calculation
    - Calculate base confidence from exception_type mapping
    - Adjust confidence based on evidence strength
    - Adjust confidence based on historical case consistency
    - Return confidence_score in range [0, 100]
    - _Requirements: 2.4_
  
  - [x] 4.5 Implement review flagging logic
    - Set requires_review = True if confidence_score < 70
    - Set requires_review = True if conflicting evidence detected
    - Return requires_review boolean
    - _Requirements: 2.5_
  
  - [x] 4.6 Generate responsibility reasoning summary
    - Synthesize determination logic into reasoning text
    - Return complete responsibility result dictionary
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
  
  - [ ]* 4.7 Write property test for responsibility classification
    - **Property 2: Responsibility Classification Validity**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
    - Verify responsible_party is in {internal, supplier, material_vendor}
    - Verify evidence list is non-empty
    - Verify confidence_score is in [0, 100]
  
  - [ ]* 4.8 Write property test for review flagging
    - **Property 3: Low Confidence Review Flagging**
    - **Validates: Requirement 2.5**
    - Verify requires_review = True when confidence_score < 70
  
  - [ ]* 4.9 Write unit tests for ResponsibilityDeterminationSkill
    - Test specific responsibility scenarios (clear supplier fault, clear internal fault)
    - Test edge cases: conflicting evidence, no historical data
    - Test boundary cases: confidence score exactly 70
    - _Requirements: 14.1_

- [x] 5. Checkpoint - Verify ResponsibilityDeterminationSkill
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement SolutionRecommendationSkill
  - [x] 6.1 Create solution_recommendation.py with @tool decorator
    - Implement `recommend_solution()` function with proper type hints
    - Define input parameters: exception_type, severity, root_cause, responsible_party, quantity_affected
    - Define return structure with solutions list and recommended_solution
    - _Requirements: 3.1, 3.2, 5.3, 5.5, 5.6_
  
  - [x] 6.2 Implement solution generation for "rework" type
    - Define rework applicability rules
    - Calculate cost_impact based on quantity and complexity
    - Calculate time_impact (3-7 days typical)
    - Calculate feasibility_score
    - Generate implementation_steps list
    - Generate pros and cons lists
    - _Requirements: 3.2, 3.3, 3.4, 3.6_
  
  - [x] 6.3 Implement solution generation for "replacement" type
    - Define replacement applicability rules
    - Calculate cost_impact (higher than rework)
    - Calculate time_impact (7-14 days typical)
    - Calculate feasibility_score
    - Generate implementation_steps list
    - Generate pros and cons lists
    - _Requirements: 3.2, 3.3, 3.4, 3.6_
  
  - [x] 6.4 Implement solution generation for "temporary_acceptance" type
    - Define temporary acceptance applicability rules (minor defects only)
    - Calculate cost_impact (low, documentation only)
    - Calculate time_impact (1-2 days)
    - Calculate feasibility_score
    - Generate implementation_steps list
    - Generate pros and cons lists
    - _Requirements: 3.2, 3.3, 3.4, 3.6_
  
  - [x] 6.5 Implement solution generation for "design_modification" type
    - Define design modification applicability rules (systematic issues)
    - Calculate cost_impact (very high)
    - Calculate time_impact (14-30 days)
    - Calculate feasibility_score (typically low)
    - Generate implementation_steps list
    - Generate pros and cons lists
    - _Requirements: 3.2, 3.3, 3.4, 3.6_
  
  - [x] 6.6 Implement solution ranking logic
    - Sort solutions by feasibility_score in descending order
    - Select recommended_solution (highest feasibility)
    - _Requirements: 3.5_
  
  - [x] 6.7 Generate recommendation summary
    - Synthesize all solutions into summary text
    - Return complete solution recommendation dictionary
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_
  
  - [ ]* 6.8 Write property test for solution non-empty
    - **Property 4: Solution Recommendation Non-Empty**
    - **Validates: Requirement 3.1**
    - Verify solutions list has at least one element
  
  - [ ]* 6.9 Write property test for solution completeness
    - **Property 5: Solution Completeness and Validity**
    - **Validates: Requirements 3.2, 3.3, 3.4, 3.6**
    - Verify solution_type is in valid set
    - Verify cost_impact >= 0
    - Verify time_impact > 0
    - Verify feasibility_score in [0, 100]
    - Verify implementation_steps is non-empty list
  
  - [ ]* 6.10 Write property test for solution ranking
    - **Property 6: Solution Ranking by Feasibility**
    - **Validates: Requirement 3.5**
    - Verify solutions are ordered by feasibility_score descending
  
  - [ ]* 6.11 Write unit tests for SolutionRecommendationSkill
    - Test specific severity-solution mappings
    - Test edge cases: zero quantity, unknown exception type
    - Test boundary cases: very high cost, very long time
    - _Requirements: 14.1_

- [x] 7. Checkpoint - Verify SolutionRecommendationSkill
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement RAGSkill for exception cases
  - [x] 8.1 Create rag_skill.py with @tool decorator
    - Implement `search_exception_cases()` function with proper type hints
    - Define input parameters: query, exception_type, top_k
    - Define return structure with cases list, summary, total_found
    - _Requirements: 4.1, 4.2, 4.3, 5.4, 5.5, 5.6_
  
  - [x] 8.2 Initialize ChromaDB client and collection
    - Create ChromaDB client with persist_directory
    - Create or get collection "exception_cases"
    - Configure embedding function
    - _Requirements: 10.1, 10.7_
  
  - [x] 8.3 Implement semantic search logic
    - Convert query to embedding
    - Search ChromaDB collection with top_k parameter
    - Filter by exception_type if specified
    - Calculate similarity scores
    - _Requirements: 4.1, 4.2, 10.5_
  
  - [x] 8.4 Implement case metadata extraction
    - Extract exception_type, responsible_party, resolution, outcome from metadata
    - Extract resolution_date and other fields
    - Format case data into structured dictionary
    - _Requirements: 4.3_
  
  - [x] 8.5 Implement low similarity handling
    - Check if all similarity scores < 0.6
    - Set summary to "no relevant historical cases found" if true
    - _Requirements: 4.5_
  
  - [x] 8.6 Implement case storage function (for adding new cases)
    - Create function to add resolved cases to ChromaDB
    - Generate embeddings from description + resolution
    - Store with complete metadata
    - _Requirements: 10.2, 10.3, 10.4_
  
  - [x] 8.7 Generate search summary
    - Synthesize retrieved cases into summary text
    - Return complete RAG result dictionary
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
  
  - [ ]* 8.8 Write property test for historical case retrieval
    - **Property 7: Historical Case Retrieval Validity**
    - **Validates: Requirements 4.2, 4.3, 4.4**
    - Verify at most 5 cases returned
    - Verify each case has required metadata
    - Verify similarity_score in [0, 1]
  
  - [ ]* 8.9 Write property test for low similarity handling
    - **Property 8: Low Similarity Case Handling**
    - **Validates: Requirement 4.5**
    - Verify "no relevant historical cases found" when all scores < 0.6
  
  - [ ]* 8.10 Write unit tests for RAGSkill
    - Test with mock ChromaDB and specific historical cases
    - Test edge cases: empty database, all low similarity scores
    - Test boundary cases: exactly 5 cases, similarity score exactly 0.6
    - _Requirements: 14.1, 14.5_

- [x] 9. Checkpoint - Verify RAGSkill
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement ExceptionAgent class
  - [x] 10.1 Create exception_agent.py file
    - Import required dependencies (Harness, Skills, LangChain)
    - Define ExceptionAgent class structure
    - _Requirements: 6.1, 6.2_
  
  - [x] 10.2 Implement __init__ method
    - Accept configuration parameters: model_name, enable_callbacks, enable_long_term_memory
    - Create AgentConfig with temperature=0.2, max_steps=15
    - Get global ToolRegistry instance
    - Create ShortTermMemory instance
    - Create LongTermMemory with ChromaDB collection "exception_agent_memory"
    - Create CallbackManager if callbacks enabled
    - Create AgentLoop instance
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.7, 15.1, 15.2, 15.3, 15.4, 15.5_
  
  - [x] 10.3 Implement _create_system_prompt method
    - Define agent role as quality exception analysis assistant
    - Specify available Skills and their purposes
    - Define workflow: analyze → retrieve cases → determine responsibility → recommend solutions
    - Define output format for final analysis report
    - Instruct agent to provide evidence-based reasoning
    - Instruct agent to flag low-confidence determinations
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_
  
  - [x] 10.4 Implement analyze_exception method
    - Accept exception_data dictionary as input
    - Build task description using _build_analysis_task
    - Trigger on_agent_start callback if enabled
    - Execute AgentLoop.run(task)
    - Trigger on_agent_complete callback if enabled
    - Parse result using _parse_analysis_result
    - Handle exceptions and trigger on_error callback
    - Return structured analysis result
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 12.1, 12.2, 12.7, 13.1, 13.2, 13.3, 13.4, 13.5_
  
  - [x] 10.5 Implement _build_analysis_task method
    - Format exception_data into structured task description
    - Include all relevant fields: exception_type, description, material, process_type, etc.
    - Specify workflow steps for the agent to follow
    - Return formatted task string
    - _Requirements: 7.1_
  
  - [x] 10.6 Implement _parse_analysis_result method
    - Parse AgentLoop result string
    - Extract analysis, responsibility, solutions, historical_cases sections
    - Structure into final result dictionary
    - Include success flag, timestamp, agent_steps
    - Return structured result
    - _Requirements: 7.6_
  
  - [x] 10.7 Implement get_state method
    - Return agent state information
    - Include agent_type, model, tools_available, agent_loop_state
    - _Requirements: 6.1_
  
  - [x] 10.8 Implement error handling and retry logic
    - Wrap LLM API calls with retry logic (3 retries, exponential backoff)
    - Handle Skill execution failures gracefully
    - Continue with remaining Skills if one fails
    - Log all errors with stack traces
    - Return partial results on timeout (120s)
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.7_
  
  - [ ]* 10.9 Write integration tests for ExceptionAgent
    - Test complete workflow from input to output
    - Verify all Skills are called in correct order
    - Verify final report structure and completeness
    - Use mock LLM for deterministic testing
    - _Requirements: 14.2_

- [x] 11. Checkpoint - Verify ExceptionAgent
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Implement FastAPI endpoint
  - [x] 12.1 Create exception.py in backend/api/routes/
    - Import FastAPI dependencies and ExceptionAgent
    - Define router for exception endpoints
    - _Requirements: 8.1_
  
  - [x] 12.2 Define request and response schemas
    - Create ExceptionAnalysisRequest Pydantic model
    - Create ExceptionAnalysisResponse Pydantic model
    - Include all required fields with proper types
    - _Requirements: 8.3_
  
  - [x] 12.3 Implement POST /api/exception/analyze endpoint
    - Define async endpoint function
    - Validate request data using Pydantic schema
    - Create ExceptionAgent instance
    - Call agent.analyze_exception(exception_data)
    - Return HTTP 200 with analysis report on success
    - Return HTTP 400 for validation errors
    - Return HTTP 500 for analysis failures
    - Log all requests and responses
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_
  
  - [x] 12.4 Integrate endpoint with main FastAPI app
    - Import exception router in main.py
    - Register router with app.include_router()
    - _Requirements: 8.1_
  
  - [ ]* 12.5 Write API endpoint tests
    - Test POST /api/exception/analyze with valid input
    - Test input validation (missing fields, invalid types)
    - Test response format and status codes
    - Test error handling (500 errors, timeouts)
    - _Requirements: 14.3_

- [x] 13. Implement database integration
  - [x] 13.1 Update database schema
    - Add ai_analysis_report JSON column to exceptions table
    - Add ai_confidence_score FLOAT column
    - Add ai_analysis_timestamp DATETIME column
    - Create migration script
    - _Requirements: 9.1, 9.2, 9.3_
  
  - [x] 13.2 Implement database update logic in endpoint
    - After successful analysis, update exception record
    - Set ai_analysis_report with complete analysis JSON
    - Set responsible_party from agent determination
    - Set resolution_plan from recommended solutions
    - Update status to "待确认" (pending confirmation)
    - Set ai_confidence_score and ai_analysis_timestamp
    - Preserve original exception data
    - Handle database errors with transaction rollback
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_
  
  - [ ]* 13.3 Write database integration tests
    - Test exception record creation and updates
    - Test ai_analysis_report JSON storage
    - Test transaction rollback on errors
    - _Requirements: 14.6_

- [x] 14. Initialize RAG knowledge base
  - [x] 14.1 Create ChromaDB initialization script
    - Create script to initialize ChromaDB collection
    - Set persist_directory to ./chroma_db/exception_agent
    - Configure embedding function
    - _Requirements: 10.1, 10.7_
  
  - [x] 14.2 Create sample historical cases data
    - Define sample resolved exception cases
    - Include diverse exception types and resolutions
    - Format with complete metadata
    - _Requirements: 10.2, 10.3, 10.4_
  
  - [x] 14.3 Implement case loading script
    - Read sample cases from JSON or CSV
    - Generate embeddings for each case
    - Store in ChromaDB with metadata
    - Verify storage with test queries
    - _Requirements: 10.2, 10.3, 10.4, 10.5, 10.6_

- [x] 15. Configuration and environment setup
  - [x] 15.1 Update requirements.txt
    - Add litellm>=1.0.0
    - Add chromadb>=0.4.0
    - Add langchain>=0.1.0
    - Add hypothesis>=6.0.0 (for property-based testing)
    - Verify all dependencies are compatible
    - _Requirements: 15.7_
  
  - [x] 15.2 Create .env.example updates
    - Add EXCEPTION_AGENT_MODEL=gpt-4
    - Add EXCEPTION_AGENT_TEMPERATURE=0.2
    - Add EXCEPTION_AGENT_MAX_STEPS=15
    - Add CHROMA_DB_PATH=./chroma_db/exception_agent
    - Add EXCEPTION_AGENT_RAG_TOP_K=5
    - _Requirements: 15.1, 15.2, 15.3, 15.6, 15.7_
  
  - [x] 15.3 Create configuration loading in config.py
    - Load exception agent environment variables
    - Provide default values
    - Validate configuration values
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6_

- [x] 16. Documentation and testing
  - [x] 16.1 Create comprehensive docstrings
    - Document all Skills with parameter descriptions
    - Document ExceptionAgent class and methods
    - Document API endpoint with request/response examples
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_
  
  - [x] 16.2 Create test execution script
    - Create script to run all tests with coverage
    - Configure pytest markers (property, unit, integration)
    - Set up coverage reporting
    - _Requirements: 14.7_
  
  - [x] 16.3 Create README for exception agent module
    - Document architecture and components
    - Document Skills and their purposes
    - Document workflow and usage examples
    - Document testing strategy
    - Document deployment steps

- [ ] 17. End-to-end integration testing
  - [ ]* 17.1 Write end-to-end workflow test
    - Test complete flow: API request → Agent execution → Database update
    - Use real exception data samples
    - Verify all components work together
    - Verify database records are updated correctly
    - _Requirements: 14.2_
  
  - [ ]* 17.2 Write error handling integration tests
    - Test LLM API failure scenarios
    - Test ChromaDB unavailability
    - Test database connection failures
    - Test timeout scenarios
    - Verify graceful degradation
    - _Requirements: 14.4_

- [x] 18. Final checkpoint and deployment preparation
  - Ensure all tests pass with minimum 80% coverage
  - Verify all Skills are registered correctly
  - Verify ChromaDB is initialized with sample cases
  - Verify API endpoint is accessible
  - Verify database schema is updated
  - Run end-to-end test with real data
  - Ask the user if questions arise before deployment.

## Notes

- Tasks marked with `*` are optional testing tasks and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at logical breaks
- Property tests validate universal correctness properties (8 properties total)
- Unit tests validate specific examples and edge cases for each Skill
- Integration tests validate end-to-end workflows and component interactions
- The implementation follows the QuotationAgent pattern for consistency
- All Skills use the @tool decorator for automatic registration
- Temperature is set to 0.2 for consistent and deterministic analysis
- ChromaDB is used for RAG with collection name "exception_cases"
- The agent uses ReAct pattern via AgentLoop for systematic reasoning
