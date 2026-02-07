import argparse
import logging
import subprocess
import sys

from me3_manager.utils.platform_utils import PlatformUtils

log = logging.getLogger(__name__)


def handle_cli_args():
    """
    Parse and handle command line arguments for direct game launching.
    Returns:
        bool: True if arguments were handled and the program should exit, False otherwise.
    """
    parser = argparse.ArgumentParser(description="Mod Engine 3 Manager")
    parser.add_argument("--launch-game", help="Launch a game by its CLI ID")
    parser.add_argument("--profile", help="Path to the profile to use")

    # Use parse_known_args to allow other potential qt args or future flags
    args, unknown = parser.parse_known_args()

    if args.launch_game:
        _launch_game(args.launch_game, args.profile)
        return True

    return False


def _launch_game(game_cli_id: str, profile_path: str):
    """
    Launch the game using the me3 CLI.
    """
    # Resolve me3 executable
    me3_exe = None
    if sys.platform == "win32":
        me3_exe = PlatformUtils._find_me3_executable_windows()
    else:
        me3_exe = PlatformUtils._find_me3_executable_linux()

    if not me3_exe:
        log.error("Could not find Mod Engine 3 executable")
        sys.exit(1)

    # Build launch command
    # me3 launch --game <id> -p <profile>
    cmd = [me3_exe, "launch", "--game", game_cli_id]
    if profile_path:
        cmd.extend(["-p", profile_path])

    # Prepare and run
    # We use sanitized_env_for_subprocess to ensure we don't leak PyInstaller/Qt libs
    # to the game process, which mimics how the GUI launches it.
    try:
        prepared_cmd = PlatformUtils.prepare_command(cmd)
        env = PlatformUtils.sanitized_env_for_subprocess()

        log.info("Launching game via CLI wrapper: %s", prepared_cmd)

        # Using subprocess.run to wait for the process
        subprocess.run(prepared_cmd, env=env, check=True)
        sys.exit(0)
    except subprocess.CalledProcessError as e:
        log.error("Game launch failed with code %d", e.returncode)
        sys.exit(e.returncode)
    except Exception as e:
        log.error("Failed to launch game: %s", e)
        sys.exit(1)
