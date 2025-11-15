#!/usr/bin/env python3
"""
Test Runner Script for QuizAgent End-to-End Tests

This script runs the comprehensive test suite and provides a summary of results.
"""

import sys
import subprocess
import os
from pathlib import Path


def check_dependencies():
    """Check if required testing dependencies are installed."""
    required_packages = ['pytest', 'pytest-mock']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for pkg in missing_packages:
            print(f"   - {pkg}")
        print("\n📦 Install missing packages with:")
        print(f"   pip install {' '.join(missing_packages)}")
        return False
    
    return True


def run_tests():
    """Run the end-to-end test suite."""
    print("=" * 70)
    print("🧪 QuizAgent End-to-End Test Suite")
    print("=" * 70)
    print()
    
    # Check dependencies
    print("📋 Checking dependencies...")
    if not check_dependencies():
        sys.exit(1)
    print("✅ All dependencies installed")
    print()
    
    # Get test file path
    test_file = Path(__file__).parent / "test_e2e.py"
    
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        sys.exit(1)
    
    # Run pytest
    print("🚀 Running tests...")
    print("-" * 70)
    print()
    
    try:
        # Run pytest with verbose output
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                str(test_file),
                "-v",  # Verbose output
                "--tb=short",  # Short traceback format
                "--color=yes",  # Colored output
                "-W", "ignore::DeprecationWarning"  # Suppress deprecation warnings
            ],
            check=False,
            capture_output=False
        )
        
        print()
        print("-" * 70)
        
        if result.returncode == 0:
            print("✅ All tests passed!")
            print()
            print("=" * 70)
            print("🎉 Test Suite Completed Successfully")
            print("=" * 70)
            return 0
        else:
            print("❌ Some tests failed")
            print()
            print("=" * 70)
            print("⚠️  Test Suite Completed with Failures")
            print("=" * 70)
            return result.returncode
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Error running tests: {e}")
        return 1


def run_specific_test_class(test_class_name):
    """Run a specific test class."""
    test_file = Path(__file__).parent / "test_e2e.py"
    
    result = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            str(test_file),
            f"::Test{test_class_name}",
            "-v",
            "--tb=short",
            "--color=yes"
        ],
        check=False
    )
    
    return result.returncode


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        # Run specific test class
        test_class = sys.argv[1]
        print(f"Running test class: {test_class}")
        sys.exit(run_specific_test_class(test_class))
    else:
        # Run all tests
        sys.exit(run_tests())


if __name__ == "__main__":
    main()

