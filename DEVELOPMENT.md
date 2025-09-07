# Development

## Installing dev dependencies

### pip

- `requirements.txt` only includes runtime deps for the GUI app.
- `requirements-dev.txt` includes runtime deps and additional dev deps for formatting/linting and building.

```sh
# Make sure venv is activated first
# Install dev deps
pip install -r requirements-dev.txt
```

### uv

```sh
# Install dev deps
uv sync --dev
```

## Linting and formatting code

Use [ruff](https://docs.astral.sh/ruff/) to lint and format. Currently only some basic rules are enabled in [pyproject.toml](pyproject.toml), but they may be increased later to try to catch more errors.

### pip

```sh
# Check for linter errors
ruff check
# Format files immediately
ruff format
```

### uv

```sh
# Check for linter errors
uv run ruff check
# Format files immediately
uv run ruff format
```

## Testing

TODO

## Building

- Builds must be done on their target platforms, e.g. build for Linux on Linux, build for Windows on Windows.
- `build/` is for temporary build files and can be cleaned by any build script/tool before building. Do not rely on specific files being there.
- `dist/` is for built artifacts (ready for usage/distribution). Build scripts/tools should not remove any files here, although they may _overwrite_ files with a new build.
- Build scripts should place the final output in `dist/$os-$version/` e.g. `dist/linux-1.1.2/me3-manager`
- Internal name of the app is always `me3-manager` (or `me3_manager` when referring to the Python module). Only user-facing name will use Me3 Manager.

### pip

```sh
# Build on Linux using pyinstaller
./build-linux.sh
# Package as AppImage
./package-linux.sh

# Build on Windows using cx_freeze
python ./build-windows.py build
```

### uv

```sh
# Build on Linux using pyinstaller
uv run ./build-linux.sh
# Package as AppImage
./package-linux.sh

# Build on Windows using cx_freeze
uv run ./build-windows.py build
```
