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

## Job structure & ingest

Ingest and normalize JSON files with validation, creating structured job folders for story processing pipeline.

### Usage
```bash
python -m tools.ingest --input <path> --schema story|timeline --out dist/jobs --title "<override title>" [--strict|--lenient]
```

### Examples

**Valid story file with title override:**
```bash
python -m tools.ingest --input tests/story_min.json --schema story --title "Beautiful Story" --out dist/jobs --lenient
# Exit code: 0
# Output: ✓ Validation passed
#         → Normalized data written to dist/jobs/2025-01-13T15-30-45Z__beautiful-story/normalized/story.normalized.json
#         → Job created at dist/jobs/2025-01-13T15-30-45Z__beautiful-story
```

**Story with validation errors (lenient mode):**
```bash
python -m tools.ingest --input invalid_story.json --schema story --out dist/jobs --lenient
# Exit code: 0 
# Output: ✗ /title: 'title' is a required property
#         → Normalized data written to dist/jobs/2025-01-13T15-31-22Z__invalid-story/normalized/story.normalized.json
#         → Job created at dist/jobs/2025-01-13T15-31-22Z__invalid-story
```

**Story with validation errors (strict mode):**
```bash
python -m tools.ingest --input invalid_story.json --schema story --out dist/jobs --strict
# Exit code: 1
# Output: ✗ /title: 'title' is a required property  
#         → Normalized data written to dist/jobs/2025-01-13T15-32-10Z__invalid-story/normalized/story.normalized.json
#         → Job created at dist/jobs/2025-01-13T15-32-10Z__invalid-story
```

### Job Structure

Each ingest creates a timestamped job folder with structured subdirectories:

```
dist/jobs/2025-01-13T15-30-45Z__beautiful-story/
├── story_job_manifest.json     # Job metadata and file paths
├── source/
│   └── story.raw.json         # Original input data (unchanged)
├── normalized/  
│   └── story.normalized.json  # Validated data with unknown fields in _extra
└── reports/
    ├── ingest.report.json     # Machine-readable validation report
    └── ingest.report.txt      # Human-readable validation report
```

**Job ID Format:** `YYYY-MM-DDTHH-MM-SSZ__<story-slug>`
- Timestamp in UTC
- Story slug derived from title: lowercase, latin characters, dash-separated
- Unknown/special characters stripped safely

**story_job_manifest.json structure:**
```json
{
  "job_id": "2025-01-13T15-30-45Z__beautiful-story",
  "created_at": "2025-01-13T15:30:45.123Z",
  "title": "Beautiful Story", 
  "slug": "beautiful-story",
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
  "status": "draft"
}
```

**Normalization:**
- Preserves original key order from input
- Unknown fields moved to top-level `_extra` object (not dropped)
- Line breaks in text fields preserved
- Validates against existing schema via tools.validate library

### Exit Codes
- `0`: Success (or lenient mode with validation errors)
- `1`: Validation failed (strict mode) or processing error  
- `2`: URL not supported

## Assets cache & registries

Content-addressed asset management with split registries for different asset types.

### Usage

**Initialize assets cache:**
```bash
python -m tools.assets init --out dist/assets
```

**Add constant files (palettes, configs, etc.):**
```bash
python -m tools.assets add-constant --file tests/golden/palette.json --out dist/assets
```

### Asset Storage

Assets are stored with content-addressed filenames using SHA256 hashes:

```
dist/assets/
├── images/                    # Image assets (future)
├── animations/               # Animation assets (future)
├── audio/                    # Audio assets (future)
├── constants/                # JSON constants, configs, palettes
│   └── sha256_a1b2c3d4e5f6.json
└── registries/               # Split registries by asset type
    ├── images.json
    ├── animations.json
    ├── audio.json
    └── constants.json
```

### Registry Structure

Each registry maintains metadata for its asset type:

```json
{
  "version": 1,
  "updated_at": "2025-01-13T15:30:45Z",
  "items": {
    "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456": {
      "path": "constants/sha256_a1b2c3d4e5f6.json",
      "sha256": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
      "meta": {
        "name": "palette.json"
      }
    }
  }
}
```

### Key Features

- **Content-addressed storage**: Files stored by SHA256 hash, preventing duplicates
- **Split registries**: Separate JSON files for each asset type (images, audio, etc.)
- **Idempotent operations**: Running commands multiple times is safe
- **Hash-based filenames**: `sha256_<first12chars>.json` for easy identification
- **Copy-based**: Always copies files (no symlinks) for reliability

### Asset Import (Future)

Job manifests can reference cached assets by SHA256:

```json
{
  "assets": {
    "palette": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456"
  }
}
```