import re
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPlainTextEdit, QDialogButtonBox
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QFont, QColor

from core.config_manager import ConfigManager


class TomlHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for TOML-like config files with VSCode Dark+ style."""

    def __init__(self, parent):
        super().__init__(parent)
        self.highlighting_rules = []

        # Top-level keys (bright blue, bold)
        main_keyword_format = QTextCharFormat()
        main_keyword_format.setForeground(QColor("#569CD6"))  # Blue
        main_keyword_format.setFontWeight(QFont.Weight.Bold)
        main_keywords = ["profileVersion", "natives", "supports", "packages"]
        self.highlighting_rules.extend(
            [
                (re.compile(rf"\b{keyword}\b"), main_keyword_format)
                for keyword in main_keywords
            ]
        )

        # Property keys (light blue)
        property_keyword_format = QTextCharFormat()
        property_keyword_format.setForeground(QColor("#9CDCFE"))  # Light blue
        property_keyword_format.setFontWeight(QFont.Weight.Normal)
        property_keywords = [
            "path",
            "game",
            "id",
            "source",
            "load_after",
            "load_before",
            "enabled",
            "optional",
            "initializer",
            "finalizer",
            "function",
            "delay",
            "ms",
            "since",
        ]
        self.highlighting_rules.extend(
            [
                (re.compile(rf"\b{keyword}\b"), property_keyword_format)
                for keyword in property_keywords
            ]
        )

        # Strings (orange, match single and double quotes)
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#CE9178"))  # Orange
        self.highlighting_rules.append((re.compile(r'"[^"]*"'), string_format))
        self.highlighting_rules.append((re.compile(r"'[^']*'"), string_format))

        # Numbers (light purple)
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#B5CEA8"))  # VSCode light greenish number
        self.highlighting_rules.append((re.compile(r"\b\d+(\.\d+)?\b"), number_format))

        # Booleans (true/false)
        boolean_format = QTextCharFormat()
        boolean_format.setForeground(QColor("#569CD6"))  # Same blue as keywords
        boolean_format.setFontWeight(QFont.Weight.DemiBold)
        self.highlighting_rules.append(
            (re.compile(r"\b(true|false)\b"), boolean_format)
        )

        # Punctuation (light gray)
        punctuation_format = QTextCharFormat()
        punctuation_format.setForeground(QColor("#D4D4D4"))  # Light gray
        self.highlighting_rules.append((re.compile(r"[=,]"), punctuation_format))

        # Brackets: [ ] (yellow)
        bracket_format = QTextCharFormat()
        bracket_format.setForeground(QColor("#DCDCAA"))  # Yellow-ish
        self.highlighting_rules.append((re.compile(r"[\[\]]"), bracket_format))

        # Braces: { } (pinkish/magenta)
        brace_format = QTextCharFormat()
        brace_format.setForeground(QColor("#C586C0"))  # Pink
        self.highlighting_rules.append((re.compile(r"[{}]"), brace_format))

        # Comments (green italic)
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6A9955"))  # Green
        comment_format.setFontItalic(True)
        self.highlighting_rules.append((re.compile(r"#.*"), comment_format))

    def highlightBlock(self, text):
        for pattern, fmt in self.highlighting_rules:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)


class ProfileEditor(QDialog):
    """A dialog for editing .me3 profile files with better layout and scaling."""

    def __init__(self, game_name: str, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.game_name = game_name
        self.config_manager = config_manager

        self.setWindowTitle(
            f"Edit Profile: {self.config_manager.get_profile_path(game_name).name}"
        )
        self.setMinimumSize(900, 650)
        self.resize(1400, 750)
        self.setStyleSheet("QDialog { background-color: #252525; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        self.editor = QPlainTextEdit()
        font = QFont("Consolas", 12)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.3)
        self.editor.setFont(font)

        self.editor.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 12px;
                font-family: Consolas, 'Courier New', monospace;
                line-height: 1.5;
            }
            QPlainTextEdit:focus {
                border: 1px solid #007acc;
            }
        """)

        self.editor.setTabStopDistance(32)

        self.highlighter = TomlHighlighter(self.editor.document())
        layout.addWidget(self.editor)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.setStyleSheet("""
            QDialogButtonBox {
                padding-top: 10px;
            }
            QDialogButtonBox QPushButton {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #5a5a5a;
                border-radius: 3px;
                padding: 8px 20px;
                font-size: 11px;
                min-width: 80px;
            }
            QDialogButtonBox QPushButton:hover {
                background-color: #4a4a4a;
                border-color: #6a6a6a;
            }
            QDialogButtonBox QPushButton:pressed {
                background-color: #2a2a2a;
            }
        """)

        button_box.accepted.connect(self.save_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.load_profile()

    def load_profile(self):
        try:
            content = self.config_manager.get_profile_content(self.game_name)
            formatted_content = self.format_toml_content(content)
            self.editor.setPlainText(formatted_content)
        except Exception as e:
            self.editor.setPlainText(f"# Failed to load profile:\n# {e}")

    def format_toml_content(self, content):
        """Format TOML content for better readability with proper structure."""
        import re

        # Remove all extra whitespace and newlines first
        content = " ".join(content.split())

        # Add line breaks after main sections
        content = re.sub(r'(profileVersion\s*=\s*"[^"]*")', r"\1\n\n", content)

        # Format natives array with advanced options support
        content = re.sub(
            r"natives\s*=\s*\[(.*?)\]", self._format_natives_section, content
        )

        # Format supports array
        content = re.sub(
            r"supports\s*=\s*\[(.*?)\]", self._format_simple_array_section, content
        )

        # Format packages array with advanced options support
        content = re.sub(
            r"packages\s*=\s*\[(.*?)\]", self._format_packages_section, content
        )

        # Clean up extra newlines
        content = re.sub(r"\n\s*\n\s*\n", "\n\n", content)

        return content.strip()

    def _format_array_section(self, match):
        """Format individual array sections."""
        full_match = match.group(0)
        array_name = full_match.split("=")[0].strip()
        array_content = match.group(1).strip()

        if not array_content:
            return f"{array_name} = []"

        # Split by objects (enclosed in braces) or simple values
        items = []
        current_item = ""
        brace_count = 0

        i = 0
        while i < len(array_content):
            char = array_content[i]

            if char == "{":
                brace_count += 1
                current_item += char
            elif char == "}":
                brace_count -= 1
                current_item += char
                if brace_count == 0:
                    items.append(current_item.strip())
                    current_item = ""
                    # Skip comma and whitespace
                    while i + 1 < len(array_content) and array_content[i + 1] in ", \t":
                        i += 1
            elif char == "," and brace_count == 0:
                if current_item.strip():
                    items.append(current_item.strip())
                current_item = ""
            else:
                current_item += char

            i += 1

        # Add remaining item
        if current_item.strip():
            items.append(current_item.strip())

        # Format the array
        if not items:
            return f"{array_name} = []"

        result = f"\n{array_name} = [\n"
        for item in items:
            result += f"    {item},\n"
        result += "]\n"

        return result

    def _format_natives_section(self, match):
        """Format natives array with proper indentation for advanced options."""
        match.group(0)
        array_content = match.group(1).strip()

        if not array_content:
            return "\nnatives = []\n"

        # Parse native objects
        natives = self._parse_objects(array_content)

        if not natives:
            return "\nnatives = []\n"

        result = "\nnatives = [\n"
        for i, native in enumerate(natives):
            result += self._format_native_object(
                native, is_last=(i == len(natives) - 1)
            )
        result += "]\n"

        return result

    def _format_packages_section(self, match):
        """Format packages array with proper indentation for advanced options."""
        match.group(0)
        array_content = match.group(1).strip()

        if not array_content:
            return "\npackages = []\n"

        # Parse package objects
        packages = self._parse_objects(array_content)

        if not packages:
            return "\npackages = []\n"

        result = "\npackages = [\n"
        for i, package in enumerate(packages):
            result += self._format_package_object(
                package, is_last=(i == len(packages) - 1)
            )
        result += "]\n"

        return result

    def _format_simple_array_section(self, match):
        """Format simple arrays like supports."""
        full_match = match.group(0)
        array_name = full_match.split("=")[0].strip()
        array_content = match.group(1).strip()

        if not array_content:
            return f"\n{array_name} = []\n"

        # Parse simple objects
        objects = self._parse_objects(array_content)

        if not objects:
            return f"\n{array_name} = []\n"

        result = f"\n{array_name} = [\n"
        for obj in objects:
            result += f"    {obj},\n"
        result += "]\n"

        return result

    def _parse_objects(self, content):
        """Parse TOML objects from array content."""
        objects = []
        current_obj = ""
        brace_count = 0

        i = 0
        while i < len(content):
            char = content[i]

            if char == "{":
                brace_count += 1
                current_obj += char
            elif char == "}":
                brace_count -= 1
                current_obj += char
                if brace_count == 0:
                    objects.append(current_obj.strip())
                    current_obj = ""
                    # Skip comma and whitespace
                    while i + 1 < len(content) and content[i + 1] in ", \t":
                        i += 1
            elif char == "," and brace_count == 0:
                if current_obj.strip():
                    objects.append(current_obj.strip())
                current_obj = ""
            else:
                current_obj += char

            i += 1

        # Add remaining object
        if current_obj.strip():
            objects.append(current_obj.strip())

        return objects

    def _format_native_object(self, native_str, is_last=False):
        """Format a single native object with proper indentation."""
        # Remove outer braces
        native_str = native_str.strip()
        if native_str.startswith("{") and native_str.endswith("}"):
            native_str = native_str[1:-1].strip()

        # Parse key-value pairs
        properties = self._parse_properties(native_str)

        if not properties:
            return "    {},\n" if not is_last else "    {}\n"

        # Check if this is a simple native (only path and enabled)
        is_simple = len(properties) <= 2 and all(
            key in ["path", "enabled"] for key in properties.keys()
        )

        if is_simple:
            # Single line format for simple natives
            prop_strs = []
            for key, value in properties.items():
                prop_strs.append(f"{key} = {value}")
            content = ", ".join(prop_strs)
            return f"    {{{content}}}{',' if not is_last else ''}\n"
        else:
            # Multi-line format for complex natives
            result = "    {\n"

            # Order properties logically
            ordered_keys = [
                "path",
                "enabled",
                "optional",
                "initializer",
                "finalizer",
                "load_before",
                "load_after",
            ]

            for key in ordered_keys:
                if key in properties:
                    value = properties[key]
                    if (
                        key in ["load_before", "load_after"]
                        and value.startswith("[")
                        and value.endswith("]")
                    ):
                        # Format dependency arrays nicely
                        result += (
                            f"        {key} = {self._format_dependency_array(value)},\n"
                        )
                    elif (
                        key == "initializer"
                        and value.startswith("{")
                        and value.endswith("}")
                    ):
                        # Format initializer object nicely
                        result += (
                            f"        {key} = {self._format_initializer(value)},\n"
                        )
                    else:
                        result += f"        {key} = {value},\n"

            # Add any remaining properties not in ordered list
            for key, value in properties.items():
                if key not in ordered_keys:
                    result += f"        {key} = {value},\n"

            result += "    }" + ("," if not is_last else "") + "\n"
            return result

    def _format_package_object(self, package_str, is_last=False):
        """Format a single package object with proper indentation."""
        # Remove outer braces
        package_str = package_str.strip()
        if package_str.startswith("{") and package_str.endswith("}"):
            package_str = package_str[1:-1].strip()

        # Parse key-value pairs
        properties = self._parse_properties(package_str)

        if not properties:
            return "    {},\n" if not is_last else "    {}\n"

        # Check if this is a simple package
        is_simple = len(properties) <= 3 and all(
            key in ["id", "path", "source", "enabled"] for key in properties.keys()
        )

        if is_simple:
            # Single line format for simple packages
            prop_strs = []
            for key, value in properties.items():
                prop_strs.append(f"{key} = {value}")
            content = ", ".join(prop_strs)
            return f"    {{{content}}}{',' if not is_last else ''}\n"
        else:
            # Multi-line format for complex packages
            result = "    {\n"

            # Order properties logically
            ordered_keys = [
                "id",
                "path",
                "source",
                "enabled",
                "load_before",
                "load_after",
            ]

            for key in ordered_keys:
                if key in properties:
                    value = properties[key]
                    if (
                        key in ["load_before", "load_after"]
                        and value.startswith("[")
                        and value.endswith("]")
                    ):
                        # Format dependency arrays nicely
                        result += (
                            f"        {key} = {self._format_dependency_array(value)},\n"
                        )
                    else:
                        result += f"        {key} = {value},\n"

            # Add any remaining properties
            for key, value in properties.items():
                if key not in ordered_keys:
                    result += f"        {key} = {value},\n"

            result += "    }" + ("," if not is_last else "") + "\n"
            return result

    def _parse_properties(self, content):
        """Parse key-value properties from object content."""
        properties = {}
        current_key = ""
        current_value = ""
        in_key = True
        brace_count = 0
        bracket_count = 0
        in_string = False
        string_char = None

        i = 0
        while i < len(content):
            char = content[i]

            if not in_string and char in ['"', "'"]:
                in_string = True
                string_char = char
                if in_key:
                    current_key += char
                else:
                    current_value += char
            elif in_string and char == string_char:
                in_string = False
                string_char = None
                if in_key:
                    current_key += char
                else:
                    current_value += char
            elif not in_string:
                if char == "=" and in_key:
                    in_key = False
                elif char == "{":
                    brace_count += 1
                    current_value += char
                elif char == "}":
                    brace_count -= 1
                    current_value += char
                elif char == "[":
                    bracket_count += 1
                    current_value += char
                elif char == "]":
                    bracket_count -= 1
                    current_value += char
                elif char == "," and brace_count == 0 and bracket_count == 0:
                    # End of property
                    if current_key.strip() and current_value.strip():
                        properties[current_key.strip()] = current_value.strip()
                    current_key = ""
                    current_value = ""
                    in_key = True
                else:
                    if in_key:
                        current_key += char
                    else:
                        current_value += char
            else:
                if in_key:
                    current_key += char
                else:
                    current_value += char

            i += 1

        # Add final property
        if current_key.strip() and current_value.strip():
            properties[current_key.strip()] = current_value.strip()

        return properties

    def _format_dependency_array(self, array_str):
        """Format dependency arrays with proper spacing."""
        # Remove outer brackets
        array_str = array_str.strip()
        if array_str.startswith("[") and array_str.endswith("]"):
            array_str = array_str[1:-1].strip()

        if not array_str:
            return "[]"

        # Parse dependency objects
        deps = self._parse_objects(array_str)

        if len(deps) == 1:
            # Single dependency on one line
            return f"[{deps[0]}]"
        else:
            # Multiple dependencies, format nicely
            result = "[\n"
            for dep in deps:
                result += f"            {dep},\n"
            result += "        ]"
            return result

    def _format_initializer(self, init_str):
        """Format initializer objects with proper spacing."""
        # Simple formatting for initializer objects
        return init_str

    def save_and_accept(self):
        content = self.editor.toPlainText()
        try:
            self.config_manager.save_profile_content(self.game_name, content)
            self.accept()
        except Exception as e:
            print(f"Failed to save profile: {e}")
            # Optionally show a QMessageBox to the user here
            self.reject()
