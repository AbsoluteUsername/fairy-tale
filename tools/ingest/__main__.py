#!/usr/bin/env python3
import sys
import json
import argparse
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

import jsonschema
from rich.console import Console


def is_url(path_str: str) -> bool:
    """Check if string is a URL."""
    try:
        result = urlparse(path_str)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def load_json(path: Path) -> Dict[str, Any]:
    """Load and parse JSON file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        raise ValueError(f"Error loading {path}: {e}")


def get_schema_path(schema_name: str) -> Path:
    """Get path to schema file."""
    base_path = Path(__file__).parent.parent.parent / "shared" / "schemas"
    schema_file = f"{schema_name}_schema.json"
    return base_path / schema_file


def extract_schema_fields(schema: Dict[str, Any], path: str = "") -> Set[str]:
    """Extract all valid field paths from a JSON schema."""
    fields = set()
    
    if "properties" in schema:
        for prop, prop_schema in schema["properties"].items():
            current_path = f"{path}.{prop}" if path else prop
            fields.add(current_path)
            
            if prop_schema.get("type") == "object":
                fields.update(extract_schema_fields(prop_schema, current_path))
            elif prop_schema.get("type") == "array" and "items" in prop_schema:
                items_schema = prop_schema["items"]
                if items_schema.get("type") == "object":
                    array_fields = extract_schema_fields(items_schema, current_path + "[]")
                    fields.update(array_fields)
    
    return fields


def normalize_object(obj: Any, schema: Dict[str, Any], path: str = "") -> Any:
    """Normalize object by removing unknown fields and sorting keys."""
    if not isinstance(obj, dict):
        return obj
    
    if "properties" not in schema:
        return obj
    
    normalized = {}
    
    # Process properties in schema order for consistent output
    for prop in sorted(schema["properties"].keys()):
        if prop in obj:
            prop_schema = schema["properties"][prop]
            value = obj[prop]
            
            if prop_schema.get("type") == "object":
                normalized[prop] = normalize_object(value, prop_schema, f"{path}.{prop}" if path else prop)
            elif prop_schema.get("type") == "array" and "items" in prop_schema:
                items_schema = prop_schema["items"]
                if isinstance(value, list):
                    if items_schema.get("type") == "object":
                        normalized[prop] = [normalize_object(item, items_schema, f"{path}.{prop}[]" if path else f"{prop}[]") for item in value]
                    else:
                        normalized[prop] = value
                else:
                    normalized[prop] = value
            else:
                normalized[prop] = value
    
    return normalized


def validate_data(data: Dict[str, Any], schema: Dict[str, Any], strict: bool = True) -> List[str]:
    """Validate JSON data against schema and return list of errors."""
    errors = []
    
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as e:
        path = "/" + "/".join(str(p) for p in e.absolute_path) if e.absolute_path else "/"
        errors.append(f"{path}: {e.message}")
        
        if e.context:
            for ctx in e.context[:5]:  # Limit context errors
                ctx_path = "/" + "/".join(str(p) for p in ctx.absolute_path) if ctx.absolute_path else "/"
                errors.append(f"{ctx_path}: {ctx.message}")
    except jsonschema.SchemaError as e:
        errors.append(f"Schema error: {e.message}")
    
    return errors


def create_report(job_id: str, input_path: Path, schema_name: str, status: str, 
                 errors: List[str], start_time: float, end_time: float,
                 strict: bool) -> Dict[str, Any]:
    """Create report data structure."""
    return {
        "job_id": job_id,
        "status": status,
        "input": str(input_path),
        "schema": schema_name,
        "mode": "strict" if strict else "lenient",
        "errors": errors,
        "timing": {
            "start_time": start_time,
            "end_time": end_time,
            "duration_sec": round(end_time - start_time, 3)
        }
    }


def write_report_txt(report: Dict[str, Any], output_path: Path):
    """Write human-readable report."""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"Job ID: {report['job_id']}\n")
        f.write(f"Status: {report['status']}\n")
        f.write(f"Input: {report['input']}\n")
        f.write(f"Schema: {report['schema']}\n")
        f.write(f"Mode: {report['mode']}\n")
        f.write(f"Duration: {report['timing']['duration_sec']}s\n")
        
        if report['errors']:
            f.write(f"\nErrors ({len(report['errors'])}):\n")
            for error in report['errors']:
                f.write(f"  {error}\n")
        else:
            f.write("\nNo errors found.\n")


def main():
    parser = argparse.ArgumentParser(description="Ingest and validate JSON data")
    parser.add_argument("--input", required=True, help="Path to input file or URL")
    parser.add_argument("--schema", required=True, choices=["story", "timeline"], 
                       help="Schema to validate against")
    parser.add_argument("--out", default="dist/ingest", help="Output directory")
    parser.add_argument("--strict", action="store_true", 
                       help="Strict mode (exit on validation errors)")
    parser.add_argument("--lenient", action="store_true",
                       help="Lenient mode (continue despite validation errors)")
    
    args = parser.parse_args()
    console = Console()
    
    # Check for conflicting flags
    if args.strict and args.lenient:
        console.print("[red]Error: Cannot specify both --strict and --lenient[/red]")
        sys.exit(1)
    
    # Default to strict mode if neither specified
    strict_mode = not args.lenient
    
    start_time = time.time()
    job_id = str(uuid.uuid4())[:8]
    
    # Check if input is URL
    if is_url(args.input):
        console.print("[red]URL not supported yet[/red]")
        sys.exit(2)
    
    input_path = Path(args.input)
    if not input_path.exists():
        console.print(f"[red]Input file not found: {input_path}[/red]")
        sys.exit(1)
    
    # Create output directory
    output_dir = Path(args.out) / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    errors = []
    status = "success"
    
    try:
        # Load schema
        schema_path = get_schema_path(args.schema)
        if not schema_path.exists():
            console.print(f"[red]Schema not found: {schema_path}[/red]")
            sys.exit(1)
        
        schema = load_json(schema_path)
        
        # Load input data
        data = load_json(input_path)
        
        # Validate data
        validation_errors = validate_data(data, schema, strict_mode)
        errors.extend(validation_errors)
        
        if validation_errors:
            status = "validation_failed"
            for error in validation_errors:
                console.print(f"[red]✗[/red] {error}")
        else:
            console.print(f"[green]✓[/green] Validation passed")
        
        # Normalize data
        normalized_data = normalize_object(data, schema)
        
        # Write normalized data
        basename = input_path.stem
        normalized_path = output_dir / f"{basename}.normalized.json"
        with open(normalized_path, 'w', encoding='utf-8') as f:
            json.dump(normalized_data, f, indent=2, ensure_ascii=False, sort_keys=True)
        
        console.print(f"[blue]→[/blue] Normalized data written to {normalized_path}")
        
    except Exception as e:
        errors.append(str(e))
        status = "error"
        console.print(f"[red]Error: {e}[/red]")
    
    end_time = time.time()
    
    # Generate reports
    report = create_report(job_id, input_path, args.schema, status, errors, 
                          start_time, end_time, strict_mode)
    
    # Write JSON report
    report_json_path = output_dir / "report.json"
    with open(report_json_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # Write text report
    report_txt_path = output_dir / "report.txt"
    write_report_txt(report, report_txt_path)
    
    console.print(f"[blue]→[/blue] Reports written to {output_dir}")
    
    # Exit with appropriate code
    if status == "validation_failed" and strict_mode:
        sys.exit(1)
    elif status == "error":
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()