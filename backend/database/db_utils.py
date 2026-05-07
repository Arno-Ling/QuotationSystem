"""
Database utility functions for exception management
Provides connection and transaction management for MySQL database
"""
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor

from config import settings

# Configure logging
logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom exception for database errors"""
    pass


@contextmanager
def get_db_connection():
    """
    Context manager for database connections
    
    Yields:
        pymysql.Connection: Database connection
        
    Raises:
        DatabaseError: If connection fails
    """
    connection = None
    try:
        # Create connection
        connection = pymysql.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            charset='utf8mb4',
            cursorclass=DictCursor,
            autocommit=False  # Use explicit transactions
        )
        logger.debug(f"Database connection established to {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
        yield connection
        
    except pymysql.Error as e:
        logger.error(f"Database connection error: {e}", exc_info=True)
        raise DatabaseError(f"Failed to connect to database: {e}")
        
    finally:
        if connection:
            connection.close()
            logger.debug("Database connection closed")


def update_exception_with_analysis(
    exception_id: str,
    analysis_result: Dict[str, Any],
    connection: Optional[pymysql.Connection] = None
) -> bool:
    """
    Update exception record with AI analysis results
    
    Args:
        exception_id: Exception identifier
        analysis_result: Complete analysis result from ExceptionAgent
        connection: Optional existing database connection (for transaction management)
        
    Returns:
        bool: True if update successful, False otherwise
        
    Raises:
        DatabaseError: If database operation fails
    """
    # Extract fields from analysis result
    responsible_party = None
    resolution_plan = None
    ai_confidence_score = None
    ai_analysis_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Extract responsibility information
    if 'responsibility' in analysis_result and analysis_result['responsibility']:
        resp = analysis_result['responsibility']
        responsible_party = resp.get('responsible_party')
        ai_confidence_score = resp.get('confidence_score')
    
    # Extract solution information for resolution plan
    if 'solutions' in analysis_result and analysis_result['solutions']:
        solutions = analysis_result['solutions']
        if solutions:
            # Use the recommended solution or first solution
            recommended = analysis_result.get('recommended_solution')
            if recommended:
                # Find the recommended solution details
                for sol in solutions:
                    if sol.get('solution_type') == recommended:
                        resolution_plan = sol.get('description')
                        break
            if not resolution_plan and solutions:
                resolution_plan = solutions[0].get('description')
    
    # Prepare ai_analysis_report JSON
    ai_analysis_report = {
        'analysis': analysis_result.get('analysis'),
        'responsibility': analysis_result.get('responsibility'),
        'solutions': analysis_result.get('solutions'),
        'historical_cases': analysis_result.get('historical_cases'),
        'recommended_solution': analysis_result.get('recommended_solution'),
        'analysis_report': analysis_result.get('analysis_report'),
        'timestamp': analysis_result.get('timestamp'),
        'agent_steps': analysis_result.get('agent_steps')
    }
    
    # Convert to JSON string
    ai_analysis_report_json = json.dumps(ai_analysis_report, ensure_ascii=False)
    
    # Determine if we should use provided connection or create new one
    use_existing_connection = connection is not None
    
    try:
        if not use_existing_connection:
            # Create new connection with context manager
            with get_db_connection() as conn:
                return _execute_update(
                    conn,
                    exception_id,
                    responsible_party,
                    resolution_plan,
                    ai_analysis_report_json,
                    ai_confidence_score,
                    ai_analysis_timestamp
                )
        else:
            # Use existing connection (caller manages transaction)
            return _execute_update(
                connection,
                exception_id,
                responsible_party,
                resolution_plan,
                ai_analysis_report_json,
                ai_confidence_score,
                ai_analysis_timestamp
            )
            
    except Exception as e:
        logger.error(f"Failed to update exception {exception_id}: {e}", exc_info=True)
        raise DatabaseError(f"Failed to update exception record: {e}")


def _execute_update(
    connection: pymysql.Connection,
    exception_id: str,
    responsible_party: Optional[str],
    resolution_plan: Optional[str],
    ai_analysis_report_json: str,
    ai_confidence_score: Optional[float],
    ai_analysis_timestamp: str
) -> bool:
    """
    Execute the actual database update
    
    Args:
        connection: Database connection
        exception_id: Exception identifier
        responsible_party: Responsible party (internal, supplier, material_vendor)
        resolution_plan: Resolution plan text
        ai_analysis_report_json: Complete analysis report as JSON string
        ai_confidence_score: Confidence score (0-100)
        ai_analysis_timestamp: Timestamp of analysis
        
    Returns:
        bool: True if update successful
        
    Raises:
        DatabaseError: If update fails
    """
    cursor = None
    try:
        cursor = connection.cursor()
        
        # Build UPDATE query
        update_query = """
            UPDATE exceptions
            SET 
                responsible_party = %s,
                resolution_plan = %s,
                ai_analysis_report = %s,
                ai_confidence_score = %s,
                ai_analysis_timestamp = %s,
                status = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        
        # Set status to "待确认" (pending confirmation) after analysis
        new_status = "待确认"
        
        # Execute update
        params = (
            responsible_party,
            resolution_plan,
            ai_analysis_report_json,
            ai_confidence_score,
            ai_analysis_timestamp,
            new_status,
            exception_id
        )
        
        logger.debug(f"Executing update for exception {exception_id}")
        logger.debug(f"Parameters: responsible_party={responsible_party}, status={new_status}, confidence={ai_confidence_score}")
        
        rows_affected = cursor.execute(update_query, params)
        
        # Commit the transaction
        connection.commit()
        
        if rows_affected == 0:
            logger.warning(f"No rows updated for exception_id {exception_id} - exception may not exist")
            return False
        
        logger.info(f"Successfully updated exception {exception_id} with AI analysis results")
        return True
        
    except pymysql.Error as e:
        # Rollback on error
        logger.error(f"Database error during update: {e}", exc_info=True)
        connection.rollback()
        raise DatabaseError(f"Database update failed: {e}")
        
    finally:
        if cursor:
            cursor.close()


