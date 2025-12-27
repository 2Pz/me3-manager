# Development

> [!IMPORTANT]
> All pip instructions assume you **activate venv** first.

uv does things in venv automatically.

## Installing dev dependencies

### pip

- `requirements.txt` only includes runtime deps for the GUI app.
- `requirements-dev.txt` includes runtime deps and additional dev deps for formatting/linting and building.

```sh
pip install -r requirements-dev.txt
```

### uv

```sh
uv sync --dev
```

## Linting and formatting code

Use [ruff linter](https://docs.astral.sh/ruff/linter/) and [formatter](https://docs.astral.sh/ruff/formatter/). Currently only some basic rules are enabled in [pyproject.toml](pyproject.toml), but they may be increased later to try to catch more errors.

### pip

```sh
# Check all .py files for linter errors
ruff check
# Fix linter errors (not all errors can be fixed automatically)
ruff check --fix

# Format all .py files
ruff format

# Lint with extra rules e.g. A (builtins), B (bugbear), S (bandit)
ruff check --extend-select A,B,S
```

### uv

Add `uv run` before each `ruff` command, e.g. `uv run ruff check`

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

## Release Process

This project uses **automated releases** with conventional commits and git-cliff for changelog generation.

### Conventional Commits

All commits to `main` should follow the [Conventional Commits](https://www.conventionalcommits.org/) specification. This allows automatic changelog generation and version bumping.

#### Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

#### Types

- **feat**: New feature (bumps minor version)
- **fix**: Bug fix (bumps patch version)
- **docs**: Documentation changes
- **style**: Code style changes (formatting, missing semicolons, etc.)
- **refactor**: Code refactoring
- **perf**: Performance improvements
- **test**: Adding or updating tests
- **build**: Build system changes
- **ci**: CI/CD changes
- **chore**: Other changes (dependencies, release prep, etc.)

#### Examples

```bash
feat: add profile import/export feature
fix: resolve crash when loading invalid config
docs: update README with installation instructions
refactor: simplify profile validation logic
```

### How Releases Work

1. **Automatic detection**: When code is pushed to `main`, the release workflow checks if there are unreleased changes
2. **Version bumping**: Based on conventional commits, git-cliff determines the next version
3. **Changelog generation**: git-cliff generates a formatted changelog
4. **Build artifacts**: Linux AppImage is built (Windows build can be added)
5. **PR creation**: A pull request is automatically created with the changelog
6. **Release draft**: A GitHub release draft is created with build artifacts

### Triggering a Release

The release workflow runs automatically on every push to `main`. If there are unreleased conventional commits, it will:

1. Create a branch named `release-v<version>`
2. Create a PR to `main` with the changelog
3. Create a draft release with artifacts

To complete the release:

1. Review and merge the release PR
2. Publish the draft release on GitHub

### Manual Trigger

You can also manually trigger the release workflow from the Actions tab.

### First-Time Setup (Maintainers Only)

To use the automated release workflow, you need to create a GitHub Personal Access Token (PAT):

1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token" → "Generate new token (classic)"
3. Give it a name like "me3-manager-release"
4. Select scopes:
   - `repo` (Full control of private repositories)
   - `workflow` (Update GitHub Action workflows)
5. Click "Generate token" and copy it
6. Go to repository Settings → Secrets and variables → Actions
7. Click "New repository secret"
8. Name: `PUSH_TOKEN`
9. Value: paste your PAT
10. Click "Add secret"

This token allows the workflow to create branches, PRs, and releases on your behalf.

