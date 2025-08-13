# Petrovich

## Install

```bash
pip install -e .
```

## Validate

Validate a single JSON file against its schema:
```bash
python -m tools.validate shared/schemas/story_schema.json tests/story_min.json
```

Validate a timeline file:
```bash
python -m tools.validate shared/schemas/timeline_schema.json tests/golden/timeline.json
```

Run all validations:
```bash
python scripts/validate_all.py
```

## Ingest

Ingest and normalize JSON files with validation:

### Usage
```bash
python -m tools.ingest --input <path_or_url> --schema story|timeline --out dist/ingest [--strict|--lenient]
```

### Examples

**Valid story file (strict mode - default):**
```bash
python -m tools.ingest --input tests/story_min.json --schema story --out dist/ingest --strict
# Exit code: 0
# Output: ✓ Validation passed
#         → Normalized data written to dist/ingest/<job-id>/story_min.normalized.json
#         → Reports written to dist/ingest/<job-id>
```

**Invalid file (strict mode):**
```bash
python -m tools.ingest --input invalid_story.json --schema story --out dist/ingest --strict
# Exit code: 1
# Output: ✗ /title: 'title' is a required property
#         → Normalized data written to dist/ingest/<job-id>/invalid_story.normalized.json
#         → Reports written to dist/ingest/<job-id>
```

**Invalid file (lenient mode):**
```bash
python -m tools.ingest --input invalid_story.json --schema story --out dist/ingest --lenient
# Exit code: 0
# Output: ✗ /title: 'title' is a required property
#         → Normalized data written to dist/ingest/<job-id>/invalid_story.normalized.json
#         → Reports written to dist/ingest/<job-id>
```

**Timeline file:**
```bash
python -m tools.ingest --input tests/golden/timeline.json --schema timeline --out dist/ingest
```

**URL input (not yet supported):**
```bash
python -m tools.ingest --input https://example.com/story.json --schema story --out dist/ingest
# Exit code: 2
# Output: URL not supported yet
```

### Output Structure

For each ingest job, the following files are created in `dist/ingest/<job-id>/`:

```
dist/ingest/<job-id>/
├── <basename>.normalized.json  # Normalized data (unknown fields removed, stable key order)
├── report.json                 # Machine-readable report
└── report.txt                  # Human-readable report
```

**report.json structure:**
```json
{
  "job_id": "a1b2c3d4",
  "status": "success|validation_failed|error",
  "input": "/path/to/input.json",
  "schema": "story",
  "mode": "strict|lenient",
  "errors": ["JSON pointer: error message"],
  "timing": {
    "start_time": 1640995200.123,
    "end_time": 1640995200.456,
    "duration_sec": 0.333
  }
}
```

### Exit Codes
- `0`: Success (or lenient mode with validation errors)
- `1`: Validation failed (strict mode) or processing error
- `2`: URL not supported