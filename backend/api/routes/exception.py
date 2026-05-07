"""
Exception Analysis API Routes
Provides REST endpoints for exception analysis using ExceptionAgent
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, validator

# Import ExceptionAgent
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_modules.agents.exception_agent import ExceptionAgent

# Import database utilities
from database.db_utils import update_exception_with_analysis, DatabaseError

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/exception",
    tags=["exception"],
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"}
    }
)


# ============================================================================
# Pydantic Models
# ============================================================================

class ExceptionAnalysisRequest(BaseModel):
    """
    Request model for exception analysis
    """
    exception_id: str = Field(..., description="Unique exception identifier")
    exception_type: str = Field(
        ...,
        description="Exception type: 尺寸偏差, 表面缺陷, 材料问题, 组装问题"
    )
    description: str = Field(..., description="Detailed exception description")
    related_entity_id: str = Field(..., description="Related part_id or order_id")
    entity_type: str = Field(..., description="Entity type: part or order")
    project_id: str = Field(..., description="Project identifier")
    supplier_id: Optional[str] = Field(None, description="Supplier identifier")
    material: Optional[str] = Field(None, description="Material type")
    process_type: Optional[str] = Field(None, description="Process type")
    severity: Optional[str] = Field(None, description="Severity: critical, major, minor")
    quantity_affected: Optional[int] = Field(None, description="Number of affected items")
    
    @validator('exception_type')
    def validate_exception_type(cls, v):
        """Validate exception type"""
        valid_types = ['尺寸偏差', '表面缺陷', '材料问题', '组装问题']
        if v not in valid_types:
            raise ValueError(f'exception_type must be one of {valid_types}')
        return v
    
    @validator('entity_type')
    def validate_entity_type(cls, v):
        """Validate entity type"""
        valid_types = ['part', 'order']
        if v not in valid_types:
            raise ValueError(f'entity_type must be one of {valid_types}')
        return v
    
    @validator('severity')
    def validate_severity(cls, v):
        """Validate severity if provided"""
        if v is not None:
            valid_severities = ['critical', 'major', 'minor']
            if v not in valid_severities:
                raise ValueError(f'severity must be one of {valid_severities}')
        return v
    
    @validator('quantity_affected')
    def validate_quantity(cls, v):
        """Validate quantity is positive"""
        if v is not None and v <= 0:
            raise ValueError('quantity_affected must be positive')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "exception_id": "EXC001",
                "exception_type": "尺寸偏差",
                "description": "轴承座内径尺寸超差0.5mm，超出公差范围±0.2mm",
                "related_entity_id": "PART001",
                "entity_type": "part",
                "project_id": "PROJ001",
                "supplier_id": "SUP001",
                "material": "钢",
                "process_type": "数控加工",
                "quantity_affected": 50
            }
        }


class AnalysisResult(BaseModel):
    """Analysis result sub-model"""
    root_cause: str = Field(..., description="Root cause of the exception")
    severity: str = Field(..., description="Severity level")
    impact_scope: str = Field(..., description="Impact scope")
    contributing_factors: List[str] = Field(..., description="Contributing factors")


class ResponsibilityResult(BaseModel):
    """Responsibility determination sub-model"""
    responsible_party: str = Field(..., description="Responsible party")
    confidence_score: float = Field(..., description="Confidence score (0-100)")
    evidence: List[str] = Field(..., description="Evidence supporting determination")
    requires_review: bool = Field(..., description="Whether human review is required")


class SolutionResult(BaseModel):
    """Solution recommendation sub-model"""
    solution_type: str = Field(..., description="Solution type")
    description: str = Field(..., description="Solution description")
    cost_impact: float = Field(..., description="Estimated cost impact")
    time_impact: int = Field(..., description="Estimated time impact in days")
    feasibility_score: float = Field(..., description="Feasibility score (0-100)")
    implementation_steps: List[str] = Field(..., description="Implementation steps")


class HistoricalCase(BaseModel):
    """Historical case sub-model"""
    case_id: str = Field(..., description="Case identifier")
    exception_type: str = Field(..., description="Exception type")
    description: str = Field(..., description="Case description")
    responsible_party: str = Field(..., description="Responsible party")
    resolution: str = Field(..., description="Resolution details")
    outcome: str = Field(..., description="Outcome")
    similarity_score: float = Field(..., description="Similarity score (0-1)")


class ExceptionAnalysisResponse(BaseModel):
    """
    Response model for exception analysis
    """
    success: bool = Field(..., description="Whether analysis was successful")
    exception_data: Dict[str, Any] = Field(..., description="Original exception data")
    analysis: Optional[AnalysisResult] = Field(None, description="Analysis results")
    historical_cases: Optional[List[HistoricalCase]] = Field(None, description="Historical cases")
    responsibility: Optional[ResponsibilityResult] = Field(None, description="Responsibility determination")
    solutions: Optional[List[SolutionResult]] = Field(None, description="Recommended solutions")
    recommended_solution: Optional[str] = Field(None, description="Best recommended solution")
    analysis_report: Optional[str] = Field(None, description="Full text analysis report")
    timestamp: str = Field(..., description="Analysis timestamp")
    agent_steps: Optional[int] = Field(None, description="Number of agent steps executed")
    error: Optional[str] = Field(None, description="Error message if failed")
    error_type: Optional[str] = Field(None, description="Error type if failed")
    message: Optional[str] = Field(None, description="Additional message")
    database_update_warning: Optional[str] = Field(None, description="Warning if database update failed")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "exception_data": {
                    "exception_id": "EXC001",
                    "exception_type": "尺寸偏差",
                    "description": "轴承座内径尺寸超差0.5mm"
                },
                "analysis": {
                    "root_cause": "加工设备精度不足或刀具磨损",
                    "severity": "major",
                    "impact_scope": "batch",
                    "contributing_factors": ["设备精度", "刀具状态"]
                },
                "responsibility": {
                    "responsible_party": "supplier",
                    "confidence_score": 85.0,
                    "evidence": ["异常类型为尺寸偏差，通常由加工方负责"],
                    "requires_review": False
                },
                "solutions": [
                    {
                        "solution_type": "rework",
                        "description": "返工处理",
                        "cost_impact": 2500.0,
                        "time_impact": 5,
                        "feasibility_score": 90.0,
                        "implementation_steps": ["退回供应商", "重新加工"]
                    }
                ],
                "recommended_solution": "rework",
                "analysis_report": "【异常分析报告】...",
                "timestamp": "2024-01-15 11:00:00",
                "agent_steps": 8
            }
        }


# ============================================================================
# API Endpoints
# ============================================================================

@router.post(
    "/analyze",
    response_model=ExceptionAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze quality exception",
    description="Analyze a quality exception using AI agent to determine root cause, responsibility, and recommend solutions"
)
async def analyze_exception(request: ExceptionAnalysisRequest) -> ExceptionAnalysisResponse:
    """
    Analyze quality exception
    
    This endpoint receives exception data and uses the ExceptionAgent to:
    1. Analyze the root cause, severity, and impact
    2. Retrieve similar historical cases
    3. Determine the responsible party
    4. Recommend solutions with cost and time estimates
    
    Args:
        request: Exception analysis request data
        
    Returns:
        ExceptionAnalysisResponse: Comprehensive analysis report
        
    Raises:
        HTTPException 400: Invalid request data
        HTTPException 500: Analysis failure
    """
    # Log the incoming request
    logger.info(f"Received exception analysis request for exception_id: {request.exception_id}")
    logger.debug(f"Request data: {request.dict()}")
    
    try:
        # Convert request to dictionary
        exception_data = request.dict()
        
        # Create ExceptionAgent instance with configured model
        import os
        model_name = os.getenv("EXCEPTION_AGENT_MODEL", "gpt-4")
        logger.info(f"Creating ExceptionAgent instance with model: {model_name}...")
        agent = ExceptionAgent(
            model_name=model_name,
            enable_callbacks=True,
            enable_long_term_memory=True
        )
        
        # Analyze exception
        logger.info(f"Starting analysis for exception {request.exception_id}...")
        result = await agent.analyze_exception(exception_data)
        
        # Log the result
        logger.info(f"Analysis completed for exception {request.exception_id}")
        logger.debug(f"Analysis result: success={result.get('success')}, steps={result.get('agent_steps')}")
        
        # Update database with analysis results if analysis was successful
        if result.get('success', False):
            try:
                logger.info(f"Updating database with analysis results for exception {request.exception_id}...")
                update_success = update_exception_with_analysis(
                    exception_id=request.exception_id,
                    analysis_result=result
                )
                
                if update_success:
                    logger.info(f"Successfully updated database for exception {request.exception_id}")
                else:
                    logger.warning(f"Database update returned False for exception {request.exception_id}")
                    
            except DatabaseError as db_err:
                # Log database error but don't fail the entire request
                # The analysis was successful, just the database update failed
                logger.error(f"Database update failed for exception {request.exception_id}: {db_err}", exc_info=True)
                # Add a warning to the result
                result['database_update_warning'] = f"Analysis completed successfully but database update failed: {str(db_err)}"
                
            except Exception as db_err:
                # Catch any other unexpected database errors
                logger.error(f"Unexpected error during database update for exception {request.exception_id}: {db_err}", exc_info=True)
                result['database_update_warning'] = f"Analysis completed successfully but database update encountered an error: {str(db_err)}"
        
        # Check if analysis was successful
        if not result.get('success', False):
            # Analysis failed
            error_msg = result.get('error', 'Unknown error')
            error_type = result.get('error_type', 'UNKNOWN_ERROR')
            logger.error(f"Analysis failed: {error_type} - {error_msg}")
            
            # Return error response with HTTP 500
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "success": False,
                    "error": error_msg,
                    "error_type": error_type,
                    "message": result.get('message', 'Exception analysis failed'),
                    "exception_data": exception_data,
                    "timestamp": result.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                }
            )
        
        # Return successful response
        response = ExceptionAnalysisResponse(
            success=True,
            exception_data=exception_data,
            analysis_report=result.get('analysis_report'),
            timestamp=result.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            agent_steps=result.get('agent_steps'),
            database_update_warning=result.get('database_update_warning'),
            # Optional fields that may be parsed from the result
            analysis=result.get('analysis'),
            historical_cases=result.get('historical_cases'),
            responsibility=result.get('responsibility'),
            solutions=result.get('solutions'),
            recommended_solution=result.get('recommended_solution')
        )
        
        logger.info(f"Successfully returning analysis response for exception {request.exception_id}")
        return response
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    
    except ValueError as e:
        # Validation error
        logger.error(f"Validation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": str(e),
                "error_type": "VALIDATION_ERROR",
                "message": "Invalid request data",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        )
    
    except Exception as e:
        # Unexpected error
        logger.error(f"Unexpected error during exception analysis: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": str(e),
                "error_type": "INTERNAL_ERROR",
                "message": "An unexpected error occurred during analysis",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        )


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Check if the exception analysis service is healthy"
)
async def health_check():
    """
    Health check endpoint
    
    Returns:
        dict: Health status
    """
    return {
        "status": "healthy",
        "service": "exception-analysis",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
