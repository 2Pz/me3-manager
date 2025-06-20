import re
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QTextEdit,
    QPushButton, QLabel, QFileDialog, QMessageBox,
)
from PyQt6.QtGui import QFont, QColor, QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtCore import QTimer

class IniSyntaxHighlighter(QSyntaxHighlighter):
    """Basic syntax highlighter for INI files."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []

        # Section format [Section]
        section_format = QTextCharFormat()
        section_format.setForeground(QColor("#569cd6"))
        section_format.setFontWeight(QFont.Weight.Bold)
        self.highlighting_rules.append((re.compile(r"\[[^\n\]]+\]"), section_format))

        # Key format Key=...
        key_format = QTextCharFormat()
        key_format.setForeground(QColor("#9cdcfe"))
        self.highlighting_rules.append((re.compile(r"^[^\s=;]+(?=\s*=)"), key_format))

        # Comment format ;... or #...
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6a9955"))
        comment_format.setFontItalic(True)
        self.highlighting_rules.append((re.compile(r"[;#].*"), comment_format))

    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            for match in re.finditer(pattern, text):
                self.setFormat(match.start(), match.end() - match.start(), format)

class ConfigEditorDialog(QDialog):
    """Dialog for editing mod INI configuration files."""
    def __init__(self, mod_name: str, config_path: Path, parent=None):
        super().__init__(parent)
        self.current_path = config_path
        self.new_path_selected: Optional[Path] = None # To track if user browsed for a new file

        self.setWindowTitle(f"Config Editor - {mod_name}")
        self.setMinimumSize(700, 500)
        self.setStyleSheet("background-color: #252525; color: #ffffff;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # Path display and browse
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit(str(self.current_path))
        self.path_edit.setReadOnly(True)
        self.path_edit.setStyleSheet("background-color: #2d2d2d; border: 1px solid #3d3d3d; padding: 4px;")
        path_layout.addWidget(self.path_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_for_config)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)

        # Text editor
        self.editor = QTextEdit()
        self.editor.setFont(QFont("Consolas", 10))
        self.editor.setStyleSheet("background-color: #1e1e1e; border: 1px solid #3d3d3d; padding: 8px;")
        self.highlighter = IniSyntaxHighlighter(self.editor.document())
        layout.addWidget(self.editor)

        # Buttons
        button_layout = QHBoxLayout()
        self.status_label = QLabel("")
        button_layout.addWidget(self.status_label)
        button_layout.addStretch()
        save_btn = QPushButton("Save"); save_btn.clicked.connect(self.save_config)
        button_layout.addWidget(save_btn)
        close_btn = QPushButton("Close"); close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
        
        if self.current_path.is_file():
            self.load_config(self.current_path)
        else:
            self.editor.setPlaceholderText(
                f"Config file not found at default location:\n{self.current_path}\n\n"
                "Use 'Browse...' to locate it, or 'Save' to create a new file at this path."
            )

    def load_config(self, path: Path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.editor.setText(f.read())
            self.current_path = path
            self.path_edit.setText(str(self.current_path))
            self.status_label.setText(f"Loaded: {path.name}")
        except Exception as e:
            QMessageBox.warning(self, "Load Error", f"Could not load file:\n{path}\n\nError: {e}")

    def save_config(self):
        if not self.current_path:
            QMessageBox.warning(self, "Save Error", "No config file path is set. Use 'Browse...' to select a file.")
            return
        
        try:
            # Ensure parent directory exists
            self.current_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.current_path, 'w', encoding='utf-8') as f:
                f.write(self.editor.toPlainText())
            self.status_label.setText(f"Saved: {self.current_path.name}")
            QTimer.singleShot(3000, lambda: self.status_label.setText(""))
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save file:\n{self.current_path}\n\nError: {e}")
            
    def browse_for_config(self):
        start_dir = str(self.current_path.parent if self.current_path else Path.cwd())
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select Mod Config File",
            start_dir,
            "INI Files (*.ini);;All Files (*)"
        )
        if file_name:
            new_path = Path(file_name)
            self.load_config(new_path)
            self.new_path_selected = new_path
