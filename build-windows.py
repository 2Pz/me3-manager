"""Build script for Windows.

Usage with uv:
    uv sync --dev
    uv run ./build-windows.py build

Usage with pip (activate venv first):
    pip install -r requirements-dev.txt
    python build-windows.py build
"""

import sys
import warnings
from pathlib import Path

import tomlkit
from cx_Freeze import Executable, setup

# Get version from pyproject.toml instead of importing me3_manager
# This is more robust in CI environments.
pyproject_path = Path(__file__).parent / "pyproject.toml"
pyproject_content = pyproject_path.read_text(encoding="utf-8")
pyproject_data = tomlkit.parse(pyproject_content)
VERSION = pyproject_data["project"]["version"]  # type: ignore[index]

warnings.filterwarnings("ignore", category=SyntaxWarning)

if sys.platform != "win32":
    sys.exit("This script must be run on Windows to build a Windows binary.")

# Include necessary files without including source code
include_files = [
    ("resources/", "resources/"),
]

# Add additional options like packages and excludes
build_exe_options = {
    # Packages are auto-detected from our imports, we shouldn't need to specify
    # "PyQt6" here.
    "packages": [],
    # Force exclude packages if needed
    "excludes": [],
    "include_files": include_files,
    # Compress all packages into a zip file if possible
    "zip_include_packages": ["*"],
    # Exclude no packages from the zip file
    "zip_exclude_packages": [],
    # Output dir for built executables and dependencies. We use an extra dir
    # because the Windows build is not a single file; this makes it easier to
    # package the Me3_Manager_VERSION dir inside a zip in CI.
    "build_exe": f"dist/windows-{VERSION}/Me3_Manager_{VERSION}",
    # Optimize .pyc files (2 strips docstrings)
    "optimize": 2,
}

# Base for the executable
base = None
if sys.platform == "win32":
    # Hide the console for production GUI apps
    base = "Win32GUI"

# Define the main executable
executables = [
    Executable(
        # The main script of your project
        "src/me3_manager/main.py",
        base=base,
        # Output executable name (without extension)
        target_name="Me3_Manager",
        # Path to the icon file
        icon="resources/icon/icon.ico",
    )
]

# Setup configuration
setup(
    name="Me3 Manager",
    version=VERSION,
    description="Mod Engine 3 Manager",
    options={"build_exe": build_exe_options},
    executables=executables,
)
