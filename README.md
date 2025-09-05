# Mod Engine 3 Manager

A GUI manager tool designed to simplify the use of [me3](https://me3.help/).

## Download and usage

Visit [Mod Engine 3 Manager](https://www.nexusmods.com/eldenringnightreign/mods/213) on Nexus Mods.

## Development

### Requirements

- Python 3.13
- pip or [uv](https://docs.astral.sh/uv/)

### Developer setup

#### Option 1: Classic Python setup

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

# Run the app
python main.py
```

#### Option 2: Modern setup with uv

```sh
git clone https://github.com/2Pz/me3-manager.git
cd me3-manager

# Automatically pick correct Python version, create venv,
# install dependencies, and run the app
uv run main.py
```

## Contributing

Contributions are welcome!

## License

This project is licensed under the [MIT License](LICENSE).
