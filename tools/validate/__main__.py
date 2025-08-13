#!/usr/bin/env python3
import sys
import json
import argparse
from pathlib import Path
from typing import Any, Dict

import jsonschema
from rich.console import Console


def load_json(path: Path) -> Dict[str, Any]:
    """Load and parse JSON file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        console = Console()
        console.print(f"[red]Error loading {path}: {e}[/red]")
        sys.exit(1)


def validate_json(schema_path: Path, data_path: Path) -> bool:
    """Validate JSON data against schema."""
    console = Console()
    
    schema = load_json(schema_path)
    data = load_json(data_path)
    
    try:
        jsonschema.validate(data, schema)
        console.print(f"[green]✓[/green] {data_path} is valid")
        return True
    except jsonschema.ValidationError as e:
        # Format error with JSON pointer path
        path = "/" + "/".join(str(p) for p in e.absolute_path) if e.absolute_path else "/"
        
        console.print(f"[red]✗[/red] {data_path} is invalid")
        console.print(f"[yellow]Path:[/yellow] {path}")
        console.print(f"[yellow]Error:[/yellow] {e.message}")
        
        if e.context:
            console.print(f"[dim]Additional context:[/dim]")
            for ctx in e.context[:3]:  # Show max 3 context errors
                ctx_path = "/" + "/".join(str(p) for p in ctx.absolute_path) if ctx.absolute_path else "/"
                console.print(f"  {ctx_path}: {ctx.message}")
        
        return False
    except jsonschema.SchemaError as e:
        console.print(f"[red]Schema error in {schema_path}: {e.message}[/red]")
        return False


def main():
    parser = argparse.ArgumentParser(description="Validate JSON data against a schema")
    parser.add_argument("schema", type=Path, help="Path to JSON schema file")
    parser.add_argument("data", type=Path, help="Path to JSON data file")
    
    args = parser.parse_args()
    
    if not args.schema.exists():
        print(f"Schema file not found: {args.schema}", file=sys.stderr)
        sys.exit(1)
    
    if not args.data.exists():
        print(f"Data file not found: {args.data}", file=sys.stderr)
        sys.exit(1)
    
    is_valid = validate_json(args.schema, args.data)
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()