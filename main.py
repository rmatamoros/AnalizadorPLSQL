#!/usr/bin/env python3
"""
PL/SQL Standards Analyzer - Main Entry Point.

Usage:
    python main.py <file.sql>              Analyze a PL/SQL file
    python main.py <file.sql> --verbose    Show detailed tool output
    python main.py --demo                  Run with the included example file
    python main.py --help                  Show this help message

Environment:
    ANTHROPIC_API_KEY  Required. Your Anthropic API key.

Example:
    export ANTHROPIC_API_KEY="sk-ant-..."
    python main.py examples/sample.sql
    python main.py examples/sample_bad.sql --verbose
"""

import sys
import os
from plsql_analyzer.agent import analyze_file, analyze_plsql_code


def print_help():
    print(__doc__)


def main():
    args = sys.argv[1:]

    if not args or "--help" in args or "-h" in args:
        print_help()
        sys.exit(0)

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable is not set.")
        print("Please set it with: export ANTHROPIC_API_KEY='your-key-here'")
        sys.exit(1)

    verbose = "--verbose" in args or "-v" in args
    args = [a for a in args if not a.startswith("-")]

    if "--demo" in sys.argv:
        demo_file = os.path.join(os.path.dirname(__file__), "examples", "sample_bad.sql")
        if not os.path.exists(demo_file):
            demo_file = os.path.join(os.path.dirname(__file__), "examples", "sample.sql")
        print(f"Running demo analysis on: {demo_file}\n")
        file_path = demo_file
    elif args:
        file_path = args[0]
    else:
        print("Error: Please provide a PL/SQL file to analyze.")
        print_help()
        sys.exit(1)

    print(f"Analyzing: {file_path}")
    print("=" * 60)

    report = analyze_file(file_path, verbose=verbose)

    print("\n" + "=" * 60)
    print("COMPLIANCE REPORT")
    print("=" * 60)
    print(report)

    # Save report to file
    report_file = file_path.rsplit(".", 1)[0] + "_report.txt"
    try:
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(f"PL/SQL Standards Compliance Report\n")
            f.write(f"File: {file_path}\n")
            f.write("=" * 60 + "\n\n")
            f.write(report)
        print(f"\nReport saved to: {report_file}")
    except Exception as e:
        print(f"\nCould not save report: {e}")


if __name__ == "__main__":
    main()
