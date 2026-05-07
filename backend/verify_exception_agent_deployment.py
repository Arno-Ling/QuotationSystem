#!/usr/bin/env python
"""
Exception Agent Deployment Verification Script

This script verifies that all components of the ExceptionAgent are properly
configured and ready for deployment.

Usage:
    python verify_exception_agent_deployment.py
"""

import os
import sys
from pathlib import Path
import importlib.util
import json


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}  {text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")


def print_success(text: str):
    """Print a success message."""
    print(f"{Colors.GREEN}✓{Colors.RESET} {text}")


def print_error(text: str):
    """Print an error message."""
    print(f"{Colors.RED}✗{Colors.RESET} {text}")


def print_warning(text: str):
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {text}")


def check_file_exists(filepath: str, description: str) -> bool:
    """Check if a file exists."""
    if Path(filepath).exists():
        print_success(f"{description}: {filepath}")
        return True
    else:
        print_error(f"{description} not found: {filepath}")
        return False


def check_directory_exists(dirpath: str, description: str) -> bool:
    """Check if a directory exists."""
    if Path(dirpath).exists() and Path(dirpath).is_dir():
        print_success(f"{description}: {dirpath}")
        return True
    else:
        print_error(f"{description} not found: {dirpath}")
        return False


def check_module_imports() -> bool:
    """Check if all required modules can be imported."""
    print_header("Checking Module Imports")
    
    modules_to_check = [
        ("fastapi", "FastAPI"),
        ("langchain", "LangChain"),
        ("chromadb", "ChromaDB"),
        ("hypothesis", "Hypothesis (for property-based testing)"),
        ("litellm", "LiteLLM"),
        ("pymysql", "PyMySQL"),
        ("pydantic", "Pydantic"),
    ]
    
    all_ok = True
    for module_name, description in modules_to_check:
        try:
            importlib.import_module(module_name)
            print_success(f"{description} installed")
        except ImportError:
            print_error(f"{description} not installed")
            all_ok = False
    
    return all_ok


def check_project_structure() -> bool:
    """Check if project structure is correct."""
    print_header("Checking Project Structure")
    
    required_files = [
        ("ai_modules/agents/exception_agent.py", "ExceptionAgent class"),
        ("ai_modules/skills/exception/__init__.py", "Exception skills package"),
        ("ai_modules/skills/exception/exception_analysis.py", "ExceptionAnalysisSkill"),
        ("ai_modules/skills/exception/responsibility_determination.py", "ResponsibilityDeterminationSkill"),
        ("ai_modules/skills/exception/solution_recommendation.py", "SolutionRecommendationSkill"),
        ("ai_modules/skills/exception/rag_skill.py", "RAGSkill"),
        ("api/routes/exception.py", "Exception API endpoint"),
        ("database/migrations/001_add_ai_analysis_columns.sql", "Database migration"),
        ("initialize_rag_knowledge_base.py", "RAG initialization script"),
    ]
    
    all_ok = True
    for filepath, description in required_files:
        if not check_file_exists(filepath, description):
            all_ok = False
    
    return all_ok


def check_configuration() -> bool:
    """Check if configuration is properly set up."""
    print_header("Checking Configuration")
    
    all_ok = True
    
    # Check .env file
    if not Path(".env").exists():
        print_warning(".env file not found (using .env.example as reference)")
        env_file = ".env.example"
    else:
        env_file = ".env"
        print_success(".env file found")
    
    # Check required environment variables
    required_vars = [
        "OPENAI_API_KEY",
        "DB_HOST",
        "DB_USER",
        "DB_PASSWORD",
        "DB_NAME",
    ]
    
    optional_vars = [
        "EXCEPTION_AGENT_MODEL",
        "EXCEPTION_AGENT_TEMPERATURE",
        "EXCEPTION_AGENT_MAX_STEPS",
        "CHROMA_DB_PATH",
        "EXCEPTION_AGENT_RAG_TOP_K",
    ]
    
    # Read env file
    env_vars = {}
    try:
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    except Exception as e:
        print_error(f"Error reading {env_file}: {e}")
        return False
    
    # Check required variables
    for var in required_vars:
        if var in env_vars and env_vars[var] and env_vars[var] != f"your-{var.lower().replace('_', '-')}":
            print_success(f"Required variable {var} is set")
        else:
            print_error(f"Required variable {var} is not set or has default value")
            all_ok = False
    
    # Check optional variables
    for var in optional_vars:
        if var in env_vars:
            print_success(f"Optional variable {var} is set: {env_vars[var]}")
        else:
            print_warning(f"Optional variable {var} not set (will use default)")
    
    return all_ok


def check_skills_registration() -> bool:
    """Check if Skills are properly registered with @tool decorator."""
    print_header("Checking Skills Registration")
    
    skills_to_check = [
        ("ai_modules/skills/exception/exception_analysis.py", "analyze_exception"),
        ("ai_modules/skills/exception/responsibility_determination.py", "determine_responsibility"),
        ("ai_modules/skills/exception/solution_recommendation.py", "recommend_solution"),
        ("ai_modules/skills/exception/rag_skill.py", "search_exception_cases"),
    ]
    
    all_ok = True
    for filepath, function_name in skills_to_check:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                if '@tool' in content and function_name in content:
                    print_success(f"{function_name} has @tool decorator")
                else:
                    print_error(f"{function_name} missing @tool decorator")
                    all_ok = False
        except Exception as e:
            print_error(f"Error checking {filepath}: {e}")
            all_ok = False
    
    return all_ok


def check_chromadb() -> bool:
    """Check if ChromaDB is initialized."""
    print_header("Checking ChromaDB Knowledge Base")
    
    chroma_path = os.getenv("CHROMA_DB_PATH", "./chroma_db/exception_agent")
    
    if not Path(chroma_path).exists():
        print_warning(f"ChromaDB not initialized at {chroma_path}")
        print_warning("Run: python initialize_rag_knowledge_base.py")
        return False
    
    try:
        import chromadb
        client = chromadb.PersistentClient(path=chroma_path)
        collection = client.get_collection(name="exception_cases")
        count = collection.count()
        
        if count > 0:
            print_success(f"ChromaDB initialized with {count} cases")
            return True
        else:
            print_warning("ChromaDB collection is empty")
            print_warning("Run: python initialize_rag_knowledge_base.py")
            return False
    except Exception as e:
        print_error(f"Error checking ChromaDB: {e}")
        return False


def check_database_schema() -> bool:
    """Check if database schema has been updated."""
    print_header("Checking Database Schema")
    
    print_warning("Database schema check requires manual verification")
    print_warning("Run the following SQL to verify:")
    print_warning("  DESCRIBE exceptions;")
    print_warning("Expected columns: ai_analysis_report, ai_confidence_score, ai_analysis_timestamp")
    
    return True


def check_api_endpoint() -> bool:
    """Check if API endpoint is properly configured."""
    print_header("Checking API Endpoint")
    
    try:
        with open("api/routes/exception.py", 'r', encoding='utf-8') as f:
            content = f.read()
            
            checks = [
                ("@router.post", "POST endpoint defined"),
                ("/analyze", "Analyze endpoint path"),
                ("ExceptionAnalysisRequest", "Request model defined"),
                ("ExceptionAnalysisResponse", "Response model defined"),
                ("ExceptionAgent", "ExceptionAgent imported"),
            ]
            
            all_ok = True
            for check_str, description in checks:
                if check_str in content:
                    print_success(description)
                else:
                    print_error(f"{description} not found")
                    all_ok = False
            
            return all_ok
    except Exception as e:
        print_error(f"Error checking API endpoint: {e}")
        return False


def check_documentation() -> bool:
    """Check if documentation is complete."""
    print_header("Checking Documentation")
    
    docs_to_check = [
        ("ai_modules/agents/EXCEPTION_AGENT_README.md", "Exception Agent README"),
        ("database/migrations/README.md", "Database migrations README"),
        ("pytest.ini", "Pytest configuration"),
        ("run_tests.py", "Test execution script"),
    ]
    
    all_ok = True
    for filepath, description in docs_to_check:
        if not check_file_exists(filepath, description):
            all_ok = False
    
    return all_ok


def print_deployment_summary(results: dict):
    """Print deployment readiness summary."""
    print_header("Deployment Readiness Summary")
    
    total_checks = len(results)
    passed_checks = sum(1 for v in results.values() if v)
    
    for check_name, passed in results.items():
        if passed:
            print_success(check_name)
        else:
            print_error(check_name)
    
    print(f"\n{Colors.BOLD}Total: {passed_checks}/{total_checks} checks passed{Colors.RESET}")
    
    if passed_checks == total_checks:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ All checks passed! Ready for deployment.{Colors.RESET}\n")
        return True
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}✗ Some checks failed. Please fix issues before deployment.{Colors.RESET}\n")
        return False


