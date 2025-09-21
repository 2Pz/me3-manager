import json
import logging
import os

from PySide6.QtCore import QLocale

from me3_manager.utils.resource_path import resource_path

log = logging.getLogger(__name__)


class Translator:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.current_language = "en"
            self.translations: dict[str, dict[str, str]] = {}
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
                    log.error("Cannot load translation file %s: %s", filename, e)

        # Ensure we have English translations
        if "en" not in self.translations:
            self.translations["en"] = {}

    def set_language(self, language_code: str):
        """Set the current language"""
        if language_code in self.translations:
            self.current_language = language_code
        else:
            log.warning("Translation for %s not found. Using English.", language_code)
            self.current_language = "en"

    def set_system_language(self):
        """Set language based on system locale"""
        # Get system locale
        system_locale = QLocale.system().name()
        # Extract language part (e.g., "zh" from "zh_CN")
        language_code = system_locale.split("_")[0]

        # language_code = "ar" # For testing purposes
        # Try to set the language, fallback to English if not available
        if language_code in self.translations:
            self.current_language = language_code
        else:
            # Try with full locale code if language code alone is not found
            if system_locale in self.translations:
                self.current_language = system_locale
            else:
                log.warning(
                    "System locale %s not supported. Using English.", system_locale
                )
                self.current_language = "en"

    def tr(self, key: str, **kwargs) -> str:
        """Translate a string using the current language"""
        # Get translation for current language, fallback to English, then to key
        translation = self.translations.get(self.current_language, {}).get(
            key, self.translations.get("en", {}).get(key, key)
        )

        # Format with provided arguments
        if kwargs:
            try:
                translation = translation.format(**kwargs)
            except KeyError as e:
                log.error(
                    "Cannot format translation for key %s: missing argument %s", key, e
                )

        return translation

    def get_available_languages(self) -> dict[str, str]:
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
