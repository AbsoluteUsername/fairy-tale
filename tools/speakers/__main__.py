#!/usr/bin/env python3
import sys
import json
import argparse
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Set


def get_current_timestamp() -> str:
    """Get current timestamp in ISO8601 format with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def load_registry(registry_path: Path) -> Dict[str, Any]:
    """Load registry JSON file or create empty structure."""
    if registry_path.exists():
        try:
            with open(registry_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    
    return {}


def save_registry(registry_path: Path, registry: Dict[str, Any]) -> None:
    """Save registry to JSON file."""
    registry["updated_at"] = get_current_timestamp()
    with open(registry_path, 'w', encoding='utf-8') as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)


def init_speakers_registries(output_dir: Path) -> None:
    """Initialize speakers registries."""
    registries_dir = output_dir / "registries"
    registries_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize speakers.json
    speakers_path = registries_dir / "speakers.json"
    if not speakers_path.exists():
        speakers_registry = {
            "version": 1,
            "updated_at": get_current_timestamp(),
            "items": {
                "narrator": {
                    "display_name": "Оповідач",
                    "default_voice": "voice_narrator",
                    "lang": "uk",
                    "pitch": 0,
                    "rate": 1.0,
                    "style": "calm"
                }
            }
        }
        save_registry(speakers_path, speakers_registry)
        print(f"Initialized speakers registry: {speakers_path}")
    else:
        print(f"Speakers registry already exists: {speakers_path}")
    
    # Initialize speaker_name_map.json
    name_map_path = registries_dir / "speaker_name_map.json"
    if not name_map_path.exists():
        name_map_registry = {
            "version": 1,
            "updated_at": get_current_timestamp(),
            "patterns": [],
            "fallback": "narrator"
        }
        save_registry(name_map_path, name_map_registry)
        print(f"Initialized speaker name map: {name_map_path}")
    else:
        print(f"Speaker name map already exists: {name_map_path}")
    
    print("Speakers registries initialization complete")


def add_speaker(output_dir: Path, speaker_id: str, display_name: str, voice: str,
               lang: str = "uk", pitch: int = 0, rate: float = 1.0, style: str = "calm") -> None:
    """Add or update a speaker in the registry."""
    registries_dir = output_dir / "registries"
    speakers_path = registries_dir / "speakers.json"
    
    if not speakers_path.exists():
        print("Error: Speakers registry not found. Run 'init' command first.")
        sys.exit(1)
    
    # Load existing registry
    registry = load_registry(speakers_path)
    if "items" not in registry:
        registry["items"] = {}
        registry["version"] = 1
    
    # Add or update speaker
    registry["items"][speaker_id] = {
        "display_name": display_name,
        "default_voice": voice,
        "lang": lang,
        "pitch": pitch,
        "rate": rate,
        "style": style
    }
    
    save_registry(speakers_path, registry)
    print(f"Added/updated speaker '{speaker_id}': {display_name}")


def link_voice(output_dir: Path, speaker_id: str, voice: str) -> None:
    """Update the default voice for a speaker."""
    registries_dir = output_dir / "registries"
    speakers_path = registries_dir / "speakers.json"
    
    if not speakers_path.exists():
        print("Error: Speakers registry not found. Run 'init' command first.")
        sys.exit(1)
    
    registry = load_registry(speakers_path)
    
    if "items" not in registry or speaker_id not in registry["items"]:
        print(f"Error: Speaker '{speaker_id}' not found in registry.")
        sys.exit(1)
    
    registry["items"][speaker_id]["default_voice"] = voice
    
    save_registry(speakers_path, registry)
    print(f"Updated voice for speaker '{speaker_id}': {voice}")


def extract_speakers_from_story(story_path: Path) -> Set[str]:
    """Extract speaker names from normalized story JSON."""
    try:
        with open(story_path, 'r', encoding='utf-8') as f:
            story = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error loading story: {e}")
        sys.exit(1)
    
    speakers = set()
    
    # Extract from dialogue
    if "scenes" in story:
        for scene in story["scenes"]:
            if "dialogue" in scene:
                for line in scene["dialogue"]:
                    if "speaker" in line:
                        speakers.add(line["speaker"])
    
    # Extract from text using Ukrainian speech verbs
    ukrainian_speech_verbs = [
        r"сказав", r"сказала", r"каже", r"мовив", r"мовила",
        r"промовив", r"промовила", r"відповів", r"відповіла",
        r"прошепотів", r"прошепотіла", r"вигукнув", r"вигукнула"
    ]
    
    verb_pattern = r"(?:" + "|".join(ukrainian_speech_verbs) + r")"
    
    def extract_from_text(text: str) -> Set[str]:
        names = set()
        # Look for patterns like "Ліна сказала" or "сказав Петро"
        patterns = [
            rf"(\w+)\s+{verb_pattern}",  # "Name said"
            rf"{verb_pattern}\s+(\w+)"   # "said Name"
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            names.update(matches)
        
        return names
    
    # Scan all text content
    if "scenes" in story:
        for scene in story["scenes"]:
            # Check dialogue text
            if "dialogue" in scene:
                for line in scene["dialogue"]:
                    if "text" in line:
                        speakers.update(extract_from_text(line["text"]))
            
            # Check scene summary and visual notes
            for field in ["summary", "visual_notes"]:
                if field in scene:
                    speakers.update(extract_from_text(scene[field]))
    
    return speakers


def suggest_missing(output_dir: Path, story_path: Path) -> None:
    """Suggest missing speakers and mappings from a story."""
    registries_dir = output_dir / "registries"
    speakers_path = registries_dir / "speakers.json"
    name_map_path = registries_dir / "speaker_name_map.json"
    
    # Load registries
    speakers_registry = load_registry(speakers_path)
    name_map_registry = load_registry(name_map_path)
    
    existing_speakers = set(speakers_registry.get("items", {}).keys())
    patterns = name_map_registry.get("patterns", [])
    
    # Extract speakers from story
    story_speakers = extract_speakers_from_story(story_path)
    
    # Find missing speakers
    missing_speakers = []
    missing_patterns = []
    
    for speaker in story_speakers:
        # Check if speaker ID exists in registry
        if speaker not in existing_speakers:
            missing_speakers.append(speaker)
        
        # Check if speaker is covered by name mapping patterns
        covered = False
        for pattern_entry in patterns:
            if "pattern" in pattern_entry:
                try:
                    if re.search(pattern_entry["pattern"], speaker, re.IGNORECASE):
                        covered = True
                        break
                except re.error:
                    continue
        
        if not covered and speaker not in [p.get("speaker") for p in patterns]:
            missing_patterns.append(speaker)
    
    # Output suggestions
    if missing_speakers:
        print("# Missing speaker IDs (add to speakers registry):")
        for speaker in sorted(missing_speakers):
            print(speaker)
    
    if missing_patterns:
        print("# Missing name mappings (add patterns):")
        for name in sorted(missing_patterns):
            print(name)
    
    if not missing_speakers and not missing_patterns:
        print("# All speakers and names are covered")


def add_map_pattern(output_dir: Path, pattern: str, speaker_id: str) -> None:
    """Add a pattern to speaker name map."""
    registries_dir = output_dir / "registries"
    name_map_path = registries_dir / "speaker_name_map.json"
    
    if not name_map_path.exists():
        print("Error: Speaker name map not found. Run 'init' command first.")
        sys.exit(1)
    
    registry = load_registry(name_map_path)
    if "patterns" not in registry:
        registry["patterns"] = []
        registry["version"] = 1
    
    # Add new pattern
    new_pattern = {
        "pattern": pattern,
        "speaker": speaker_id
    }
    
    registry["patterns"].append(new_pattern)
    
    save_registry(name_map_path, registry)
    print(f"Added mapping pattern: '{pattern}' → '{speaker_id}'")


def main():
    parser = argparse.ArgumentParser(description="Manage speakers registry and name mappings")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize speakers registries")
    init_parser.add_argument("--out", required=True, help="Assets directory")
    
    # Add speaker command
    add_parser = subparsers.add_parser("add", help="Add or update a speaker")
    add_parser.add_argument("--id", required=True, help="Speaker ID")
    add_parser.add_argument("--display", required=True, help="Display name")
    add_parser.add_argument("--voice", required=True, help="Default voice")
    add_parser.add_argument("--lang", default="uk", help="Language (default: uk)")
    add_parser.add_argument("--pitch", type=int, default=0, help="Pitch (default: 0)")
    add_parser.add_argument("--rate", type=float, default=1.0, help="Rate (default: 1.0)")
    add_parser.add_argument("--style", default="calm", help="Style (default: calm)")
    add_parser.add_argument("--out", required=True, help="Assets directory")
    
    # Link voice command
    link_parser = subparsers.add_parser("link-voice", help="Update speaker's default voice")
    link_parser.add_argument("--id", required=True, help="Speaker ID")
    link_parser.add_argument("--voice", required=True, help="Default voice")
    link_parser.add_argument("--out", required=True, help="Assets directory")
    
    # Suggest missing command
    suggest_parser = subparsers.add_parser("suggest-missing", help="Suggest missing speakers and mappings")
    suggest_parser.add_argument("--in", dest="input_file", required=True, help="Path to normalized story JSON")
    suggest_parser.add_argument("--out", required=True, help="Assets directory")
    
    # Add map pattern command
    pattern_parser = subparsers.add_parser("add-map-pattern", help="Add name mapping pattern")
    pattern_parser.add_argument("--pattern", required=True, help="Regex pattern")
    pattern_parser.add_argument("--speaker", required=True, help="Speaker ID")
    pattern_parser.add_argument("--out", required=True, help="Assets directory")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    output_dir = Path(args.out)
    
    if args.command == "init":
        init_speakers_registries(output_dir)
    elif args.command == "add":
        add_speaker(output_dir, args.id, args.display, args.voice,
                   args.lang, args.pitch, args.rate, args.style)
    elif args.command == "link-voice":
        link_voice(output_dir, args.id, args.voice)
    elif args.command == "suggest-missing":
        story_path = Path(args.input_file)
        suggest_missing(output_dir, story_path)
    elif args.command == "add-map-pattern":
        add_map_pattern(output_dir, args.pattern, args.speaker)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()