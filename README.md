# Mod Engine 3 Manager

[Mod Engine 3 Manager](https://www.nexusmods.com/eldenringnightreign/mods/213)  
A GUI manager tool designed to simplify the use of **Mod Engine 3**.

---

## License
This project is licensed under the [MIT License](LICENSE).

---

## Developer Setup

### Clone the repository
```bash
git clone https://github.com/2Pz/me3-manager.git
cd me3-manager
```

---

### Option 1: Classic Python Setup
```bash
# Create venv with your Python version
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

---

### Option 2: Modern Setup with uv

```bash
git clone https://github.com/2Pz/me3-manager.git
cd me3-manager

# Automatically pick correct Python version, create venv,
# install dependencies, and run the app
uv run me3-manager
```

---


## Contributing
Contributions are welcome!
