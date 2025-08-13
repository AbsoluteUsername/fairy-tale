#!/usr/bin/env python3
import sys
import json
import argparse
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional


def load_json(path: Path) -> Dict[str, Any]:
    """Load and parse JSON file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        raise ValueError(f"Error loading {path}: {e}")


def load_speaker_registries(assets_dir: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Load speaker registries from assets directory."""
    registries_dir = assets_dir / "registries"
    
    speakers_path = registries_dir / "speakers.json"
    name_map_path = registries_dir / "speaker_name_map.json"
    
    speakers = {}
    name_map = {"patterns": [], "fallback": "narrator"}
    
    if speakers_path.exists():
        try:
            speakers = load_json(speakers_path)
        except ValueError:
            print(f"Warning: Could not load speakers registry from {speakers_path}")
    
    if name_map_path.exists():
        try:
            name_map = load_json(name_map_path)
        except ValueError:
            print(f"Warning: Could not load speaker name map from {name_map_path}")
    
    return speakers, name_map


def canonicalize_speaker(raw_speaker: str, speakers_registry: Dict[str, Any], 
                        name_map: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """
    Canonicalize a speaker name/id using registries.
    Returns (canonical_speaker, unresolved_name_or_none).
    """
    # Check if raw speaker is already a canonical ID in speakers registry
    if "items" in speakers_registry and raw_speaker in speakers_registry["items"]:
        return raw_speaker, None
    
    # Try name mapping patterns
    for pattern_entry in name_map.get("patterns", []):
        if "pattern" in pattern_entry and "speaker" in pattern_entry:
            try:
                if re.search(pattern_entry["pattern"], raw_speaker, re.IGNORECASE):
                    return pattern_entry["speaker"], None
            except re.error:
                continue
    
    # Use fallback and track as unresolved
    fallback = name_map.get("fallback", "narrator")
    return fallback, raw_speaker


def extract_quotes(text: str) -> List[Tuple[str, str]]:
    """
    Extract quoted speech from text.
    Returns list of (quote_content, speaker_name) tuples.
    """
    quotes = []
    
    # Ukrainian speech verb patterns
    ukrainian_speech_verbs = [
        r"сказав", r"сказала", r"каже", r"мовив", r"мовила",
        r"промовив", r"промовила", r"відповів", r"відповіла", 
        r"прошепотів", r"прошепотіла", r"вигукнув", r"вигукнула"
    ]
    
    verb_pattern = r"(?:" + "|".join(ukrainian_speech_verbs) + r")"
    
    # Pattern for quotes with attribution
    # Examples: "Ого!" сказала Ліна or Ліна сказала: "Ого!"
    patterns = [
        rf'"([^"]+)"\s*,?\s*{verb_pattern}\s+([А-ЯІЇЄҐ][а-яіїєґ]+)',  # "Quote" said Name
        rf'([А-ЯІЇЄҐ][а-яіїєґ]+)(?:\s+[а-яіїєґ]+)*?\s+{verb_pattern}\s*:?\s*"([^"]+)"',   # Name (words) said: "Quote"
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if len(match) == 2:
                # For both patterns: first capture is speaker, second is quote content
                speaker_name, quote_content = match[0], match[1]
                quotes.append((quote_content.strip(), speaker_name.strip()))
    
    return quotes


def split_text_and_quotes(text: str, max_chars: int = 220) -> List[Tuple[str, Optional[str]]]:
    """
    Split text into chunks, separating quotes from narration.
    Returns list of (text_chunk, speaker_or_none) tuples.
    """
    chunks = []
    
    # Extract all quotes first
    quotes = extract_quotes(text)
    
    # If no quotes, return the whole text as narration
    if not quotes:
        # Split long text into chunks
        if len(text) <= max_chars:
            chunks.append((text, None))
        else:
            words = text.split()
            current_chunk = []
            current_length = 0
            
            for word in words:
                word_length = len(word) + (1 if current_chunk else 0)  # +1 for space
                
                if current_length + word_length > max_chars and current_chunk:
                    chunks.append((" ".join(current_chunk), None))
                    current_chunk = [word]
                    current_length = len(word)
                else:
                    current_chunk.append(word)
                    current_length += word_length
            
            if current_chunk:
                chunks.append((" ".join(current_chunk), None))
        
        return chunks
    
    # Process text with quotes - work through each quote sequentially
    remaining_text = text
    
    for quote_content, speaker_name in quotes:
        # Find the full quote attribution pattern in the text
        ukrainian_speech_verbs = [
            r"сказав", r"сказала", r"каже", r"мовив", r"мовила",
            r"промовив", r"промовила", r"відповів", r"відповіла", 
            r"прошепотів", r"прошепотіла", r"вигукнув", r"вигукнула"
        ]
        
        verb_pattern = r"(?:" + "|".join(ukrainian_speech_verbs) + r")"
        
        # Look for the full quote pattern: Name verb: "Quote"
        full_quote_pattern = rf'{re.escape(speaker_name)}\s+{verb_pattern}\s*:?\s*"[^"]*{re.escape(quote_content)}[^"]*"'
        quote_match = re.search(full_quote_pattern, remaining_text, re.IGNORECASE)
        
        if quote_match:
            # Add text before the quote as narration
            before_quote = remaining_text[:quote_match.start()].strip()
            if before_quote:
                # Clean up punctuation if it ends with comma/and
                before_quote = re.sub(r',?\s*і\s*$', '', before_quote).strip()
                chunks.append((before_quote, None))
            
            # Add the quote content with speaker
            chunks.append((quote_content, speaker_name))
            
            # Continue with text after the quote
            remaining_text = remaining_text[quote_match.end():].strip()
    
    # Add any remaining text as narration
    if remaining_text.strip():
        chunks.append((remaining_text.strip(), None))
    
    return chunks


def generate_tts_lines(story: Dict[str, Any], speakers_registry: Dict[str, Any], 
                      name_map: Dict[str, Any], max_chars: int = 220,
                      enforce_known: bool = False) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Generate TTS lines from story with speaker canonicalization.
    Returns (lines, unresolved_speakers).
    """
    lines = []
    unresolved_speakers = []
    line_counter = 1
    
    if "scenes" not in story:
        return lines, unresolved_speakers
    
    for scene in story["scenes"]:
        scene_id = scene.get("id", "unknown")
        
        if "dialogue" not in scene:
            continue
            
        for dialogue_item in scene["dialogue"]:
            speaker = dialogue_item.get("speaker", "narrator")
            text = dialogue_item.get("text", "")
            
            if not text.strip():
                continue
            
            # Canonicalize the main speaker
            canonical_speaker, unresolved_speaker = canonicalize_speaker(
                speaker, speakers_registry, name_map
            )
            
            if unresolved_speaker:
                unresolved_speakers.append(f"Speaker ID: {unresolved_speaker}")
            
            # Split text and handle quotes
            text_chunks = split_text_and_quotes(text, max_chars)
            
            for chunk_text, quote_speaker in text_chunks:
                if not chunk_text.strip():
                    continue
                
                # Determine final speaker
                final_speaker = canonical_speaker
                
                if quote_speaker:
                    # This is a quoted part - canonicalize the quote speaker
                    quote_canonical, quote_unresolved = canonicalize_speaker(
                        quote_speaker, speakers_registry, name_map
                    )
                    final_speaker = quote_canonical
                    
                    if quote_unresolved:
                        unresolved_speakers.append(f"Speaker name: {quote_unresolved}")
                
                # Create TTS line (schema compliant)
                line = {
                    "id": f"{scene_id}_{line_counter:03d}",
                    "text": chunk_text.strip(),
                    "speaker": final_speaker
                }
                
                lines.append(line)
                line_counter += 1
    
    return lines, list(set(unresolved_speakers))  # Remove duplicates


def main():
    parser = argparse.ArgumentParser(description="Generate TTS lines from story JSON")
    parser.add_argument("--input", required=True, help="Path to story JSON file")
    parser.add_argument("--output", required=True, help="Output path for TTS lines JSON")
    parser.add_argument("--assets", required=True, help="Path to assets directory")
    parser.add_argument("--max-chars", type=int, default=220, help="Maximum characters per line")
    parser.add_argument("--enforce-known", action="store_true",
                       help="Exit with error if any unresolved speakers found")
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    assets_dir = Path(args.assets)
    
    # Load input story
    try:
        story = load_json(input_path)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    # Load speaker registries
    speakers_registry, name_map = load_speaker_registries(assets_dir)
    
    # Generate TTS lines
    lines, unresolved_speakers = generate_tts_lines(
        story, speakers_registry, name_map, args.max_chars, args.enforce_known
    )
    
    # Handle unresolved speakers
    if unresolved_speakers:
        if args.enforce_known:
            print("Error: Unresolved speakers found:")
            for speaker in sorted(unresolved_speakers):
                print(f"  {speaker}")
            sys.exit(1)
        else:
            print("Warning: Unresolved speakers found:")
            for speaker in sorted(unresolved_speakers):
                print(f"  {speaker}")
    
    # Create output directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write TTS lines
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(lines, f, indent=2, ensure_ascii=False)
    
    print(f"Generated {len(lines)} TTS lines → {output_path}")
    sys.exit(0)


if __name__ == "__main__":
    main()