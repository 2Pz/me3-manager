Mod Engine 3 Manager
![alt text](https://img.shields.io/badge/license-MIT-blue.svg)

![alt text](https://img.shields.io/badge/python-3.8+-brightgreen.svg)

![alt text](https://img.shields.io/badge/UI-PyQt6-orange.svg)
A modern, intuitive graphical user interface (GUI) for managing mods for games that use Mod Engine 3. This tool simplifies the process of installing, enabling, disabling, and configuring your mods, getting you back in the game faster.
This application is designed to work with the standard Mod Engine 3 file structure and provides a seamless experience for managing mods for games like Elden Ring and Nightreign.
(Please replace this with a real screenshot of your application)
✨ Features
Multi-Game Support: Easily switch between different game profiles (Elden Ring and Nightreign supported out-of-the-box).
One-Click Toggles: Enable or disable any mod with a single click of a button.
Drag & Drop Installation: Simply drag your .dll mod files onto the application window to install them.
External Mod Support: Add and manage mods located anywhere on your system, not just in the default mods folder.
Built-in Config Editor: Edit mod .ini configuration files directly within the manager, complete with syntax highlighting.
Embedded Terminal: Launch your game and see the real-time output from Mod Engine 3 directly within the manager window.
Easy File Access: Quickly open the game's mods folder or an external mod's folder in your file explorer.
Mod Search: Instantly find the mod you're looking for with a built-in search bar.
Modern Dark UI: A clean, modern, and easy-to-use interface.
🚀 Getting Started
There are two ways to get the Mod Engine 3 Manager running: using the Python script or downloading a pre-compiled release.
Prerequisites
Python 3.8+ (if running from source).
Mod Engine 3 installed in its default location. The manager assumes ME3 and its configuration files are located at %LocalAppData%\garyttierney\me3.
Option 1: Running from Source (for Developers)
Clone the repository:
Generated sh
git clone https://github.com/your-username/mod-engine-3-manager.git
cd mod-engine-3-manager
Use code with caution.
Sh
Create a virtual environment (recommended):
Generated sh
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
Use code with caution.
Sh
Install the required dependencies:
Generated sh
pip install -r requirements.txt
Use code with caution.
Sh
Run the application:
Generated sh
python mainbackup.py
Use code with caution.
Sh
Option 2: Pre-compiled Release (for Users)
The easiest way to get started is to download the latest pre-compiled version.
Go to the Releases page of this repository.
Download the .zip or .exe file from the latest release.
Extract the contents and run ModEngine3Manager.exe.
📖 How to Use
Launch the Manager: Start the application.
Select a Game: Click on "Elden Ring" or "Nightreign" in the left sidebar to load the mods for that game.
Install Mods:
Drag & Drop: Drag one or more mod .dll files onto the main window.
Add External: Click the ➕ button to browse for a .dll file located anywhere on your computer.
Manage Mods:
Enable/Disable: Click the power button ⏻ next to a mod's name. Green means enabled, red means disabled.
Edit Config: Click the gear icon ⚙️ to open the built-in editor for the mod's config.ini file. If the file doesn't exist, you can create and save it.
Delete: Click the trash can 🗑 to remove a mod from the list and delete its file (if it's not an external mod).
Launch the Game: Click the big 🚀 Launch [Game Name] button to start the game with your selected mods active. You can monitor the output from Mod Engine 3 in the terminal at the bottom.
🔧 Configuration
The application works by reading and writing to the standard Mod Engine 3 profile files (.me3 files).
ME3 Profiles Location: C:\Users\<YourUser>\AppData\Local\garyttierney\me3\config\profiles
Game Mods Folders:
Elden Ring: ...\profiles\eldenring-mods
Nightreign: ...\profiles\nightreign-mods
Manager Settings: The manager stores custom paths for mod config files in ...\me3\config\manager_settings.json.
🤝 Contributing
Contributions are welcome! If you have an idea for a new feature or have found a bug, please feel free to contribute.
Open an Issue: Discuss the change you wish to make by creating an issue first.
Fork the Repository: Create your own fork of the project.
Create a Branch: git checkout -b feature/AmazingFeature
Commit Your Changes: git commit -m 'Add some AmazingFeature'
Push to the Branch: git push origin feature/AmazingFeature
Open a Pull Request: Submit a pull request back to the main repository.
