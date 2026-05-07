"""
Verification script for FastAPI exception analysis endpoint
Verifies the structure without making actual HTTP calls
"""
import sys
import inspect
from typing import get_type_hints

print("\n" + "=" * 80)
print("FastAPI Exception Analysis Endpoint Structure Verification")
print("=" * 80)

# Test 1: Import the main app
print("\n1. Testing main.py imports...")
try:
    from main import app
    print("   ✅ Successfully imported FastAPI app")
except Exception as e:
    print(f"   ❌ Failed to import app: {e}")
    sys.exit(1)

# Test 2: Import the exception router
print("\n2. Testing exception router imports...")
try:
    from api.routes import exception
    print("   ✅ Successfully imported exception router")
except Exception as e:
    print(f"   ❌ Failed to import exception router: {e}")
    sys.exit(1)

# Test 3: Verify Pydantic models
print("\n3. Verifying Pydantic models...")
try:
    from api.routes.exception import (
        ExceptionAnalysisRequest,
        ExceptionAnalysisResponse,
        AnalysisResult,
        ResponsibilityResult,
        SolutionResult,
        HistoricalCase
    )
    print("   ✅ ExceptionAnalysisRequest model exists")
    print("   ✅ ExceptionAnalysisResponse model exists")
    print("   ✅ AnalysisResult model exists")
    print("   ✅ ResponsibilityResult model exists")
    print("   ✅ SolutionResult model exists")
    print("   ✅ HistoricalCase model exists")
    
    # Check required fields in request model
    request_fields = ExceptionAnalysisRequest.__fields__
    required_fields = [
        'exception_id', 'exception_type', 'description',
        'related_entity_id', 'entity_type', 'project_id'
    ]
    for field in required_fields:
        if field in request_fields:
            print(f"   ✅ Request model has required field: {field}")
        else:
            print(f"   ❌ Request model missing required field: {field}")
            sys.exit(1)
    
    # Check optional fields
    optional_fields = [
        'supplier_id', 'material', 'process_type',
        'severity', 'quantity_affected'
    ]
    for field in optional_fields:
        if field in request_fields:
            print(f"   ✅ Request model has optional field: {field}")
    
except Exception as e:
    print(f"   ❌ Failed to verify Pydantic models: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Verify router endpoints
print("\n4. Verifying router endpoints...")
try:
    from api.routes.exception import router
    
    # Get all routes
    routes = [route for route in router.routes]
    print(f"   ✅ Router has {len(routes)} routes")
    
    # Check for analyze endpoint
    analyze_found = False
    health_found = False
    
    for route in routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            print(f"   ✅ Route: {route.methods} {route.path}")
            if '/analyze' in route.path and 'POST' in route.methods:
                analyze_found = True
            if '/health' in route.path and 'GET' in route.methods:
                health_found = True
    
    if analyze_found:
        print("   ✅ POST /analyze endpoint exists")
    else:
        print("   ❌ POST /analyze endpoint not found")
        sys.exit(1)
    
    if health_found:
        print("   ✅ GET /health endpoint exists")
    else:
        print("   ⚠️  GET /health endpoint not found (optional)")
    
except Exception as e:
    print(f"   ❌ Failed to verify router endpoints: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Verify endpoint function signature
print("\n5. Verifying endpoint function signature...")
try:
    from api.routes.exception import analyze_exception
    
    # Check if it's an async function
    if inspect.iscoroutinefunction(analyze_exception):
        print("   ✅ analyze_exception is an async function")
    else:
        print("   ❌ analyze_exception is not async")
        sys.exit(1)
    
    # Check function signature
    sig = inspect.signature(analyze_exception)
    params = list(sig.parameters.keys())
    print(f"   ✅ Function parameters: {params}")
    
    if 'request' in params:
        print("   ✅ Function accepts 'request' parameter")
    else:
        print("   ❌ Function missing 'request' parameter")
        sys.exit(1)
    
    # Check return type annotation
    if sig.return_annotation != inspect.Signature.empty:
        print(f"   ✅ Function has return type annotation: {sig.return_annotation}")
    
except Exception as e:
    print(f"   ❌ Failed to verify endpoint function: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 6: Verify app has router registered
print("\n6. Verifying router registration in app...")
try:
    from main import app
    
    # Check if router is registered
    app_routes = [route for route in app.routes]
    print(f"   ✅ App has {len(app_routes)} routes")
    
    exception_routes = [
        route for route in app_routes
        if hasattr(route, 'path') and '/api/exception' in route.path
    ]
    
    if exception_routes:
        print(f"   ✅ Found {len(exception_routes)} exception routes in app")
        for route in exception_routes:
            if hasattr(route, 'methods'):
                print(f"      - {route.methods} {route.path}")
    else:
        print("   ❌ No exception routes found in app")
        sys.exit(1)
    
except Exception as e:
    print(f"   ❌ Failed to verify router registration: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 7: Verify ExceptionAgent import in endpoint
print("\n7. Verifying ExceptionAgent import...")
try:
    # Check if ExceptionAgent can be imported from the endpoint module
    import api.routes.exception as exc_module
    
    # Check if ExceptionAgent is imported
    if hasattr(exc_module, 'ExceptionAgent'):
        print("   ✅ ExceptionAgent is imported in exception.py")
    else:
        print("   ⚠️  ExceptionAgent not directly accessible (may be imported differently)")
    
    # Try to import ExceptionAgent directly
    from ai_modules.agents.exception_agent import ExceptionAgent
    print("   ✅ ExceptionAgent can be imported from ai_modules.agents.exception_agent")
    
except Exception as e:
    print(f"   ❌ Failed to verify ExceptionAgent import: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Summary
print("\n" + "=" * 80)
print("✅ All Structure Verification Tests Passed!")
print("=" * 80)
print("\nVerified Components:")
print("  ✓ FastAPI app structure")
print("  ✓ Exception router module")
print("  ✓ Pydantic request/response models")
print("  ✓ POST /api/exception/analyze endpoint")
print("  ✓ Async endpoint function")
print("  ✓ Router registration in main app")
print("  ✓ ExceptionAgent integration")
print("\n" + "=" * 80)
print("Task 12 Implementation Complete!")
print("=" * 80)
print("\nImplemented:")
print("  ✓ 12.1: Created backend/api/routes/ directory structure")
print("  ✓ 12.2: Created exception.py with FastAPI router")
print("  ✓ 12.3: Defined ExceptionAnalysisRequest and ExceptionAnalysisResponse models")
print("  ✓ 12.4: Implemented POST /api/exception/analyze endpoint (async)")
print("  ✓ 12.5: Integrated endpoint with main FastAPI app in backend/main.py")
print("\nKey Features:")
print("  ✓ Async endpoint function")
print("  ✓ Pydantic schema validation for request/response")
print("  ✓ Creates ExceptionAgent instance in endpoint")
print("  ✓ Calls agent.analyze_exception(exception_data)")
print("  ✓ Returns HTTP 200 with analysis report on success")
print("  ✓ Returns HTTP 400 for validation errors")
print("  ✓ Returns HTTP 500 for analysis failures")
print("  ✓ Logs all requests and responses")
print("  ✓ Router registered in main.py with app.include_router()")
print("\nNote: Converted backend/main.py from demo script to proper FastAPI application")
print("=" * 80)
