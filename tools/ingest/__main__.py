#!/usr/bin/env python3
import sys
import json
import argparse
import time
import re
from datetime import datetime, timezone
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


def create_story_slug(title: str) -> str:
    """Create a story slug from title: lowercase, latin, dash-separated."""
    # Convert to lowercase and normalize unicode
    slug = title.lower().strip()
    
    # Replace common unicode characters with latin equivalents
    replacements = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e', 'ж': 'zh',
        'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
        'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts',
        'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu',
        'я': 'ya', 'і': 'i', 'ї': 'i', 'є': 'e', 'ґ': 'g',
    }
    
    for cyrillic, latin in replacements.items():
        slug = slug.replace(cyrillic, latin)
    
    # Keep only alphanumeric, spaces, and basic punctuation
    slug = re.sub(r'[^\w\s-]', '', slug)
    
    # Replace spaces and multiple dashes with single dashes
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    
    # Remove leading/trailing dashes
    slug = slug.strip('-')
    
    # Limit length
    if len(slug) > 50:
        slug = slug[:50].rstrip('-')
    
    return slug or 'untitled'


def generate_job_id(title: str) -> str:
    """Generate job ID: YYYY-MM-DDTHH-MM-SSZ__<story-slug>"""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    slug = create_story_slug(title)
    return f"{timestamp}__{slug}"


def normalize_object_with_extra(obj: Any, schema: Dict[str, Any], preserve_order: bool = True) -> Any:
    """Normalize object by moving unknown fields to _extra and preserving known fields."""
    if not isinstance(obj, dict):
        return obj
    
    if "properties" not in schema:
        return obj
    
    normalized = {}
    extra = {}
    schema_props = schema["properties"]
    
    # Get original key order if preserving
    keys_to_process = list(obj.keys()) if preserve_order else sorted(obj.keys())
    
    # Process all keys
    for key in keys_to_process:
        value = obj[key]
        
        if key in schema_props:
            # Known field - normalize recursively
            prop_schema = schema_props[key]
            
            if prop_schema.get("type") == "object":
                normalized[key] = normalize_object_with_extra(value, prop_schema, preserve_order)
            elif prop_schema.get("type") == "array" and "items" in prop_schema:
                items_schema = prop_schema["items"]
                if isinstance(value, list) and items_schema.get("type") == "object":
                    normalized[key] = [normalize_object_with_extra(item, items_schema, preserve_order) for item in value]
                else:
                    normalized[key] = value
            else:
                normalized[key] = value
        else:
            # Unknown field - move to _extra
            extra[key] = value
    
    # Add _extra if there are unknown fields
    if extra:
        normalized["_extra"] = extra
    
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


def create_job_manifest(job_id: str, title: str, slug: str, status: str) -> Dict[str, Any]:
    """Create job manifest data structure."""
    return {
        "job_id": job_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": title,
        "slug": slug,
        "paths": {
            "source_story": "source/story.raw.json",
            "story": "normalized/story.normalized.json", 
            "tts_lines": "tts/tts_lines.json",
            "audio_manifest": "tts/audio/audio_manifest.json",
            "storyboard": "visual/storyboard.json",
            "asset_manifest": "visual/asset_manifest.json",
            "timeline": "timeline/timeline.json",
            "ffmpeg_script": "timeline/ffmpeg_script.txt",
            "video": "video/final.mp4"
        },
        "status": status
    }


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
    parser.add_argument("--input", required=True, help="Path to input file")
    parser.add_argument("--schema", required=True, choices=["story", "timeline"], 
                       help="Schema to validate against")
    parser.add_argument("--out", default="dist/jobs", help="Output directory")
    parser.add_argument("--title", help="Override title for job ID generation")
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
    
    # Check if input is URL
    if is_url(args.input):
        console.print("[red]URL not supported yet[/red]")
        sys.exit(2)
    
    input_path = Path(args.input)
    if not input_path.exists():
        console.print(f"[red]Input file not found: {input_path}[/red]")
        sys.exit(1)
    
    errors = []
    status = "draft"
    
    try:
        # Load input data first to get title
        data = load_json(input_path)
        
        # Determine title for job ID
        title = args.title
        if not title and isinstance(data, dict) and "title" in data:
            title = str(data["title"])
        if not title:
            title = input_path.stem
        
        # Generate job ID and create directory structure
        job_id = generate_job_id(title)
        slug = create_story_slug(title)
        
        output_dir = Path(args.out) / job_id
        source_dir = output_dir / "source"
        normalized_dir = output_dir / "normalized"  
        reports_dir = output_dir / "reports"
        
        # Create all directories
        for dir_path in [source_dir, normalized_dir, reports_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Save raw input data
        raw_path = source_dir / "story.raw.json"
        with open(raw_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Load schema
        schema_path = get_schema_path(args.schema)
        if not schema_path.exists():
            console.print(f"[red]Schema not found: {schema_path}[/red]")
            sys.exit(1)
        
        schema = load_json(schema_path)
        
        # Validate data
        validation_errors = validate_data(data, schema, strict_mode)
        errors.extend(validation_errors)
        
        if validation_errors:
            status = "failed"
            for error in validation_errors:
                console.print(f"[red]✗[/red] {error}")
        else:
            console.print(f"[green]✓[/green] Validation passed")
        
        # Normalize data (preserve original key order and move unknown fields to _extra)
        normalized_data = normalize_object_with_extra(data, schema, preserve_order=True)
        
        # Write normalized data
        normalized_path = normalized_dir / "story.normalized.json"
        with open(normalized_path, 'w', encoding='utf-8') as f:
            json.dump(normalized_data, f, indent=2, ensure_ascii=False)
        
        console.print(f"[blue]→[/blue] Normalized data written to {normalized_path}")
        
    except Exception as e:
        errors.append(str(e))
        status = "failed"
        console.print(f"[red]Error: {e}[/red]")
    
    end_time = time.time()
    
    try:
        # Create job manifest
        manifest = create_job_manifest(job_id, title, slug, status)
        manifest_path = output_dir / "story_job_manifest.json"
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        # Generate reports
        report = create_report(job_id, input_path, args.schema, status, errors, 
                              start_time, end_time, strict_mode)
        
        # Write JSON report
        report_json_path = reports_dir / "ingest.report.json"
        with open(report_json_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # Write text report
        report_txt_path = reports_dir / "ingest.report.txt"
        write_report_txt(report, report_txt_path)
        
        console.print(f"[blue]→[/blue] Job created at {output_dir}")
        
    except Exception as e:
        console.print(f"[red]Error creating job files: {e}[/red]")
        sys.exit(1)
    
    # Exit with appropriate code
    if status == "failed" and strict_mode:
        sys.exit(1)
    elif status == "failed":
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()