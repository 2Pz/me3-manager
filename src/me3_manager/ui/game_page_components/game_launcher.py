"""
Game Launch Handler for GamePage.

Encapsulates all logic related to launching the game, including checking for the
ME3 executable, handling custom executable paths, and constructing the command
to run the game via terminal or subprocess.
"""

import shlex
import subprocess
from typing import TYPE_CHECKING

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QMessageBox

from me3_manager.utils.platform_utils import PlatformUtils
from me3_manager.utils.translator import tr

if TYPE_CHECKING:
    from ..game_page import GamePage


class GameLauncher:
    """Handles all logic related to launching the game."""

    def __init__(self, game_page: "GamePage"):
        self.game_page = game_page
        self.config_manager = game_page.config_manager
        self.game_name = game_page.game_name

    def launch_game(self):
        """Launch the game with the configured profile and settings."""
        try:
            main_window = self.game_page.window()
            if main_window.me3_version == tr("not_installed"):
                if not self._handle_me3_not_installed():
                    return  # User aborted installation

            profile_path = self.config_manager.get_profile_path(self.game_name)
            if not profile_path.exists():
                QMessageBox.warning(
                    self.game_page,
                    tr("launch_error_title"),
                    tr("profile_not_found_msg", path=profile_path),
                )
                return

            cli_id = self.config_manager.get_game_cli_id(self.game_name)
            if not cli_id:
                QMessageBox.warning(
                    self.game_page,
                    tr("launch_error_title"),
                    tr("cli_id_not_found_msg", game_name=self.game_name),
                )
                return

            custom_exe_path = self.config_manager.get_game_exe_path(self.game_name)
            if custom_exe_path:
                self._launch_with_custom_exe(custom_exe_path, cli_id, str(profile_path))
                return

            command_args = ["me3", "launch", "--game", cli_id, "-p", str(profile_path)]
            if hasattr(main_window, "terminal"):
                self._launch_in_terminal(command_args, main_window.terminal)
            else:
                self._launch_direct(command_args)

            self.game_page._update_status(
                tr("launching_game_status", game_name=self.game_name)
            )

        except Exception as e:
            QMessageBox.warning(
                self.game_page,
                tr("launch_error_title"),
                tr("launch_game_failed_msg", error=str(e)),
            )

    def _handle_me3_not_installed(self) -> bool:
        """Shows a dialog prompting the user to install ME3 and returns if successful."""

        from me3_manager.ui.main_window import HelpAboutDialog

        reply = QMessageBox.question(
            self.game_page,
            tr("me3_not_installed_title"),
            tr("me3_required_for_launch_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            main_window = self.game_page.window()
            dialog = HelpAboutDialog(main_window, initial_setup=True)
            dialog.exec()
            main_window.refresh_me3_status()
            return main_window.me3_version != tr("not_installed")
        return False

    def _launch_with_custom_exe(self, exe_path: str, cli_id: str, profile_path: str):
        """Handles the specific logic for launching with a custom executable."""
        main_window = self.game_page.window()
        if hasattr(main_window, "terminal"):
            self.run_me3_with_custom_exe(
                exe_path,
                cli_id,
                profile_path,
                main_window.terminal,
            )
            self.game_page._update_status(
                tr("launching_with_custom_exe_status", game_name=self.game_name)
            )
        else:
            QMessageBox.information(
                self.game_page,
                tr("launch_error_title"),
                tr("custom_exe_requires_terminal_info"),
            )

    def run_me3_with_custom_exe(
        self, exe_path: str, cli_id: str, profile_path: str, terminal
    ):
        """Constructs and runs the ME3 command for a custom executable in the terminal."""
        args = [
            "launch",
            "--exe",
            exe_path,
            "--skip-steam-init",
            "--game",
            cli_id,
            "-p",
            profile_path,
        ]
        display_command = f"me3 launch --exe {shlex.quote(exe_path)} --skip-steam-init --game {cli_id} -p {shlex.quote(profile_path)}"
        terminal.output.append(f"$ {display_command}")

        if terminal.process is not None:
            terminal.process.kill()
            terminal.process.waitForFinished(1000)

        terminal.process = QProcess(terminal)
        terminal.process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels
        )
        # Sanitize environment to avoid leaking PyInstaller libs to child processes
        terminal.process.setProcessEnvironment(
            PlatformUtils.build_qprocess_environment()
        )
        terminal.process.readyReadStandardOutput.connect(terminal.handle_stdout)
        terminal.process.finished.connect(terminal.process_finished)
        # Use centralized list command prep for QProcess
        program, qargs = PlatformUtils.prepare_list_command_for_qprocess(["me3"] + args)
        terminal.process.start(program, qargs)

    def _launch_in_terminal(self, command_args, terminal):
        """Launch the game command in the integrated terminal."""
        display_command = " ".join(shlex.quote(arg) for arg in command_args)
        terminal.output.append(f"$ {display_command}")

        if terminal.process is not None:
            terminal.process.kill()
            terminal.process.waitForFinished(1000)

        terminal.process = QProcess(terminal)
        terminal.process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels
        )
        terminal.process.readyReadStandardOutput.connect(terminal.handle_stdout)
        terminal.process.finished.connect(terminal.process_finished)
        terminal.run_command(command_args, skip_display=True)

    def _launch_direct(self, command_args):
        """Launch the game command directly via a subprocess."""
        # Use centralized subprocess preparation
        prepared = PlatformUtils.prepare_command(command_args)
        subprocess.Popen(
            prepared,
            env=PlatformUtils.sanitized_env_for_subprocess(),
        )
