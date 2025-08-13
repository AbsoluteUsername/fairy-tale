#!/usr/bin/env python3
import sys
import json
import hashlib
import argparse
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any


def get_current_timestamp() -> str:
    """Get current timestamp in ISO8601 format with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of file content."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def load_registry(registry_path: Path) -> Dict[str, Any]:
    """Load registry JSON file or create empty structure."""
    if registry_path.exists():
        try:
            with open(registry_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    
    return {
        "version": 1,
        "updated_at": get_current_timestamp(),
        "items": {}
    }


def save_registry(registry_path: Path, registry: Dict[str, Any]) -> None:
    """Save registry to JSON file."""
    registry["updated_at"] = get_current_timestamp()
    with open(registry_path, 'w', encoding='utf-8') as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)


def init_assets_cache(output_dir: Path) -> None:
    """Initialize assets cache directory structure and registries."""
    print(f"Initializing assets cache at {output_dir}")
    
    # Create directory structure
    directories = [
        output_dir / "images",
        output_dir / "animations", 
        output_dir / "audio",
        output_dir / "constants",
        output_dir / "registries"
    ]
    
    for dir_path in directories:
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {dir_path}")
    
    # Initialize registries
    registries = ["images.json", "animations.json", "audio.json", "constants.json"]
    
    for registry_name in registries:
        registry_path = output_dir / "registries" / registry_name
        if not registry_path.exists():
            empty_registry = {
                "version": 1,
                "updated_at": get_current_timestamp(),
                "items": {}
            }
            save_registry(registry_path, empty_registry)
            print(f"Initialized registry: {registry_path}")
        else:
            print(f"Registry already exists: {registry_path}")
    
    print("Assets cache initialization complete")


def add_constant(file_path: Path, output_dir: Path) -> None:
    """Add a constant file to the assets cache."""
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)
    
    if not file_path.is_file():
        print(f"Error: Path is not a file: {file_path}")
        sys.exit(1)
    
    # Ensure assets cache is initialized
    registries_dir = output_dir / "registries"
    constants_dir = output_dir / "constants"
    
    if not registries_dir.exists() or not constants_dir.exists():
        print("Error: Assets cache not initialized. Run 'init' command first.")
        sys.exit(1)
    
    # Compute SHA256
    sha256_full = compute_sha256(file_path)
    sha256_short = sha256_full[:12]
    
    # Load constants registry
    registry_path = registries_dir / "constants.json"
    registry = load_registry(registry_path)
    
    # Check if file already exists in registry
    if sha256_full in registry["items"]:
        print(f"Constant already exists in cache: {sha256_full}")
        return
    
    # Copy file to constants directory with content-addressed name
    target_filename = f"sha256_{sha256_short}.json"
    target_path = constants_dir / target_filename
    
    shutil.copy2(file_path, target_path)
    print(f"Copied {file_path} → {target_path}")
    
    # Update registry
    registry["items"][sha256_full] = {
        "path": f"constants/{target_filename}",
        "sha256": sha256_full,
        "meta": {
            "name": file_path.name
        }
    }
    
    save_registry(registry_path, registry)
    print(f"Updated registry: {registry_path}")
    print(f"SHA256: {sha256_full}")


def add_image(file_path: Path, output_dir: Path) -> None:
    """Add an image file to the assets cache (stub)."""
    print("add-image not implemented yet")
    sys.exit(2)


def add_animation(file_path: Path, output_dir: Path) -> None:
    """Add an animation file to the assets cache (stub)."""
    print("add-animation not implemented yet")
    sys.exit(2)


def add_audio(file_path: Path, output_dir: Path) -> None:
    """Add an audio file to the assets cache (stub)."""
    print("add-audio not implemented yet")
    sys.exit(2)


def main():
    parser = argparse.ArgumentParser(description="Manage assets cache and registries")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize assets cache")
    init_parser.add_argument("--out", required=True, help="Output directory for assets cache")
    
    # Add-constant command
    add_const_parser = subparsers.add_parser("add-constant", help="Add a constant file to cache")
    add_const_parser.add_argument("--file", required=True, help="Path to constant file")
    add_const_parser.add_argument("--out", required=True, help="Assets cache directory")
    
    # Add-image command (stub)
    add_img_parser = subparsers.add_parser("add-image", help="Add an image file to cache")
    add_img_parser.add_argument("--file", required=True, help="Path to image file")
    add_img_parser.add_argument("--out", required=True, help="Assets cache directory")
    
    # Add-animation command (stub)
    add_anim_parser = subparsers.add_parser("add-animation", help="Add an animation file to cache")
    add_anim_parser.add_argument("--file", required=True, help="Path to animation file")
    add_anim_parser.add_argument("--out", required=True, help="Assets cache directory")
    
    # Add-audio command (stub)
    add_audio_parser = subparsers.add_parser("add-audio", help="Add an audio file to cache")
    add_audio_parser.add_argument("--file", required=True, help="Path to audio file")
    add_audio_parser.add_argument("--out", required=True, help="Assets cache directory")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    output_dir = Path(args.out)
    
    if args.command == "init":
        init_assets_cache(output_dir)
    elif args.command == "add-constant":
        file_path = Path(args.file)
        add_constant(file_path, output_dir)
    elif args.command == "add-image":
        file_path = Path(args.file)
        add_image(file_path, output_dir)
    elif args.command == "add-animation":
        file_path = Path(args.file)
        add_animation(file_path, output_dir)
    elif args.command == "add-audio":
        file_path = Path(args.file)
        add_audio(file_path, output_dir)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()