"""
Test script for database integration
Tests the database utility functions for exception analysis
"""
import sys
import os
import json
from datetime import datetime

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'database'))
sys.path.insert(0, os.path.dirname(__file__))

from database.db_utils import (
    update_exception_with_analysis,
    get_exception_by_id,
    create_exception_record,
    DatabaseError
)


def test_database_connection():
    """Test basic database connection"""
    print("=" * 80)
    print("TEST 1: Database Connection")
    print("=" * 80)
    
    try:
        from database.db_utils import get_db_connection
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 as test")
            result = cursor.fetchone()
            cursor.close()
            
            if result and result.get('test') == 1:
                print("✓ Database connection successful")
                return True
            else:
                print("✗ Database connection failed - unexpected result")
                return False
                
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False


def test_create_exception():
    """Test creating an exception record"""
    print("\n" + "=" * 80)
    print("TEST 2: Create Exception Record")
    print("=" * 80)
    
    exception_data = {
        'exception_id': 'TEST_EXC_001',
        'project_id': 'PROJ001',
        'related_entity_id': 'PART001',
        'entity_type': 'part',
        'exception_type': '尺寸偏差',
        'description': '测试异常：轴承座内径尺寸超差0.5mm',
        'report_by': 'test_user'
    }
    
    try:
        # First, try to delete if exists
        try:
            from database.db_utils import get_db_connection
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM exceptions WHERE id = %s", (exception_data['exception_id'],))
                conn.commit()
                cursor.close()
        except:
            pass
        
        # Create the exception
        success = create_exception_record(exception_data)
        
        if success:
            print(f"✓ Exception record created: {exception_data['exception_id']}")
            
            # Verify it was created
            record = get_exception_by_id(exception_data['exception_id'])
            if record:
                print(f"✓ Exception record verified in database")
                print(f"  - ID: {record['id']}")
                print(f"  - Type: {record['exception_type']}")
                print(f"  - Status: {record['status']}")
                return True
            else:
                print("✗ Exception record not found after creation")
                return False
        else:
            print("✗ Failed to create exception record")
            return False
            
    except Exception as e:
        print(f"✗ Error creating exception: {e}")
        return False


def test_update_with_analysis():
    """Test updating exception with analysis results"""
    print("\n" + "=" * 80)
    print("TEST 3: Update Exception with Analysis Results")
    print("=" * 80)
    
    # Sample analysis result
    analysis_result = {
        'success': True,
        'analysis': {
            'root_cause': '加工设备精度不足或刀具磨损',
            'severity': 'major',
            'impact_scope': 'batch',
            'contributing_factors': ['设备精度', '刀具状态', '工艺参数']
        },
        'responsibility': {
            'responsible_party': 'supplier',
            'confidence_score': 85.0,
            'evidence': ['异常类型为尺寸偏差，通常由加工方负责', '历史案例显示该供应商有类似问题'],
            'requires_review': False,
            'reasoning': '基于异常类型和历史数据，判定为供应商加工问题'
        },
        'solutions': [
            {
                'solution_type': 'rework',
                'description': '对超差零件进行返工加工，修正内径尺寸',
                'cost_impact': 2500.0,
                'time_impact': 5,
                'feasibility_score': 90.0,
                'implementation_steps': ['退回供应商', '重新加工', '重新检验', '重新交付']
            },
            {
                'solution_type': 'replacement',
                'description': '重新制造新零件替换超差零件',
                'cost_impact': 5000.0,
                'time_impact': 10,
                'feasibility_score': 75.0,
                'implementation_steps': ['下达新订单', '重新生产', '检验新零件', '交付新零件']
            }
        ],
        'recommended_solution': 'rework',
        'historical_cases': [
            {
                'case_id': 'CASE123',
                'exception_type': '尺寸偏差',
                'description': '类似的内径超差问题',
                'responsible_party': 'supplier',
                'resolution': '返工处理',
                'outcome': '成功解决',
                'similarity_score': 0.85
            }
        ],
        'analysis_report': '【异常分析报告】\n一、基本信息\n异常类型：尺寸偏差\n...',
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'agent_steps': 8
    }
    
    try:
        # Update the exception
        success = update_exception_with_analysis(
            exception_id='TEST_EXC_001',
            analysis_result=analysis_result
        )
        
        if success:
            print("✓ Exception updated with analysis results")
            
            # Verify the update
            record = get_exception_by_id('TEST_EXC_001')
            if record:
                print(f"✓ Updated record verified:")
                print(f"  - Responsible Party: {record.get('responsible_party')}")
                print(f"  - Resolution Plan: {record.get('resolution_plan')[:50]}..." if record.get('resolution_plan') else "  - Resolution Plan: None")
                print(f"  - AI Confidence Score: {record.get('ai_confidence_score')}")
                print(f"  - AI Analysis Timestamp: {record.get('ai_analysis_timestamp')}")
                print(f"  - Status: {record.get('status')}")
                
                # Check if ai_analysis_report is valid JSON
                if record.get('ai_analysis_report'):
                    try:
                        report_json = json.loads(record['ai_analysis_report']) if isinstance(record['ai_analysis_report'], str) else record['ai_analysis_report']
                        print(f"  - AI Analysis Report: Valid JSON with {len(report_json)} keys")
                        print(f"    Keys: {list(report_json.keys())}")
                    except:
                        print(f"  - AI Analysis Report: Present but not valid JSON")
                else:
                    print(f"  - AI Analysis Report: None")
                
                # Verify expected values
                if record.get('responsible_party') == 'supplier':
                    print("✓ Responsible party correctly set to 'supplier'")
                else:
                    print(f"✗ Responsible party incorrect: {record.get('responsible_party')}")
                
                if record.get('ai_confidence_score') == 85.0:
                    print("✓ Confidence score correctly set to 85.0")
                else:
                    print(f"✗ Confidence score incorrect: {record.get('ai_confidence_score')}")
                
                if record.get('status') == '待确认':
                    print("✓ Status correctly updated to '待确认'")
                else:
                    print(f"✗ Status incorrect: {record.get('status')}")
                
                return True
            else:
                print("✗ Exception record not found after update")
                return False
        else:
            print("✗ Failed to update exception with analysis")
            return False
            
    except Exception as e:
        print(f"✗ Error updating exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cleanup():
    """Clean up test data"""
    print("\n" + "=" * 80)
    print("CLEANUP: Removing Test Data")
    print("=" * 80)
    
    try:
        from database.db_utils import get_db_connection
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM exceptions WHERE id = %s", ('TEST_EXC_001',))
            conn.commit()
            cursor.close()
            
        print("✓ Test data cleaned up")
        return True
        
    except Exception as e:
        print(f"✗ Error cleaning up: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("DATABASE INTEGRATION TESTS")
    print("=" * 80)
    
    results = []
    
    # Test 1: Connection
    results.append(("Database Connection", test_database_connection()))
    
    # Test 2: Create Exception
    results.append(("Create Exception", test_create_exception()))
    
    # Test 3: Update with Analysis
    results.append(("Update with Analysis", test_update_with_analysis()))
    
    # Cleanup
    test_cleanup()
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(main())
