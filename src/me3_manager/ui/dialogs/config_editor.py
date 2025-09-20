import re
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
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

        section_format = QTextCharFormat()
        section_format.setForeground(QColor("#569cd6"))
        section_format.setFontWeight(QFont.Weight.Bold)
        self.highlighting_rules.append((re.compile(r"\[[^\n\]]+\]"), section_format))

        key_format = QTextCharFormat()
        key_format.setForeground(QColor("#9cdcfe"))
        key_format.setFontWeight(QFont.Weight.Normal)
        self.highlighting_rules.append(
            (re.compile(r"^[^\s=;#]+(?=\s*=)", re.MULTILINE), key_format)
        )

        quoted_string_format = QTextCharFormat()
        quoted_string_format.setForeground(QColor("#ce9178"))
        self.highlighting_rules.append((re.compile(r'"[^"]*"'), quoted_string_format))
        self.highlighting_rules.append((re.compile(r"'[^']*'"), quoted_string_format))

        boolean_format = QTextCharFormat()
        boolean_format.setForeground(QColor("#569cd6"))
        boolean_format.setFontWeight(QFont.Weight.Bold)
        boolean_pattern = r"=\s*(true|false|yes|no|on|off)\s*(?:[;#]|$)"
        self.highlighting_rules.append(
            (re.compile(boolean_pattern, re.IGNORECASE | re.MULTILINE), boolean_format)
        )

        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#b5cea8"))
        number_pattern = r"=\s*([-+]?(?:\d*\.?\d+)(?:[eE][-+]?\d+)?)\s*(?:[;#]|$)"
        self.highlighting_rules.append(
            (re.compile(number_pattern, re.MULTILINE), number_format)
        )

        value_format = QTextCharFormat()
        value_format.setForeground(QColor("#d4d4d4"))
        self.highlighting_rules.append(
            (re.compile(r"=\s*([^;\r\n#]+?)(?:\s*[;#]|$)", re.MULTILINE), value_format)
        )

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6a9955"))
        comment_format.setFontItalic(True)
        self.highlighting_rules.append((re.compile(r"[;#].*"), comment_format))

        equals_format = QTextCharFormat()
        equals_format.setForeground(QColor("#d4d4d4"))
        self.highlighting_rules.append((re.compile(r"="), equals_format))

    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            for match in pattern.finditer(text):
                if match.groups():
                    start, end = match.span(1)
                else:
                    start, end = match.span()
                self.setFormat(start, end - start, format)


class ConfigEditorDialog(QDialog):
    """Dialog for editing mod INI configuration files."""

    def __init__(self, mod_name: str, config_path: Path, parent=None):
        super().__init__(parent)
        self.initial_path = config_path
        self.current_path = config_path

        self.setWindowTitle(tr("edit_config_title", mod_name=mod_name))
        self.setMinimumSize(700, 500)
        self.resize(1400, 750)
        self.setStyleSheet("background-color: #252525; color: #ffffff;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

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

        self.editor = QTextEdit()
        self.editor.setFont(QFont("Consolas", 12))
        self.editor.setStyleSheet(
            "background-color: #1e1e1e; border: 1px solid #3d3d3d; padding: 8px;"
        )
        self.highlighter = IniSyntaxHighlighter(self.editor.document())
        layout.addWidget(self.editor)

        button_layout = QHBoxLayout()
        self.status_label = QLabel("")
        button_layout.addWidget(self.status_label)
        button_layout.addStretch()

        save_btn = QPushButton(tr("save_button"))
        save_btn.clicked.connect(self.save_text_only)
        button_layout.addWidget(save_btn)

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
        if not self.current_path:
            QMessageBox.warning(self, tr("save_error"), tr("save_error_msg"))
            return
        try:
            self.current_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.current_path, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
            self.status_label.setText(tr("config_saved", path=self.current_path))
            QTimer.singleShot(3000, lambda: self.status_label.setText(""))
        except Exception as e:
            QMessageBox.critical(
                self,
                tr("save_error"),
                tr("could_not_save_msg", path=self.current_path, error=e),
            )

    def finalize_and_close(self):
        if self.current_path != self.initial_path:
            self.accept()
        else:
            self.reject()

    def browse_for_config(self):
        start_dir = str(self.current_path.parent if self.current_path else Path.cwd())
        file_name, _ = QFileDialog.getOpenFileName(
            self, tr("select_config_file"), start_dir, tr("ini_files_filter")
        )
        if file_name:
            new_path = Path(file_name)
            self.load_config(new_path)
