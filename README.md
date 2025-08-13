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