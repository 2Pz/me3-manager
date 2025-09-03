import json
import os
from typing import Dict
from utils.resource_path import resource_path
from PyQt6.QtCore import QLocale


class Translator:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Translator, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.current_language = "en"
            self.translations: Dict[str, Dict[str, str]] = {}
            self._load_translations()
            self._initialized = True

    def _load_translations(self):
        """Load all available translations from JSON files"""
        translations_dir = resource_path("resources/translations")

        # Create translations directory if it doesn't exist
        if not os.path.exists(translations_dir):
            os.makedirs(translations_dir)

        # Load all JSON translation files
        for filename in os.listdir(translations_dir):
            if filename.endswith(".json"):
                lang_code = filename[:-5]  # Remove .json extension
                file_path = os.path.join(translations_dir, filename)

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        self.translations[lang_code] = json.load(f)
                except Exception as e:
                    print(f"Error loading translation file {filename}: {e}")

        # Ensure we have English translations
        if "en" not in self.translations:
            self.translations["en"] = {}

    def set_language(self, language_code: str):
        """Set the current language"""
        if language_code in self.translations:
            self.current_language = language_code
        else:
            print(
                f"Warning: Translation for language '{language_code}' not found. Using English."
            )
            self.current_language = "en"

    def set_system_language(self):
        """Set language based on system locale"""
        # Get system locale
        system_locale = QLocale.system().name()
        language_code = system_locale.split("_")[0]  # Extract language part (e.g., "zh" from "zh_CN")

        language_code = "ar" # For testing purposes
        # Try to set the language, fallback to English if not available
        if language_code in self.translations:
            self.current_language = language_code
        else:
            # Try with full locale code if language code alone is not found
            if system_locale in self.translations:
                self.current_language = system_locale
            else:
                print(
                    f"System language '{system_locale}' not supported. Using English."
                )
                self.current_language = "en"

    def tr(self, key: str, **kwargs) -> str:
        """Translate a string using the current language"""
        translation = self.translations.get(self.current_language, {}).get(
            key, self.translations.get("en", {}).get(key, key)
        )

        if kwargs:
            try:
                # Convert kwargs to positional args for {} placeholders
                translation = translation.format(*kwargs.values())
            except (KeyError, IndexError) as e:
                print(f"Error formatting translation for key '{key}': {e}")

        return translation

    def get_available_languages(self) -> Dict[str, str]:
        """Get available languages with their names"""
        result = {}
        for lang_code in self.translations.keys():
            # Try to get language name from the translation file itself
            lang_name = self.translations[lang_code].get("language_name", lang_code)
            result[lang_code] = lang_name
        
        return result


# Global translator instance
translator = Translator()


def tr(key: str, **kwargs) -> str:
    """Global translation function"""
    return translator.tr(key, **kwargs)
