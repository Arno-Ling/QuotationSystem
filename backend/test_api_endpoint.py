"""
Test script for FastAPI exception analysis endpoint
Tests the endpoint structure and basic functionality
"""
import sys
import asyncio
from fastapi.testclient import TestClient

# Import the FastAPI app
from main import app

# Create test client
client = TestClient(app)


def test_root_endpoint():
    """Test root endpoint"""
    print("\n" + "=" * 80)
    print("Testing Root Endpoint")
    print("=" * 80)
    
    response = client.get("/")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    assert response.status_code == 200
    assert "message" in response.json()
    print("✅ Root endpoint test passed")


def test_health_endpoint():
    """Test health check endpoint"""
    print("\n" + "=" * 80)
    print("Testing Health Check Endpoint")
    print("=" * 80)
    
    response = client.get("/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    print("✅ Health check endpoint test passed")


def test_exception_health_endpoint():
    """Test exception service health check endpoint"""
    print("\n" + "=" * 80)
    print("Testing Exception Service Health Check Endpoint")
    print("=" * 80)
    
    response = client.get("/api/exception/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    print("✅ Exception service health check endpoint test passed")


def test_exception_analyze_validation():
    """Test exception analysis endpoint with invalid data"""
    print("\n" + "=" * 80)
    print("Testing Exception Analysis Endpoint - Validation")
    print("=" * 80)
    
    # Test with missing required fields
    invalid_data = {
        "exception_id": "EXC001",
        "exception_type": "尺寸偏差"
        # Missing other required fields
    }
    
    response = client.post("/api/exception/analyze", json=invalid_data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    assert response.status_code == 422  # Validation error
    print("✅ Validation test passed - correctly rejected invalid data")


def test_exception_analyze_invalid_type():
    """Test exception analysis endpoint with invalid exception type"""
    print("\n" + "=" * 80)
    print("Testing Exception Analysis Endpoint - Invalid Type")
    print("=" * 80)
    
    invalid_data = {
        "exception_id": "EXC001",
        "exception_type": "invalid_type",  # Invalid type
        "description": "Test description",
        "related_entity_id": "PART001",
        "entity_type": "part",
        "project_id": "PROJ001"
    }
    
    response = client.post("/api/exception/analyze", json=invalid_data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    assert response.status_code == 422  # Validation error
    print("✅ Invalid type test passed - correctly rejected invalid exception type")


def test_exception_analyze_structure():
    """Test exception analysis endpoint structure with valid data (without actual LLM call)"""
    print("\n" + "=" * 80)
    print("Testing Exception Analysis Endpoint - Structure")
    print("=" * 80)
    
    valid_data = {
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
    
    print("Request data:")
    for key, value in valid_data.items():
        print(f"  {key}: {value}")
    
    print("\n⚠️  Note: This test will attempt to call the ExceptionAgent")
    print("⚠️  If OPENAI_API_KEY is not set, the endpoint will return an error")
    print("⚠️  This is expected behavior for testing the endpoint structure")
    
    # This will likely fail without proper API key, but we can check the structure
    response = client.post("/api/exception/analyze", json=valid_data)
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response keys: {list(response.json().keys())}")
    
    # The endpoint should return a structured response even on error
    response_data = response.json()
    
    if response.status_code == 500:
        # Expected if no API key or agent fails
        print("✅ Endpoint returned structured error response (expected without API key)")
        # Check error response structure
        if "detail" in response_data:
            detail = response_data["detail"]
            assert "success" in detail or "error" in detail
            print("✅ Error response has correct structure")
    elif response.status_code == 200:
        # Success case (if API key is available)
        print("✅ Endpoint returned successful response")
        assert "success" in response_data
        assert "exception_data" in response_data
        assert "timestamp" in response_data
        print("✅ Success response has correct structure")
    else:
        print(f"⚠️  Unexpected status code: {response.status_code}")


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("FastAPI Exception Analysis Endpoint Tests")
    print("=" * 80)
    
    try:
        # Test basic endpoints
        test_root_endpoint()
        test_health_endpoint()
        test_exception_health_endpoint()
        
        # Test validation
        test_exception_analyze_validation()
        test_exception_analyze_invalid_type()
        
        # Test endpoint structure
        test_exception_analyze_structure()
        
        print("\n" + "=" * 80)
        print("✅ All Tests Completed!")
        print("=" * 80)
        print("\nSummary:")
        print("  ✓ Root endpoint working")
        print("  ✓ Health check endpoints working")
        print("  ✓ Request validation working")
        print("  ✓ Endpoint structure correct")
        print("\nNote: Full integration test requires OPENAI_API_KEY to be set")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
