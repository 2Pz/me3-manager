import re
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from me3_manager.utils.translator import tr


class IniSyntaxHighlighter(QSyntaxHighlighter):
    """Enhanced syntax highlighter for INI files with improved visual hierarchy."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []

        # Section format [Section] - main sections in bold blue
        section_format = QTextCharFormat()
        section_format.setForeground(QColor("#569cd6"))
        section_format.setFontWeight(QFont.Weight.Bold)
        self.highlighting_rules.append((re.compile(r"\[[^\n\]]+\]"), section_format))

        # Key format Key=... - keys in lighter blue
        key_format = QTextCharFormat()
        key_format.setForeground(QColor("#9cdcfe"))
        key_format.setFontWeight(QFont.Weight.Normal)
        self.highlighting_rules.append(
            (re.compile(r"^[^\s=;#]+(?=\s*=)", re.MULTILINE), key_format)
        )

        # String values in quotes - orange for quoted strings
        quoted_string_format = QTextCharFormat()
        quoted_string_format.setForeground(QColor("#ce9178"))
        self.highlighting_rules.append((re.compile(r'"[^"]*"'), quoted_string_format))
        self.highlighting_rules.append((re.compile(r"'[^']*'"), quoted_string_format))

        # Boolean values - special highlighting for true/false/yes/no/on/off
        boolean_format = QTextCharFormat()
        boolean_format.setForeground(QColor("#569cd6"))
        boolean_format.setFontWeight(QFont.Weight.Bold)
        boolean_pattern = r"=\s*(true|false|yes|no|on|off)\s*(?:[;#]|$)"
        self.highlighting_rules.append(
            (re.compile(boolean_pattern, re.IGNORECASE | re.MULTILINE), boolean_format)
        )

        # Numeric values - highlight numbers
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#b5cea8"))  # Light green for numbers
        number_pattern = r"=\s*([-+]?(?:\d*\.?\d+)(?:[eE][-+]?\d+)?)\s*(?:[;#]|$)"
        self.highlighting_rules.append(
            (re.compile(number_pattern, re.MULTILINE), number_format)
        )

        # General values - catch remaining values after =
        value_format = QTextCharFormat()
        value_format.setForeground(QColor("#d4d4d4"))  # Light gray for other values
        self.highlighting_rules.append(
            (re.compile(r"=\s*([^;\r\n#]+?)(?:\s*[;#]|$)", re.MULTILINE), value_format)
        )

        # Comment format ;... or #... - comments in green italic
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6a9955"))
        comment_format.setFontItalic(True)
        self.highlighting_rules.append((re.compile(r"[;#].*"), comment_format))

        # Equals sign - subtle highlighting
        equals_format = QTextCharFormat()
        equals_format.setForeground(QColor("#d4d4d4"))
        self.highlighting_rules.append((re.compile(r"="), equals_format))

    def highlightBlock(self, text):
        # Apply highlighting rules in order
        for pattern, format in self.highlighting_rules:
            for match in pattern.finditer(text):
                # For patterns that capture groups, highlight only the captured group
                if match.groups():
                    start, end = match.span(1)  # Highlight the first captured group
                else:
                    start, end = match.span()  # Highlight the entire match
                self.setFormat(start, end - start, format)


class ConfigEditorDialog(QDialog):
    """Dialog for editing mod INI configuration files."""

    def __init__(self, mod_name: str, config_path: Path, parent=None):
        super().__init__(parent)
        # *** FIX: Store the initial path to detect changes later ***
        self.initial_path = config_path
        self.current_path = config_path

        self.setWindowTitle(tr("edit_config_title", mod_name=mod_name))
        self.setMinimumSize(700, 500)
        self.resize(1400, 750)
        self.setStyleSheet("background-color: #252525; color: #ffffff;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # Path display and browse
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit(str(self.current_path))
        self.path_edit.setReadOnly(True)
        self.path_edit.setStyleSheet(
            "background-color: #2d2d2d; border: 1px solid #3d3d3d; padding: 4px;"
        )
        path_layout.addWidget(self.path_edit)
        browse_btn = QPushButton(tr("browse_button"))
        browse_btn.clicked.connect(self.browse_for_config)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)

        # Text editor
        self.editor = QTextEdit()
        self.editor.setFont(QFont("Consolas", 12))
        self.editor.setStyleSheet(
            "background-color: #1e1e1e; border: 1px solid #3d3d3d; padding: 8px;"
        )
        self.highlighter = IniSyntaxHighlighter(self.editor.document())
        layout.addWidget(self.editor)

        # Buttons
        button_layout = QHBoxLayout()
        self.status_label = QLabel("")
        button_layout.addWidget(self.status_label)
        button_layout.addStretch()

        # A "Save" button that does NOT close the dialog
        save_btn = QPushButton(tr("save_button"))
        save_btn.clicked.connect(self.save_text_only)
        button_layout.addWidget(save_btn)

        # A "Close" button that intelligently accepts or rejects
        close_btn = QPushButton(tr("close_button"))
        close_btn.clicked.connect(self.finalize_and_close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        if self.current_path.is_file():
            self.load_config(self.current_path)
        else:
            self.editor.setPlaceholderText(
                tr("edit_config_placeholder", path=self.current_path)
            )

    def load_config(self, path: Path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.editor.setText(f.read())
            self.current_path = path
            self.path_edit.setText(str(self.current_path))
            self.status_label.setText(tr("config_loaded", path=path))
        except Exception as e:
            QMessageBox.warning(
                self, tr("load_error"), tr("load_error_msg", path=path, error=e)
            )

    def save_text_only(self):
        """Saves only the text content to the current path without closing."""
        if not self.current_path:
            QMessageBox.warning(
                self,
                tr("save_error"),
                tr("save_error_msg"),
            )
            return

        try:
            self.current_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.current_path, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
            self.status_label.setText(tr("config_saved", path=self.current_path))
            # Clear the status message after 3 seconds
            QTimer.singleShot(3000, lambda: self.status_label.setText(""))
        except Exception as e:
            QMessageBox.critical(
                self,
                tr("save_error"),
                tr("could_not_save_msg", path=self.current_path, error=e),
            )

    def finalize_and_close(self):
        """
        Closes the dialog. If the path was changed, it signals 'Accepted'
        so the main window can save the new path permanently.
        """
        if self.current_path != self.initial_path:
            # The path was changed, so signal success.
            self.accept()
        else:
            # The path was not changed, so just close normally.
            self.reject()

    def browse_for_config(self):
        start_dir = str(self.current_path.parent if self.current_path else Path.cwd())
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            tr("select_config_file"),
            start_dir,
            tr("ini_files_filter"),
        )
        if file_name:
            new_path = Path(file_name)
            self.load_config(new_path)
