#!/usr/bin/sh

# Sync from pyproject.toml to pip-style requirements files
#
# Usage:
# Run from project root:
# $ ./scripts/sync-requirements.sh

# Export runtime deps to requirements.txt
uv export --no-hashes --format=requirements.txt --output-file=requirements.txt --quiet &&
	echo "Synced requirements.txt"

# Export runtime + dev deps to requirements-dev.txt
uv export --group dev --no-hashes --format=requirements.txt --output-file=requirements-dev.txt --quiet &&
	echo "Synced requirements-dev.txt"