def get_exception_by_id(exception_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve exception record by ID
    
    Args:
        exception_id: Exception identifier
        
    Returns:
        Optional[Dict[str, Any]]: Exception record or None if not found
        
    Raises:
        DatabaseError: If database operation fails
    """
    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            
            query = "SELECT * FROM exceptions WHERE id = %s"
            cursor.execute(query, (exception_id,))
            
            result = cursor.fetchone()
            cursor.close()
            
            return result
            
    except Exception as e:
        logger.error(f"Failed to retrieve exception {exception_id}: {e}", exc_info=True)
        raise DatabaseError(f"Failed to retrieve exception: {e}")


def create_exception_record(exception_data: Dict[str, Any]) -> bool:
    """
    Create a new exception record
    
    Args:
        exception_data: Exception data dictionary
        
    Returns:
        bool: True if creation successful
        
    Raises:
        DatabaseError: If database operation fails
    """
    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            
            # Build INSERT query
            insert_query = """
                INSERT INTO exceptions (
                    id, project_id, related_entity_id, entity_type,
                    exception_type, description, report_by, status
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
            """
            
            params = (
                exception_data.get('exception_id'),
                exception_data.get('project_id'),
                exception_data.get('related_entity_id'),
                exception_data.get('entity_type'),
                exception_data.get('exception_type'),
                exception_data.get('description'),
                exception_data.get('report_by', 'system'),
                '溯源中'  # Initial status: under investigation
            )
            
            cursor.execute(insert_query, params)
            connection.commit()
            cursor.close()
            
            logger.info(f"Successfully created exception record {exception_data.get('exception_id')}")
            return True
            
    except Exception as e:
        logger.error(f"Failed to create exception record: {e}", exc_info=True)
        raise DatabaseError(f"Failed to create exception: {e}")
