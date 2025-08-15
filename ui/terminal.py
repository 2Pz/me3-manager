import sys
import re
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QApplication
from PyQt6.QtGui import QFont
from PyQt6.QtCore import QProcess
import shlex

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
        title = QLabel("🖥 Terminal")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff; margin: 4px;")
        header.addWidget(title)
        
        header.addStretch()
        
        # Copy button
        copy_btn = QPushButton("Copy")
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
        clear_btn = QPushButton("Clear")
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
        copy_btn.setText("Copied!")
        
        # Reset button text after 1 second
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1000, lambda: copy_btn.setText(original_text))

    def parse_ansi_to_html(self, text: str) -> str:
        """Converts text with ANSI escape codes to HTML for display in QTextEdit."""
        ansi_colors = {
            '30': 'black', '31': '#CD3131', '32': '#0DBC79', '33': '#E5E510',
            '34': '#2472C8', '35': '#BC3FBC', '36': '#11A8CD', '37': '#E5E5E5',
            '90': '#767676',
        }
        
        ansi_escape_pattern = re.compile(r'(\x1B\[((?:\d|;)*)m)')
        parts = ansi_escape_pattern.split(text)
        html_output = ""
        in_span = False
        
        i = 0
        while i < len(parts):
            text_part = parts[i]

            text_part = text_part.replace('&', '&').replace('<', '<').replace('>', '>')
            text_part = text_part.replace('\n', '<br>')
            html_output += text_part
            
            i += 1
            if i >= len(parts): break
                
            codes_str = parts[i+1]
            
            if in_span:
                html_output += "</span>"
                in_span = False
                
            codes = codes_str.split(';')
            if not codes or codes[0] in ('', '0'):
                pass # Span is already closed
            else:
                styles = []
                for code in codes:
                    if code in ansi_colors:
                        styles.append(f'color:{ansi_colors.get(code)};')
                    elif code == '1':
                        styles.append('font-weight:bold;')
                    elif code == '2':
                        styles.append('opacity:0.7;')
                    elif code == '3':
                        styles.append('font-style:italic;')
                    elif code == '4':
                        styles.append('text-decoration:underline;')
                
                if styles:
                    html_output += f'<span style="{"".join(styles)}">'
                    in_span = True
                    
            i += 2 
            
        if in_span:
            html_output += "</span>"
            
        return html_output
    
    def run_command(self, command, working_dir: str = None):
        """Run a command in the embedded terminal
        
        Args:
            command: Either a string command or list of arguments
            working_dir: Optional working directory
        """
        import os
        
        # Handle both string commands and argument lists
        if isinstance(command, str):
            # Legacy string command - display as-is
            display_command = command
            is_legacy_string = True
        else:
            # New argument list - display nicely quoted
            display_command = " ".join(shlex.quote(arg) for arg in command)
            is_legacy_string = False
        
        self.output.append(f"$ {display_command}")
        
        if self.process is not None:
            self.process.kill()
            self.process.waitForFinished(1000)
        
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.finished.connect(self.process_finished)
        
        if working_dir:
            self.process.setWorkingDirectory(working_dir)

        if is_legacy_string:
            # Handle legacy string commands with shell
            if sys.platform == "win32":
                self.process.start("cmd", ["/c", command])
            else:
                # Check if we're running in Flatpak
                is_flatpak = os.path.exists("/.flatpak-info") or "/app/" in os.environ.get("PATH", "")

                if is_flatpak:
                    # Use flatpak-spawn to run on host with proper environment
                    user_home = os.path.expanduser("~")
                    me3_path = f"{user_home}/.local/bin/me3"
                    
                    # Construct command with full path to me3
                    if command.startswith("me3 "):
                        host_command = command.replace("me3 ", f"{me3_path} ", 1)
                    else:
                        host_command = command
                    
                    full_command = f"flatpak-spawn --host bash -l -c '{host_command}'"
                    self.process.start("bash", ["-c", full_command])
                    self.output.append("Running command on host system via flatpak-spawn...")
                else:
                    # Get environment from login shell
                    from PyQt6.QtCore import QProcessEnvironment
                    import subprocess
                    
                    try:
                        result = subprocess.run(
                            ["bash", "-l", "-c", "env"], 
                            capture_output=True, 
                            text=True, 
                            timeout=10
                        )
                        if result.returncode == 0:
                            env = QProcessEnvironment()
                            for line in result.stdout.strip().split('\n'):
                                if '=' in line:
                                    key, value = line.split('=', 1)
                                    env.insert(key, value)
                        else:
                            env = QProcessEnvironment.systemEnvironment()
                    except:
                        env = QProcessEnvironment.systemEnvironment()
                    
                    self.process.setProcessEnvironment(env)
                    self.process.start("bash", ["-l", "-c", command])
        else:
            # Handle new argument list format - direct execution, no shell needed
            program = command[0]
            args = command[1:] if len(command) > 1 else []
            
            if sys.platform != "win32":
                # Check if we're running in Flatpak on Linux
                is_flatpak = os.path.exists("/.flatpak-info") or "/app/" in os.environ.get("PATH", "")
                
                if is_flatpak and program == "me3":
                    # Use flatpak-spawn for me3 commands
                    user_home = os.path.expanduser("~")
                    me3_path = f"{user_home}/.local/bin/me3"
                    flatpak_args = ["flatpak-spawn", "--host", me3_path] + args
                    self.process.start("flatpak-spawn", flatpak_args[1:])
                    self.output.append("Running command on host system via flatpak-spawn...")
                else:
                    # Set up environment for non-flatpak Linux
                    from PyQt6.QtCore import QProcessEnvironment
                    import subprocess
                    
                    try:
                        result = subprocess.run(
                            ["bash", "-l", "-c", "env"], 
                            capture_output=True, 
                            text=True, 
                            timeout=10
                        )
                        if result.returncode == 0:
                            env = QProcessEnvironment()
                            for line in result.stdout.strip().split('\n'):
                                if '=' in line:
                                    key, value = line.split('=', 1)
                                    env.insert(key, value)
                            self.process.setProcessEnvironment(env)
                    except:
                        pass  # Use default environment
                    
                    self.process.start(program, args)
            else:
                # Windows - direct execution
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
            self.output.append("Process completed successfully.")
        else:
            self.output.append(f"Process finished with exit code: {exit_code}")
    
    def clear_output(self):
        self.output.clear()