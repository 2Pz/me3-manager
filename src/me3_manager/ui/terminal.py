import re
import shlex

from PySide6.QtCore import QProcess, QSize, QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from me3_manager.utils.platform_utils import PlatformUtils
from me3_manager.utils.resource_path import resource_path
from me3_manager.utils.translator import tr


class EmbeddedTerminal(QWidget):
    """Embedded terminal widget for running ME3 processes"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Terminal header
        header = QHBoxLayout()

        # Create icon label
        icon_label = QLabel()
        icon_label.setPixmap(
            QIcon(resource_path("resources/icon/terminal.svg")).pixmap(QSize(24, 24))
        )

        # Create title without emoji
        title = QLabel(tr("terminal_title"))
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff; margin: 4px;")

        # Add both icon and title to header
        header.addWidget(icon_label)
        header.addWidget(title)
        header.addStretch()

        # Copy button
        copy_btn = QPushButton(tr("copy_button"))
        copy_btn.setFixedSize(60, 25)
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #4d4d4d;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #5d5d5d;
            }
        """)
        copy_btn.clicked.connect(self.copy_output)
        header.addWidget(copy_btn)

        # Clear button
        clear_btn = QPushButton(tr("clear_button"))
        clear_btn.setFixedSize(60, 25)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #4d4d4d;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #5d5d5d;
            }
        """)
        clear_btn.clicked.connect(self.clear_output)
        header.addWidget(clear_btn)

        layout.addLayout(header)

        # Terminal output
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Consolas", 9))
        self.output.setStyleSheet("""
            QTextEdit {
                background-color: #0c0c0c;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        self.output.setMaximumHeight(200)
        layout.addWidget(self.output)

        self.setLayout(layout)

    def copy_output(self):
        """Copy terminal output to clipboard"""
        clipboard = QApplication.clipboard()
        # Get plain text (without HTML formatting)
        text = self.output.toPlainText()
        clipboard.setText(text)

        # Visual feedback - temporarily change button text
        copy_btn = self.sender()
        original_text = copy_btn.text()
        copy_btn.setText(tr("copied_feedback"))

        # Reset button text after 1 second
        QTimer.singleShot(1000, lambda: copy_btn.setText(original_text))

    def parse_ansi_to_html(self, text: str) -> str:
        """Converts text with ANSI escape codes to HTML for display in QTextEdit."""
        ansi_colors = {
            "30": "black",
            "31": "#CD3131",
            "32": "#0DBC79",
            "33": "#E5E510",
            "34": "#2472C8",
            "35": "#BC3FBC",
            "36": "#11A8CD",
            "37": "#E5E5E5",
            "90": "#767676",
        }

        ansi_escape_pattern = re.compile(r"(\x1B\[((?:\d|;)*)m)")
        parts = ansi_escape_pattern.split(text)
        html_output = ""
        in_span = False

        i = 0
        while i < len(parts):
            text_part = parts[i]

            text_part = text_part.replace("&", "&").replace("<", "<").replace(">", ">")
            text_part = text_part.replace("\n", "<br>")
            html_output += text_part

            i += 1
            if i >= len(parts):
                break

            codes_str = parts[i + 1]

            if in_span:
                html_output += "</span>"
                in_span = False

            codes = codes_str.split(";")
            if not codes or codes[0] in ("", "0"):
                pass  # Span is already closed
            else:
                styles = []
                for code in codes:
                    if code in ansi_colors:
                        styles.append(f"color:{ansi_colors.get(code)};")
                    elif code == "1":
                        styles.append("font-weight:bold;")
                    elif code == "2":
                        styles.append("opacity:0.7;")
                    elif code == "3":
                        styles.append("font-style:italic;")
                    elif code == "4":
                        styles.append("text-decoration:underline;")

                if styles:
                    html_output += f'<span style="{"".join(styles)}">'
                    in_span = True

            i += 2

        if in_span:
            html_output += "</span>"

        return html_output

    def run_command(self, command, working_dir: str = None, skip_display: bool = False):
        """Run a command in the embedded terminal

        Args:
            command: Either a string command or list of arguments
            working_dir: Optional working directory
            skip_display: Skip displaying the command (already displayed elsewhere)
        """

        # Handle both string commands and argument lists
        if isinstance(command, str):
            display_command = command
            is_legacy_string = True
        else:
            display_command = " ".join(shlex.quote(arg) for arg in command)
            is_legacy_string = False

        # Only display if not skipped
        if not skip_display:
            self.output.append(f"$ {display_command}")

        if self.process is not None:
            self.process.kill()
            self.process.waitForFinished(1000)

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        # Sanitize environment to avoid leaking PyInstaller libs to child processes
        self.process.setProcessEnvironment(PlatformUtils.build_qprocess_environment())
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.finished.connect(self.process_finished)

        if working_dir:
            self.process.setWorkingDirectory(working_dir)

        if is_legacy_string:
            program, args = PlatformUtils.prepare_string_command_for_qprocess(command)
            self.process.start(program, args)
        else:
            # Handle new argument list format (use centralized list prep)
            program, args = PlatformUtils.prepare_list_command_for_qprocess(command)
            self.process.start(program, args)

    def handle_stdout(self):
        cursor = self.output.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.output.setTextCursor(cursor)

        # Since streams are merged, this now reads both stdout and stderr
        data = self.process.readAllStandardOutput()
        stdout = bytes(data).decode("utf8", errors="ignore")

        html_content = self.parse_ansi_to_html(stdout)
        self.output.insertHtml(html_content)

        cursor.movePosition(cursor.MoveOperation.End)
        self.output.setTextCursor(cursor)

    def process_finished(self, exit_code, exit_status):
        if exit_code == 0:
            self.output.append(tr("process_success_status"))
        else:
            self.output.append(
                tr("process_finished_with_code_status", exit_code=exit_code)
            )

    def clear_output(self):
        self.output.clear()
