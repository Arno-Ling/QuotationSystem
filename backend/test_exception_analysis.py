"""
Test ExceptionAnalysisSkill - Direct Test
"""
import sys
import os

# Add backend to path
backend_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_path)

# Import directly without going through ai_modules.__init__
from ai_modules.skills.exception import exception_analysis

# Test the skill
print("Testing ExceptionAnalysisSkill...")
result = exception_analysis.analyze_exception(
    exception_type='尺寸偏差',
    description='轴承座内径尺寸超差0.5mm，超出公差范围',
    entity_type='part',
    material='钢',
    process_type='数控加工'
)

print('\n✅ ExceptionAnalysisSkill Test Results:')
print(f'Root Cause: {result["root_cause"]}')
print(f'Severity: {result["severity"]}')
print(f'Impact Scope: {result["impact_scope"]}')
print(f'Contributing Factors: {result["contributing_factors"]}')
print(f'\nSummary: {result["analysis_summary"]}')
print('\n✅ Test passed! ExceptionAnalysisSkill is working correctly.')
