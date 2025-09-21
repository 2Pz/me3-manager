import re

from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from me3_manager.core.config_facade import ConfigFacade as ConfigManager
from me3_manager.utils.translator import tr


class TomlHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for TOML-like config files with VSCode Dark+ style."""

    def __init__(self, parent):
        super().__init__(parent)
        self.highlighting_rules = []

        # Top-level keys (bright blue, bold)
        main_keyword_format = QTextCharFormat()
        main_keyword_format.setForeground(QColor("#569CD6"))
        main_keyword_format.setFontWeight(QFont.Weight.Bold)
        main_keywords = [
            "profileVersion",
            "natives",
            "supports",
            "packages",
            "mods",
            "game",
        ]
        self.highlighting_rules.extend(
            [
                (re.compile(rf"\b{keyword}\b"), main_keyword_format)
                for keyword in main_keywords
            ]
        )

        # Property keys (light blue)
        property_keyword_format = QTextCharFormat()
        property_keyword_format.setForeground(QColor("#9CDCFE"))
        property_keyword_format.setFontWeight(QFont.Weight.Normal)
        property_keywords = [
            "path",
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
            # v2 game settings
            "launch",
            "savefile",
            "disable_arxan",
            "start_online",
        ]

        self.highlighting_rules.extend(
            [
                (re.compile(rf"\b{keyword}\b"), property_keyword_format)
                for keyword in property_keywords
            ]
        )
        self.highlighting_rules.append(
            (
                re.compile(
                    r'"[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*"(?=\s*=)'
                ),
                property_keyword_format,
            )
        )

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#CE9178"))
        self.highlighting_rules.append((re.compile(r'"[^"]*"(?!\s*=)'), string_format))
        self.highlighting_rules.append((re.compile(r"'[^']*'"), string_format))

        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#B5CEA8"))
        self.highlighting_rules.append((re.compile(r"\b\d+(\.\d+)?\b"), number_format))

        boolean_format = QTextCharFormat()
        boolean_format.setForeground(QColor("#569CD6"))
        boolean_format.setFontWeight(QFont.Weight.DemiBold)
        self.highlighting_rules.append(
            (re.compile(r"\b(true|false)\b"), boolean_format)
        )

        punctuation_format = QTextCharFormat()
        punctuation_format.setForeground(QColor("#D4D4D4"))
        self.highlighting_rules.append((re.compile(r"[=,]"), punctuation_format))

        bracket_format = QTextCharFormat()
        bracket_format.setForeground(QColor("#DCDCAA"))
        self.highlighting_rules.append((re.compile(r"[\[\]]"), bracket_format))

        brace_format = QTextCharFormat()
        brace_format.setForeground(QColor("#C586C0"))
        self.highlighting_rules.append((re.compile(r"[{}]"), brace_format))

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6A9955"))
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
            tr(
                "edit_profile_title",
                profile_name=self.config_manager.get_profile_path(game_name).name,
            )
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

        self.editor.setStyleSheet(
            """
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 12px;
                font-family: Consolas, 'Courier New', monospace;
                line-height: 1.5;
            }
            QPlainTextEdit:focus { border: 1px solid #007acc; }
            """
        )

        self.editor.setTabStopDistance(32)

        self.highlighter = TomlHighlighter(self.editor.document())
        layout.addWidget(self.editor)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.setStyleSheet(
            """
            QDialogButtonBox { padding-top: 10px; }
            QDialogButtonBox QPushButton {
                background-color: #3c3c3c; color: #ffffff;
                border: 1px solid #5a5a5a; border-radius: 3px; padding: 8px 20px;
                font-size: 11px; min-width: 80px;
            }
            QDialogButtonBox QPushButton:hover { background-color: #4a4a4a; border-color: #6a6a6a; }
            QDialogButtonBox QPushButton:pressed { background-color: #2a2a2a; }
            """
        )

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
            self.editor.setPlainText(tr("profile_load_failed_comment", error=str(e)))

    def format_toml_content(self, content):
        import re

        content = re.sub(r"\n\s*\n\s*\n+", "\n\n", content)
        content = re.sub(
            r'(profileVersion\s*=\s*"[^"]*")\s*\n\s*\n\s*(\[\[)', r"\1\n\n\2", content
        )
        return content.strip()

    def save_and_accept(self):
        content = self.editor.toPlainText()
        try:
            # Try to parse and re-write using our version-aware writer so that
            # switching profileVersion between v1 and v2 converts layout while
            # preserving enabled mods.
            import tomllib

            try:
                data = tomllib.loads(content)
                # Normalize to canonical, then write with requested version
                from me3_manager.core.profiles import (
                    ProfileConverter,
                    TomlProfileWriter,
                )

                canonical = ProfileConverter.normalize(data)
                # Preserve requested version from the edited content if present
                requested_version = str(
                    data.get("profileVersion", canonical.get("profileVersion", "v1"))
                )
                canonical["profileVersion"] = requested_version

                profile_path = self.config_manager.get_profile_path(self.game_name)
                TomlProfileWriter.write_profile(profile_path, canonical, self.game_name)
            except Exception:
                # Fallback: raw write if parsing/conversion fails
                self.config_manager.save_profile_content(self.game_name, content)

            self.accept()
        except Exception as e:
            QMessageBox.warning(
                self,
                tr("profile_save_failed_title"),
                tr("profile_save_failed_msg", error=str(e)),
            )
            self.reject()