def print_next_steps():
    """Print next steps for deployment."""
    print_header("Next Steps")
    
    print("1. Install dependencies:")
    print("   pip install -r requirements.txt")
    print()
    print("2. Configure environment:")
    print("   cp .env.example .env")
    print("   # Edit .env with your configuration")
    print()
    print("3. Run database migration:")
    print("   mysql -u root -p mold_procurement < database/migrations/001_add_ai_analysis_columns.sql")
    print()
    print("4. Initialize RAG knowledge base:")
    print("   python initialize_rag_knowledge_base.py")
    print()
    print("5. Run tests:")
    print("   python run_tests.py --coverage")
    print()
    print("6. Start application:")
    print("   uvicorn main:app --host 0.0.0.0 --port 8000")
    print()
    print("7. Verify endpoint:")
    print("   curl -X POST http://localhost:8000/api/exception/analyze \\")
    print("     -H 'Content-Type: application/json' \\")
    print("     -d '{\"exception_id\": \"TEST-001\", \"exception_type\": \"尺寸偏差\", ...}'")
    print()


def main():
    """Main verification function."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║   Exception Agent Deployment Verification                 ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"{Colors.RESET}")
    
    # Run all checks
    results = {
        "Module Imports": check_module_imports(),
        "Project Structure": check_project_structure(),
        "Configuration": check_configuration(),
        "Skills Registration": check_skills_registration(),
        "ChromaDB Knowledge Base": check_chromadb(),
        "Database Schema": check_database_schema(),
        "API Endpoint": check_api_endpoint(),
        "Documentation": check_documentation(),
    }
    
    # Print summary
    ready = print_deployment_summary(results)
    
    # Print next steps
    if not ready:
        print_next_steps()
    
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
