#!/usr/bin/env python3
"""
Test runner script for multi-provider-router
Provides convenient ways to run tests with different configurations
"""

import subprocess
import sys
import argparse
from pathlib import Path


def run_command(cmd, description):
    """Run a command and print results"""
    print(f"\n{'='*70}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*70}\n")

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"\n❌ {description} failed with exit code {result.returncode}")
        return False
    else:
        print(f"\n✅ {description} succeeded")
        return True


def run_all_tests(verbose=False, coverage=True):
    """Run all tests"""
    cmd = ["pytest", "tests/"]

    if verbose:
        cmd.append("-vv")

    if coverage:
        cmd.extend([
            "--cov=multi_provider_router",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov",
            "--cov-report=xml:coverage.xml"
        ])

    return run_command(cmd, "All Tests")


def run_unit_tests(verbose=False):
    """Run only unit tests"""
    cmd = ["pytest", "tests/", "-m", "unit"]

    if verbose:
        cmd.append("-vv")

    return run_command(cmd, "Unit Tests")


def run_integration_tests(verbose=False):
    """Run only integration tests"""
    cmd = ["pytest", "tests/", "-m", "integration"]

    if verbose:
        cmd.append("-vv")

    return run_command(cmd, "Integration Tests")


def run_specific_test_file(test_file, verbose=False):
    """Run tests from a specific file"""
    cmd = ["pytest", test_file]

    if verbose:
        cmd.append("-vv")

    return run_command(cmd, f"Tests in {test_file}")


def run_tests_with_pattern(pattern, verbose=False):
    """Run tests matching a pattern"""
    cmd = ["pytest", "-k", pattern]

    if verbose:
        cmd.append("-vv")

    return run_command(cmd, f"Tests matching '{pattern}'")


def run_coverage_report():
    """Generate and display coverage report"""
    cmd = [
        "pytest",
        "--cov=multi_provider_router",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov",
        "tests/"
    ]

    success = run_command(cmd, "Coverage Report")

    if success:
        print("\n📊 Coverage report generated in htmlcov/ directory")
        print("   Open htmlcov/index.html in your browser to view")

    return success


def run_fast_tests():
    """Run fast tests only (exclude slow)"""
    cmd = ["pytest", "tests/", "-m", "not slow"]

    return run_command(cmd, "Fast Tests (excluding slow)")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Test runner for multi-provider-router",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all tests with coverage
  python run_tests.py

  # Run all tests verbosely
  python run_tests.py --verbose --all

  # Run only unit tests
  python run_tests.py --unit

  # Run only integration tests
  python run_tests.py --integration

  # Run specific test file
  python run_tests.py --file tests/test_providers.py

  # Run tests matching pattern
  python run_tests.py --pattern "glm"

  # Run fast tests only
  python run_tests.py --fast

  # Generate coverage report
  python run_tests.py --coverage
        """
    )

    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only")
    parser.add_argument("--file", type=str, help="Run specific test file")
    parser.add_argument("--pattern", type=str, help="Run tests matching pattern")
    parser.add_argument("--fast", action="store_true", help="Run fast tests only (exclude slow)")
    parser.add_argument("--coverage", action="store_true", help="Generate coverage report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Default to running all tests if no specific option provided
    if not any([args.unit, args.integration, args.file, args.pattern, args.fast, args.coverage]):
        args.all = True

    success = True

    if args.all:
        success = run_all_tests(verbose=args.verbose)

    elif args.unit:
        success = run_unit_tests(verbose=args.verbose)

    elif args.integration:
        success = run_integration_tests(verbose=args.verbose)

    elif args.file:
        success = run_specific_test_file(args.file, verbose=args.verbose)

    elif args.pattern:
        success = run_tests_with_pattern(args.pattern, verbose=args.verbose)

    elif args.fast:
        success = run_fast_tests()

    elif args.coverage:
        success = run_coverage_report()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
