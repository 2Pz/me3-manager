"""
Service for applying configuration overrides to files.
Uses ConfigUpdater to preserve comments and formatting in INI files.
"""

import logging
from pathlib import Path
from typing import Any

from configupdater import ConfigUpdater

log = logging.getLogger(__name__)


class ConfigApplicator:
    """Handles application of configuration overrides to files on disk."""

    @staticmethod
    def apply_ini_overrides(
        config_path: Path, overrides: dict[str, Any], case_sensitive: bool = True
    ) -> bool:
        """
        Apply key-value overrides to an INI file while preserving comments.

        Args:
            config_path: Path to the INI file.
            overrides: Dictionary of overrides. Supports:
                       1. Flat: { "Section.Key": Value }
                       2. Nested: { "Section": { "Key": Value } }
            case_sensitive: Whether to respect case sensitivity (default: True).

        Returns:
            True if changes were made and saved, False otherwise.
        """
        if not overrides:
            return False

        # Normalize overrides into { "Section": { "Key": Value } }
        normalized_overrides: dict[str, dict[str, Any]] = {}

        for key, value in overrides.items():
            if isinstance(value, dict):
                # Nested format
                section = key
                if section not in normalized_overrides:
                    normalized_overrides[section] = {}
                normalized_overrides[section].update(value)
            elif "." in key:
                # Dotted format
                section, option = key.split(".", 1)
                if section not in normalized_overrides:
                    normalized_overrides[section] = {}
                normalized_overrides[section][option] = value
            else:
                log.warning(
                    "Skipping invalid config override key (no section and not a dict): %s",
                    key,
                )

        if not normalized_overrides:
            return False

        try:
            updater = ConfigUpdater()
            file_exists = config_path.exists()

            if file_exists:
                # Read file with appropriate encoding
                # Try utf-8 first, fallback to latin-1
                try:
                    updater.read(str(config_path), encoding="utf-8")
                except UnicodeDecodeError:
                    updater.read(str(config_path), encoding="latin-1")
            else:
                # Ensure parent directory exists
                config_path.parent.mkdir(parents=True, exist_ok=True)
                log.info("Creating new config file: %s", config_path)

            changed = False

            for section_name, options in normalized_overrides.items():
                if not updater.has_section(section_name):
                    updater.add_section(section_name)
                    updater[section_name].add_after.space(1)
                    changed = True

                section = updater[section_name]

                for key, value in options.items():
                    val_str = str(value)

                    if key in section:
                        current_val = section[key].value
                        if current_val != val_str:
                            section[key] = val_str
                            log.info(
                                "Updated config %s: [%s] %s = %s",
                                config_path.name,
                                section_name,
                                key,
                                val_str,
                            )
                            changed = True
                    else:
                        section[key] = val_str
                        log.info(
                            "Added config %s: [%s] %s = %s",
                            config_path.name,
                            section_name,
                            key,
                            val_str,
                        )
                        changed = True

            if changed:
                if file_exists:
                    updater.update_file()
                else:
                    with open(config_path, "w", encoding="utf-8") as f:
                        updater.write(f)
                return True

            return False

        except Exception:
            log.exception("Failed to apply config overrides to %s", config_path)
            return False
