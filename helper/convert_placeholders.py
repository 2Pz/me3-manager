"""
Convert named placeholders {name} to positional placeholders {} in translation files
"""

import json
import os
import re
import sys

# Add parent directory to path to import utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.resource_path import resource_path


def convert_placeholders_in_text(text):
    """Convert {name} to {} in a string"""
    return re.sub(r'\{\w+\}', '{}', text)


def process_file(file_path):
    """Process a single JSON file"""
    print(f"Processing: {os.path.basename(file_path)}")
    
    # Load file
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Convert placeholders
    converted_count = 0
    for key, value in data.items():
        if isinstance(value, str) and '{' in value:
            original = value
            data[key] = convert_placeholders_in_text(value)
            if original != data[key]:
                converted_count += 1
                print(f"  {key}: {original} → {data[key]}")
    
    # Save file
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"  Converted {converted_count} strings\n")


def main():
    translations_dir = resource_path("resources/translations")
    
    if not os.path.exists(translations_dir):
        print(f"Directory not found: {translations_dir}")
        return
    
    # Find all JSON files
    json_files = [f for f in os.listdir(translations_dir) if f.endswith('.json')]
    
    if not json_files:
        print("No JSON files found")
        return
    
    print(f"Found {len(json_files)} files: {json_files}\n")
    
    # Process each file
    for filename in json_files:
        file_path = os.path.join(translations_dir, filename)
        try:
            process_file(file_path)
        except Exception as e:
            print(f"Error processing {filename}: {e}")
    
    print("Done!")


if __name__ == "__main__":
    main()