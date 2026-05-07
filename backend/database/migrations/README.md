# Database Migrations

This directory contains SQL migration scripts for the mold procurement system database.

## Migration Files

### 001_add_ai_analysis_columns.sql

**Purpose**: Add AI analysis columns to the exceptions table for storing ExceptionAgent analysis results.

**Changes**:
- Adds `ai_analysis_report` JSON column to store complete analysis results
- Adds `ai_confidence_score` FLOAT column to store confidence score (0-100)
- Adds `ai_analysis_timestamp` DATETIME column to track when analysis was performed
- Creates indexes on `ai_confidence_score` and `ai_analysis_timestamp` for query performance

**When to Run**: Before deploying the ExceptionAgent feature (Task 13 completion)

**How to Run**:
```bash
# Connect to MySQL
mysql -u root -p

# Run the migration
source backend/database/migrations/001_add_ai_analysis_columns.sql

# Or use mysql command directly
mysql -u root -p mold_procurement < backend/database/migrations/001_add_ai_analysis_columns.sql
```

**Verification**:
```sql
USE mold_procurement;
DESCRIBE exceptions;

-- Should show the new columns:
-- ai_analysis_report (JSON)
-- ai_confidence_score (FLOAT)
-- ai_analysis_timestamp (DATETIME)

-- Check indexes
SHOW INDEX FROM exceptions;
```

**Rollback** (if needed):
```sql
USE mold_procurement;

-- Remove indexes
DROP INDEX idx_ai_confidence_score ON exceptions;
DROP INDEX idx_ai_analysis_timestamp ON exceptions;

-- Remove columns
ALTER TABLE exceptions DROP COLUMN ai_analysis_report;
ALTER TABLE exceptions DROP COLUMN ai_confidence_score;
ALTER TABLE exceptions DROP COLUMN ai_analysis_timestamp;
```

## Migration Process

1. **Backup Database**: Always backup the database before running migrations
   ```bash
   mysqldump -u root -p mold_procurement > backup_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **Test in Development**: Run migrations in development environment first

3. **Run Migration**: Execute the migration script

4. **Verify Changes**: Check that columns and indexes were created correctly

5. **Test Application**: Verify that the application works with the new schema

## AI Analysis Report JSON Structure

The `ai_analysis_report` column stores a JSON object with the following structure:

```json
{
  "analysis": {
    "root_cause": "加工设备精度不足或刀具磨损",
    "severity": "major",
    "impact_scope": "batch",
    "contributing_factors": ["设备精度", "刀具状态", "工艺参数"]
  },
  "responsibility": {
    "responsible_party": "supplier",
    "confidence_score": 85.0,
    "evidence": ["异常类型为尺寸偏差，通常由加工方负责"],
    "requires_review": false,
    "reasoning": "基于异常类型和历史数据，判定为供应商加工问题"
  },
  "solutions": [
    {
      "solution_type": "rework",
      "description": "对超差零件进行返工加工，修正内径尺寸",
      "cost_impact": 2500.0,
      "time_impact": 5,
      "feasibility_score": 90.0,
      "implementation_steps": ["退回供应商", "重新加工", "重新检验", "重新交付"]
    }
  ],
  "historical_cases": [
    {
      "case_id": "CASE123",
      "exception_type": "尺寸偏差",
      "similarity_score": 0.85
    }
  ],
  "recommended_solution": "rework",
  "analysis_report": "【完整的文本分析报告】...",
  "timestamp": "2024-01-15 11:00:00",
  "agent_steps": 8
}
```

## Database Update Logic

When the ExceptionAgent completes analysis, the following fields are updated:

1. **ai_analysis_report**: Complete JSON analysis result
2. **ai_confidence_score**: Confidence score from responsibility determination
3. **ai_analysis_timestamp**: Timestamp when analysis completed
4. **responsible_party**: Extracted from analysis (internal, supplier, material_vendor)
5. **resolution_plan**: Extracted from recommended solution
6. **status**: Updated to "待确认" (pending confirmation)
7. **updated_at**: Automatically updated by MySQL

## Transaction Handling

The database update logic uses transactions to ensure data consistency:

- **Commit**: If all updates succeed
- **Rollback**: If any update fails
- **Error Logging**: All database errors are logged with full stack traces

## Error Handling

If database update fails:
- The analysis result is still returned to the user
- A warning is included in the response: `database_update_warning`
- The error is logged for investigation
- The system continues to function (graceful degradation)

## Querying AI Analysis Results

Example queries:

```sql
-- Get exceptions with low confidence scores (require review)
SELECT id, exception_type, responsible_party, ai_confidence_score
FROM exceptions
WHERE ai_confidence_score < 70
ORDER BY ai_confidence_score ASC;

-- Get recent AI analyses
SELECT id, exception_type, status, ai_analysis_timestamp
FROM exceptions
WHERE ai_analysis_timestamp IS NOT NULL
ORDER BY ai_analysis_timestamp DESC
LIMIT 10;

-- Get exceptions by responsible party
SELECT id, exception_type, responsible_party, ai_confidence_score
FROM exceptions
WHERE responsible_party = 'supplier'
AND ai_analysis_timestamp IS NOT NULL;

-- Extract specific fields from JSON
SELECT 
    id,
    exception_type,
    JSON_EXTRACT(ai_analysis_report, '$.analysis.severity') as severity,
    JSON_EXTRACT(ai_analysis_report, '$.recommended_solution') as recommended_solution
FROM exceptions
WHERE ai_analysis_report IS NOT NULL;
```

## Notes

- The `ai_analysis_report` column uses JSON type for flexible storage and querying
- Indexes are created on frequently queried columns for performance
- The migration is idempotent - safe to run multiple times (uses `ADD COLUMN` which fails gracefully if column exists)
- All timestamps use MySQL DATETIME type for consistency
- Character set is utf8mb4 to support Chinese characters
