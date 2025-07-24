import re
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPlainTextEdit, QDialogButtonBox
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QFont, QColor
from PyQt6.QtCore import Qt

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
        self.highlighting_rules.extend([
            (re.compile(rf"\b{keyword}\b"), main_keyword_format)
            for keyword in main_keywords
        ])

        # Property keys (light blue)
        property_keyword_format = QTextCharFormat()
        property_keyword_format.setForeground(QColor("#9CDCFE"))  # Light blue
        property_keyword_format.setFontWeight(QFont.Weight.Normal)
        property_keywords = ["path", "game", "id", "source", "load_after", "load_before"]
        self.highlighting_rules.extend([
            (re.compile(rf"\b{keyword}\b"), property_keyword_format)
            for keyword in property_keywords
        ])

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
        self.highlighting_rules.append((re.compile(r"\b(true|false)\b"), boolean_format))

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
        
        self.setWindowTitle(f"Edit Profile: {self.config_manager.get_profile_path(game_name).name}")
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
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
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
        content = ' '.join(content.split())
        
        # Add line breaks after main sections
        content = re.sub(r'(profileVersion\s*=\s*"[^"]*")', r'\1\n\n', content)
        
        # Format natives array
        content = re.sub(r'natives\s*=\s*\[(.*?)\]', self._format_array_section, content)
        
        # Format supports array  
        content = re.sub(r'supports\s*=\s*\[(.*?)\]', self._format_array_section, content)
        
        # Format packages array
        content = re.sub(r'packages\s*=\s*\[(.*?)\]', self._format_array_section, content)
        
        # Clean up extra newlines
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        
        return content.strip()
    
    def _format_array_section(self, match):
        """Format individual array sections."""
        full_match = match.group(0)
        array_name = full_match.split('=')[0].strip()
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
            
            if char == '{':
                brace_count += 1
                current_item += char
            elif char == '}':
                brace_count -= 1
                current_item += char
                if brace_count == 0:
                    items.append(current_item.strip())
                    current_item = ""
                    # Skip comma and whitespace
                    while i + 1 < len(array_content) and array_content[i + 1] in ', \t':
                        i += 1
            elif char == ',' and brace_count == 0:
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

    def save_and_accept(self):
        content = self.editor.toPlainText()
        try:
            self.config_manager.save_profile_content(self.game_name, content)
            self.accept()
        except Exception as e:
            print(f"Failed to save profile: {e}")
            # Optionally show a QMessageBox to the user here
            self.reject()