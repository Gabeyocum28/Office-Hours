#!/usr/bin/env python3
# run_tests.py - Simple test runner for Office Hours AI

import os
import sys
import subprocess
import argparse

def run_command(command):
    """Run a shell command and return success status."""
    print(f"🏃 Running: {' '.join(command)}")
    try:
        result = subprocess.run(command)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Command failed: {e}")
        return False

def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="Office Hours AI Test Runner")
    
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--coverage", action="store_true", help="Run tests with coverage")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # If no specific action is specified, run all tests
    if not any([args.unit, args.integration, args.all, args.coverage]):
        args.all = True
    
    # Build pytest command
    cmd = [sys.executable, "-m", "pytest", "tests/"]
    
    if args.verbose:
        cmd.append("-v")
    
    if args.coverage:
        cmd.extend(["--cov=app", "--cov-report=html", "--cov-report=term"])
    
    if args.unit:
        cmd.extend(["-m", "unit"])
    elif args.integration:
        cmd.extend(["-m", "integration"])
    
    # Run the tests
    success = run_command(cmd)
    
    if success:
        print("\n🎉 Tests completed successfully!")
        if args.coverage:
            print("📊 Coverage report generated in htmlcov/")
        return 0
    else:
        print("\n💥 Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())