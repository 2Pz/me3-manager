import os
import subprocess
import sys
from pathlib import Path

from me3_manager.utils.platform_utils import PlatformUtils


class SteamService:
    """
    Simple helper for launching Steam if available.
    Best-effort, silent; returns True if a launch attempt was made without error.
    """

    def is_running(self) -> bool:
        """Return True if a Steam process appears to be running."""
        try:
            if sys.platform == "win32":
                try:
                    out = subprocess.run(
                        ["tasklist"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        text=True,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                    return "steam.exe" in out.stdout.lower()
                except Exception:
                    return False

            names = ["steam", "com.valvesoftware.Steam"]
            for name in names:
                try:
                    res = subprocess.run(
                        ["pgrep", "-f", name],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    if res.returncode == 0:
                        return True
                except FileNotFoundError:
                    pass
                except Exception:
                    pass

                try:
                    res = subprocess.run(
                        ["pidof", name],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    if res.returncode == 0:
                        return True
                except FileNotFoundError:
                    pass
                except Exception:
                    pass

            try:
                for pid in os.listdir("/proc"):
                    if not pid.isdigit():
                        continue
                    cmdline_path = f"/proc/{pid}/cmdline"
                    try:
                        with open(cmdline_path, "rb") as f:
                            data = f.read().decode(errors="ignore").lower()
                            if "steam" in data:
                                return True
                    except Exception:
                        continue
            except Exception:
                pass

            return False
        except Exception:
            return False

    def launch(self, steam_path: Path | None = None) -> bool:
        """
        Best-effort Steam launch across platforms and packaging (Flatpak).
        - Windows: use provided path or "steam" on PATH
        - Linux/macOS: try provided path, then "steam -silent", then Flatpak app id
        Returns True if a launch attempt was successfully started.
        """
        try:
            # Avoid launching if already running to prevent popup/focus
            if self.is_running():
                return True

            if sys.platform == "win32":
                startupinfo = None
                try:
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                except Exception:
                    startupinfo = None

                # Prefer explicit path
                if steam_path and steam_path.exists():
                    subprocess.Popen([str(steam_path)], startupinfo=startupinfo)
                    return True

                # Fallback to PATH
                subprocess.Popen(["steam"], startupinfo=startupinfo)
                return True

            # Non-Windows: build candidate commands
            candidates: list[list[str]] = []
            if steam_path and steam_path.exists():
                candidates.append([str(steam_path), "-silent"])  # explicit path
            candidates.append(["steam", "-silent"])  # PATH
            candidates.append(
                ["flatpak", "run", "com.valvesoftware.Steam", "-silent"]
            )  # Flatpak

            for cmd in candidates:
                try:
                    prepared = PlatformUtils.prepare_command(cmd)
                    subprocess.Popen(
                        prepared,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        env=PlatformUtils.sanitized_env_for_subprocess(),
                    )
                    return True
                except FileNotFoundError:
                    continue
                except Exception:
                    continue

            return False
        except Exception:
            return False
