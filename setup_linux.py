import sys
import os
from cx_Freeze import setup, Executable
from version import VERSION
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning)

# Include data files (like icons, resources, etc.)
include_files = [
    ('resources/', 'resources/'),
]

# Define cx_Freeze build options for Linux
build_exe_options = {
    'packages': [],
    'excludes': [],
    'include_files': include_files,
    'zip_include_packages': ['*'],
    'zip_exclude_packages': [],
    'build_exe': f'build/Me3_Manager_{VERSION}',
    'optimize': 2
}

# Linux doesn't use base='Win32GUI'
base = None

# Define output executable name
target_name = 'Me3_Manager'

# Define the main executable
executables = [
    Executable(
        'main.py',
        base=base,
        target_name=target_name,
        icon=None  # Linux usually doesn't bundle icons into the binary
    )
]

# Setup configuration
setup(
    name=f'Me3_Manager_{VERSION}',
    version=VERSION,
    description='Mod Engine 3 Manager (Linux)',
    options={'build_exe': build_exe_options},
    executables=executables
)

# python setup_linux.py build
