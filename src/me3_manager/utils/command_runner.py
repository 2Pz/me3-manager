from __future__ import annotations

import subprocess
import sys

from me3_manager.utils.platform_utils import PlatformUtils


class CommandRunner:
    """
    Central command execution helper.
    - Prepares commands (Flatpak-aware)
    - Runs subprocess with consistent defaults
    - Hides console windows on Windows
    """

    @staticmethod
    def prepare_command(cmd: list[str]) -> list[str]:
        return PlatformUtils.prepare_command(cmd)

    @staticmethod
    def run(
        cmd: list[str] | str,
        *,
        shell: bool = False,
        timeout: int | None = None,
        capture_output: bool = True,
        text: bool = True,
        env: dict | None = None,
        encoding: str | None = "utf-8",
        errors: str | None = "replace",
    ) -> tuple[int, str, str]:
        """
        Execute a command and return (returncode, stdout, stderr).
        """
        startupinfo = None
        if sys.platform == "win32":
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            except Exception:
                startupinfo = None

        result = subprocess.run(
            cmd,
            shell=shell,
            capture_output=capture_output,
            text=text,
            check=False,
            startupinfo=startupinfo,
            timeout=timeout,
            env=env,
            encoding=encoding,
            errors=errors,
        )

        stdout = result.stdout if result.stdout is not None else ""
        stderr = result.stderr if result.stderr is not None else ""
        return result.returncode, stdout, stderr
