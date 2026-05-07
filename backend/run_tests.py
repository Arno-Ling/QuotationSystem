#!/usr/bin/env python
"""
Test Execution Script for Exception Agent

This script runs all tests with coverage reporting and organizes tests by type.

Usage:
    python run_tests.py [options]
    
Options:
    --all           Run all tests (default)
    --property      Run property-based tests only
    --unit          Run unit tests only
    --integration   Run integration tests only
    --coverage      Generate coverage report
    --verbose       Verbose output
    --help          Show this help message
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd: list, description: str) -> int:
    """
    Run a command and return exit code.
    
    Args:
        cmd: Command to run as list
        description: Description of what's being run
        
    Returns:
        Exit code from command
    """
    print(f"\n{'='*60}")
    print(f"  {description}")
    print(f"{'='*60}\n")
    
    result = subprocess.run(cmd)
    return result.returncode


def main():
    """Main test execution function."""
    parser = argparse.ArgumentParser(
        description="Run Exception Agent tests with coverage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all tests (default)"
    )
    
    parser.add_argument(
        "--property",
        action="store_true",
        help="Run property-based tests only"
    )
    
    parser.add_argument(
        "--unit",
        action="store_true",
        help="Run unit tests only"
    )
    
    parser.add_argument(
        "--integration",
        action="store_true",
        help="Run integration tests only"
    )
    
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Generate coverage report"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    # Default to all tests if no specific type selected
    if not (args.property or args.unit or args.integration):
        args.all = True
    
    # Base pytest command
    pytest_cmd = ["pytest"]
    
    # Add verbosity
    if args.verbose:
        pytest_cmd.append("-v")
    
    # Add coverage if requested
    if args.coverage:
        pytest_cmd.extend([
            "--cov=ai_modules/agents",
            "--cov=ai_modules/skills/exception",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-report=xml"
        ])
    
    exit_code = 0
    
    # Run tests based on selection
    if args.all:
        # Run all tests
        cmd = pytest_cmd.copy()
        result = run_command(cmd, "Running All Tests")
        exit_code = max(exit_code, result)
        
    else:
        # Run specific test types
        if args.property:
            cmd = pytest_cmd + ["-m", "property"]
            result = run_command(cmd, "Running Property-Based Tests")
            exit_code = max(exit_code, result)
        
        if args.unit:
            cmd = pytest_cmd + ["-m", "unit"]
            result = run_command(cmd, "Running Unit Tests")
            exit_code = max(exit_code, result)
        
        if args.integration:
            cmd = pytest_cmd + ["-m", "integration"]
            result = run_command(cmd, "Running Integration Tests")
            exit_code = max(exit_code, result)
    
    # Print summary
    print(f"\n{'='*60}")
    print("  Test Execution Summary")
    print(f"{'='*60}")
    
    if exit_code == 0:
        print("✓ All tests passed!")
    else:
        print(f"✗ Tests failed with exit code {exit_code}")
    
    if args.coverage:
        print("\nCoverage reports generated:")
        print("  - HTML: htmlcov/index.html")
        print("  - XML: coverage.xml")
        print("  - Terminal: See above")
    
    print(f"{'='*60}\n")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
