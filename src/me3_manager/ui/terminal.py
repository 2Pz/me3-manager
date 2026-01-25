import re
import shlex

from PySide6.QtCore import QProcess, QSize, QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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

        # Start Shell button
        self.shell_btn = QPushButton(tr("start_shell_button"))
        self.shell_btn.setFixedSize(80, 25)
        self.shell_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1084d9;
            }
            QPushButton:disabled {
                background-color: #3d3d3d;
                color: #888888;
            }
        """)
        self.shell_btn.clicked.connect(self.toggle_shell)
        header.addWidget(self.shell_btn)

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

        # Input field
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText(tr("terminal_input_placeholder"))
        self.input_field.setFont(QFont("Consolas", 9))
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
        """)
        self.input_field.returnPressed.connect(self.send_input)
        self.input_field.setEnabled(False)  # Disabled by default until shell starts
        layout.addWidget(self.input_field)

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
            self._kill_process()

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

        # When running a specific command (like game launch), we disable interactive input
        self.set_interactive_mode(False)

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

        # Reset UI state when process ends
        self.set_interactive_mode(False)

    def clear_output(self):
        self.output.clear()

    def closeEvent(self, event):
        """Ensure subprocess is killed when the widget is closed."""
        self._kill_process()
        super().closeEvent(event)

    def toggle_shell(self):
        """Toggle the interactive system shell."""
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            self._kill_process()
            self.output.append(tr("shell_stopped_status"))
            self.shell_btn.setText(tr("start_shell_button"))
            self.set_interactive_mode(False)
        else:
            self.start_interactive_shell()

    def start_interactive_shell(self):
        """Start an interactive system shell."""
        import sys

        self._kill_process()
        self.output.clear()

        shell_cmd = "powershell.exe" if sys.platform == "win32" else "/bin/bash"
        self.output.append(tr("starting_shell_status", shell=shell_cmd))

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.setProcessEnvironment(PlatformUtils.build_qprocess_environment())

        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.finished.connect(self.process_finished)

        self.process.start(shell_cmd)

        self.shell_btn.setText(tr("stop_shell_button"))
        self.set_interactive_mode(True)
        self.input_field.setFocus()

    def send_input(self):
        """Send text from input field to the running process."""
        if not self.process or self.process.state() != QProcess.ProcessState.Running:
            return

        text = self.input_field.text()

        # Write to process stdin
        self.process.write(f"{text}\n".encode())
        self.input_field.clear()

    def set_interactive_mode(self, enabled: bool):
        """Enable or disable interactive input controls."""
        self.input_field.setEnabled(enabled)
        if enabled:
            self.shell_btn.setText(tr("stop_shell_button"))
        else:
            self.shell_btn.setText(tr("start_shell_button"))

    def _kill_process(self):
        """Helper to kill the current process if running."""
        if self.process is not None:
            if self.process.state() == QProcess.ProcessState.Running:
                self.process.kill()
                self.process.waitForFinished(1000)
            self.process = None
