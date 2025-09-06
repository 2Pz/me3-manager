"""Mod Engine 3 Manager"""

import importlib.metadata

# Get version from pyproject.toml
__version__: str = importlib.metadata.version(__name__)
