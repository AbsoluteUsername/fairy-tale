#!/usr/bin/env python3
"""Validate all JSON data files against their schemas."""

import sys
from pathlib import Path
from subprocess import run, PIPE

# Define validation pairs: (schema_path, data_files)
VALIDATIONS = [
    ("shared/schemas/story_schema.json", [
        "tests/story_min.json",
        "tests/story_full.json"
    ]),
    ("shared/schemas/timeline_schema.json", [
        "tests/golden/timeline.json"
    ]),
]


def validate_file(schema_path: str, data_path: str) -> bool:
    """Run validation for a single file pair."""
    result = run([
        sys.executable, "-m", "tools.validate",
        schema_path, data_path
    ], capture_output=True, text=True)
    
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    
    return result.returncode == 0


def main():
    """Run all validations."""
    project_root = Path(__file__).parent.parent
    failed = 0
    total = 0
    
    for schema_path, data_files in VALIDATIONS:
        for data_file in data_files:
            total += 1
            schema_full = project_root / schema_path
            data_full = project_root / data_file
            
            if not schema_full.exists():
                print(f"Schema not found: {schema_path}")
                failed += 1
                continue
                
            if not data_full.exists():
                print(f"Data file not found: {data_file}")
                failed += 1
                continue
            
            if not validate_file(str(schema_full), str(data_full)):
                failed += 1
    
    print(f"\nValidation complete: {total - failed}/{total} passed")
    
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()