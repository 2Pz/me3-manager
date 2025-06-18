import sys
from cx_Freeze import setup, Executable
import os
from version import VERSION


import warnings
warnings.filterwarnings("ignore", category=SyntaxWarning)



# Include necessary files without including source code
include_files = [
    ('resources/', 'resources/'),
]

# Add additional options like packages and excludes
build_exe_options = {
    'packages': ['PyQt6'],  
    'excludes': [],  # Exclude any unused packages
    'include_files': include_files,
    'zip_include_packages': ['*'],  # Compress packages into a zip file
    'zip_exclude_packages': [],     # Exclude no packages from the zip file
    'build_exe': f'build/Me3_Manager_{VERSION}',  # Customize build output path
    'optimize': 2  # Optimize .pyc files (2 strips docstrings)
}

# Base for the executable
base = None
if sys.platform == 'win32':
    base = 'Win32GUI' # base = 'Win32GUI'   Hide the console for production GUI apps

# Define the main executable
executables = [
    Executable(
        'main.py',  # The main script of your project
        base=base,
        target_name=f'Me3_Manager.exe',  # Output executable name
        icon='resources/icon/icon.ico'  # Path to the icon file
    )
]

# Setup configuration
setup(
    name=f'Me3_Manager_{VERSION}',
    version=VERSION,
    description='Mod Engine 3 Manager',
    options={'build_exe': build_exe_options},
    executables=executables
)

# python setup.py build
