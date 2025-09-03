#!/usr/bin/env python3
"""
Translation Sync Script
Synchronizes all translation JSON files with the master English translation file.
- Adds missing keys from en.json to other translation files
- Organizes keys to match the order in en.json
- Preserves existing translations
"""

import json
import os
import sys

# Add parent directory to path to import utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.resource_path import resource_path


def load_json_file(file_path):
    """Load and parse a JSON file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return None


def save_json_file(file_path, data):
    """Save data to a JSON file with proper formatting."""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving {file_path}: {e}")
        return False


def sync_translations():
    """Main function to sync all translation files."""
    # Get the translations directory
    translations_dir = resource_path("resources/translations")

    if not os.path.exists(translations_dir):
        print(f"Translations directory not found: {translations_dir}")
        return

    # Load master file (en.json)
    master_file = os.path.join(translations_dir, "en.json")

    if not os.path.exists(master_file):
        print(f"Master file not found: {master_file}")
        return

    print(f"Loading master file: {master_file}")
    master_data = load_json_file(master_file)

    if master_data is None:
        print("Failed to load master file")
        return

    print(f"Master file contains {len(master_data)} keys")

    # Find all JSON files in the directory
    json_files = [
        f
        for f in os.listdir(translations_dir)
        if f.endswith(".json") and f != "en.json"
    ]

    if not json_files:
        print("No other translation files found")
        return

    print(f"Found {len(json_files)} translation files: {json_files}")

    # Process each translation file
    for filename in json_files:
        file_path = os.path.join(translations_dir, filename)
        print(f"\nProcessing: {filename}")

        # Load existing translation
        existing_data = load_json_file(file_path)

        if existing_data is None:
            print("  Creating new file with English translations")
            existing_data = {}

        # Create synchronized data with master key order
        synced_data = {}
        added_keys = []

        # Go through master keys in order
        for key in master_data.keys():
            if key in existing_data:
                # Keep existing translation
                synced_data[key] = existing_data[key]
            else:
                # Add missing key with English translation
                synced_data[key] = master_data[key]
                added_keys.append(key)

        # Check for extra keys in existing file (not in master)
        extra_keys = set(existing_data.keys()) - set(master_data.keys())

        # Report changes
        print(f"  Keys in file: {len(existing_data)}")
        print(f"  Keys in master: {len(master_data)}")

        if added_keys:
            print(f"  Added {len(added_keys)} missing keys:")
            for key in added_keys[:5]:  # Show first 5
                print(f"    + {key}")
            if len(added_keys) > 5:
                print(f"    ... and {len(added_keys) - 5} more")

        if extra_keys:
            print(f"  Found {len(extra_keys)} extra keys (keeping them at the end):")
            for key in list(extra_keys)[:3]:  # Show first 3
                print(f"    ? {key}")
            if len(extra_keys) > 3:
                print(f"    ... and {len(extra_keys) - 3} more")

            # Add extra keys at the end
            for key in sorted(extra_keys):
                synced_data[key] = existing_data[key]

        # Save synchronized file
        if save_json_file(file_path, synced_data):
            print(f"Successfully updated {filename}")
        else:
            print(f"Failed to update {filename}")

    print("\nSync completed!")


if __name__ == "__main__":
    sync_translations()
