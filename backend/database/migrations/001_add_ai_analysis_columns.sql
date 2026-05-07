-- Migration: Add AI analysis columns to exceptions table
-- Date: 2024-01-15
-- Description: Add columns for storing AI analysis results from ExceptionAgent

USE mold_procurement;

-- Add ai_analysis_report column to store complete analysis JSON
ALTER TABLE exceptions 
ADD COLUMN ai_analysis_report JSON COMMENT 'AI分析报告JSON (包含analysis, responsibility, solutions, historical_cases)';

-- Add ai_confidence_score column to store confidence score from responsibility determination
ALTER TABLE exceptions 
ADD COLUMN ai_confidence_score FLOAT COMMENT 'AI责任判定置信度分数 (0-100)';

-- Add ai_analysis_timestamp column to track when AI analysis was performed
ALTER TABLE exceptions 
ADD COLUMN ai_analysis_timestamp DATETIME COMMENT 'AI分析完成时间';

-- Add index on ai_confidence_score for querying low-confidence cases
CREATE INDEX idx_ai_confidence_score ON exceptions(ai_confidence_score);

-- Add index on ai_analysis_timestamp for querying recent analyses
CREATE INDEX idx_ai_analysis_timestamp ON exceptions(ai_analysis_timestamp);

-- Verify the changes
DESCRIBE exceptions;
