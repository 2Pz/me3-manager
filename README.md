# Mod Engine 3 Manager

[![Logo](resources/icon/icon.ico)]()

A GUI manager tool designed to simplify the use of [me3](https://me3.help/).

## Download and usage

Visit [ME3 Manager Help](https://me3-manager.github.io/me3-manager-help/).

## Development

### Requirements

- Python 3.13
- (optional) [uv](https://docs.astral.sh/uv/)

### Developer setup

#### Option 1: Classic Python setup

Using [venv](https://docs.python.org/3/library/venv.html) for isolation is **strongly recommended**.

```sh
git clone https://github.com/2Pz/me3-manager.git
cd me3-manager

# Create venv
python -m venv .venv

# Activate venv
# On Linux/macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the GUI app
me3-manager
```

Our `requirements.txt` includes `-e .`, which installs the project directory as an [editable install](https://setuptools.pypa.io/en/latest/userguide/development_mode.html). You can make changes to the source code, then run `me3-manager` to see your changes immediately.

#### Option 2: Modern setup with uv

uv is much faster than pip, and will manage deps and venv for you.

```sh
git clone https://github.com/2Pz/me3-manager.git
cd me3-manager

# Run the GUI app
uv run me3-manager
```

For more development notes, tools, and building, see [DEVELOPMENT.md](DEVELOPMENT.md).

## Contributing

Contributions are welcome! Please open an [issue](https://github.com/2Pz/me3-manager/issues) if you have any questions about what to work on.

## License

This project is licensed under the [MIT License](LICENSE).
