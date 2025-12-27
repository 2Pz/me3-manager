# 📜 Me3 Manager - Release History

> A comprehensive changelog for the Mod Engine 3 Manager application.
> All notable changes to this project are documented here.

## 📦 Release 1.3.0
**Released:** December 27, 2025


### ✨ New Features


- Add automated release workflow with changelog generation `[ci]`



---
## 📦 Release 1.2.3
**Released:** December 24, 2025


### ✨ New Features


- Add 'load_early' option for native modules and update UI `[mod_manager]`



### 🧹 Maintenance


- Bump version to 1.2.3



---
## 📦 Release 1.2.2
**Released:** December 13, 2025


### ✨ New Features


- Add savefile choice and apply imported profile options `[profile]`



### 🔧 Bug Fixes


- Handle unreadable mod folders during scan `[mod_manager]`



### 🧹 Maintenance


- Bump version to 1.2.2



---
## 📦 Release 1.2.1
**Released:** November 04, 2025


### ✨ New Features


- Allow disabling active regulation.bin `[mod-regulation]`


- Add external package mod support



### 🔧 Bug Fixes


- Enforce single active regulation.bin across internal and external packages `[core/mod_manager]`


- Auto-expand Game Options dialog on checkbox toggle `[ui]`


- Fix(regulation): re-activate using full path; include external packages
- Pass full mod_path to set_regulation_active to avoid “Mod folder not found”.
- Update disable_all_regulations to handle internal and tracked external packages.



---
## 📦 Release 1.2.0
**Released:** October 28, 2025


### ✨ New Features


- Add app update checker and notification



### 🔧 Bug Fixes


- Install dropped valid mod folder as a single package `[drag-drop]`


- Improve mod installation process for dropped packages `[mod-installer]`



### 🧹 Maintenance


- Bump version to 1.2.0



---
## 📦 Release 1.1.9
**Released:** October 21, 2025


### ✨ New Features


- Add profile comparison dialog


- Default installer path for ME3 executable in platform_utils.py


- Savefile warnings in Profile Settings and Game Page



### 🔧 Bug Fixes


- Steam Deck Game Mode config detection (XDG fallback + login-shell retry)


- Resolve absolute me3 path so SteamOS Game Mode detects ME3 `[linux]`



### 🧹 Maintenance


- Bump version to 1.1.9



---
## 📦 Release 1.1.8
**Released:** October 12, 2025


### ✨ New Features


- Documentation link to Help About dialog



### 🔧 Bug Fixes


- Image link



### 🧹 Maintenance


- Version to 1.1.8



---
## 📦 Release 1.1.7
**Released:** October 03, 2025


### ✨ New Features


- Add support section handling for profile versioning `[profile]`


- Add Steam integration for profile shortcuts `[profile]`


- Route updates for portable ME3 to ZIP installer `[windows]`



### 🔧 Bug Fixes


- Improve error handling for profile directory and file creation `[config]`


- Detect ME3 without admin; preserve drag-and-drop `[windows]`



### 🧹 Maintenance


- README



---
## 📦 Release 1.1.6
**Released:** September 21, 2025


### 🔧 Bug Fixes


- Enforce unique mod folders for profiles


- Use dotted key notation instead of nested tables


- Reliably open paths/dirs in PyInstaller/Flatpak builds `[linux]`


- Correct rendering position in DraggableGameButton for drag operations


- Resolve resources relative to project root or _MEIPASS


- PATH installation failure by correcting endswith() syntax


- Use canonical game slugs in me3.toml and migrate legacy keys `[config]`



### ♻️ Code Refactoring


- Migrate from PyQt6 to PySide6, update dependencies, and add export functionality



### 🧹 Maintenance


- Requirements


- Dependencies & requirements


- Version to 1.1.6 and enhance command execution in Linux environment



---
## 📦 Release 1.1.5
**Released:** September 11, 2025


### ✨ New Features


- Script to sync requirements.txt


- Cache me3 info output to improve performance



### 🔧 Bug Fixes


- Outdated types


- Wrong key in translation


- Regex for valid mod names to exclude illegal characters



### 🧹 Maintenance


- Rules



### Fix


- Save optional dependency state for Package mods



---
## 📦 Release 1.1.4
**Released:** September 11, 2025


### 🔧 Bug Fixes


- Https://github.com/2Pz/me3-manager/issues/41



### 🧹 Maintenance


- Linter rules for logging



---
## 📦 Release 1.1.3
**Released:** September 10, 2025


### ✨ New Features


- .python-version and pyproject.toml files for project configuration


- Language name to translation files and improve language retrieval logic


- Translation support for tooltips and UI strings across multiple modules


- Translations and improve UI for advanced mod options


- Ruff dev dep


- CI lint/format check


- Isort rule


- __init__.py to indicate package


- Uv entry point


- More dev instructions


- .git-blame-ignore-revs


- Rules for logging


- Logging to main.py


- Get_me3_binary_path method to PathManager and update ME3VersionManager to use it


- Validation and error handling for mod installation process



### 🔧 Bug Fixes


- Lint/format errors


- Concurrency groups


- Import paths for HelpAboutDialog and GamePage in main window and game page modules


- No module named 'winreg' on linux


- A bug with filter does not work after last refactor



### 🧹 Maintenance


- .gitignore to include AppDir contents


- README.md


- Main.py


- Build-appimage.sh


- Windows build script


- Config_facade.py


- Path_manager.py


- Translation placeholders and improve TOML config handling



### Fixes


- Steam Deck users can now launch games from both desktop and game mode again



---
## 📦 Release 1.1.2
**Released:** August 16, 2025


### ✨ New Features


- Update custom ME3 installer path to match official structure


- Add ME3 installation check before game launch



### 🔧 Bug Fixes


- UI


- Profile paths with spaces cause excessive shell quoting in launch commands


- Handle system-wide ME3 configs on Linux without permission errors



### Https


- //github.com/2Pz/me3-manager/issues/5



---
## 📦 Release 1.1.1
**Released:** August 06, 2025


### 🧹 Maintenance


- README.md


- Config_manager.py


- Mod_manager.py



---
## 📦 Release 1.1.0
**Released:** August 01, 2025


### ✨ New Features


- Add support for custom ME3 config paths in ConfigManager


- Bump version to 1.1.0


- Enhance ME3 config management with improved path validation and user options



---
## 📦 Release 1.0.9
**Released:** July 31, 2025


### ✨ New Features


- Add advanced mod options dialog and dependency management


- Implement ModManager for improved mod handling and UI integration


- Enhance command preparation for cross-platform compatibility and update game options dialog description


- Update build scripts for single executable generation and enhance game options dialog size


- Enhance primary config path retrieval and implement default config creation


- Update profile management icon to new design


- Implement installation monitoring for ME3 with version change detection


- Increase game options dialog size for better usability


- Adjust items per page spinbox range to allow a minimum of 1


- Update video links in Help dialog for platform-specific guidance and remove custom installer button


- Update settings icon to enhance visual consistency


- Increase Advanced Options dialog height for improved usability


- Enhance Game Options dialog with ME3 config file management features


- Implement expandable tree structure for mod display and enhance mod item widget


- Increase Game Options dialog width for improved layout


- Refactor ModItem layout and button styles for improved UI consistency



### 🔧 Bug Fixes


- Simplify description text in game options dialog



### 🧹 Maintenance


- Bump version to 1.0.9



---
## 📦 Release 1.0.8
**Released:** July 25, 2025


### ✨ New Features


- Implement centralized ME3 version management and update settings



### ♻️ Code Refactoring


- Improve mod syncing logic and variable naming for clarity


- Enhance syntax highlighting in profile editor for improved readability and consistency


- Remove extra spaces in TOML configuration formatting for consistency


- Clean up logging in file watcher updates for improved readability



### 🧹 Maintenance


- Update version to 1.0.8



---
## 📦 Release 1.0.7
**Released:** July 23, 2025


### ✨ New Features


- Steam deck support


- New icon assets: add, arrow-down, delete, edit, play, and settings



### 🔧 Bug Fixes


- Formatting in GamePage class to improve code readability



### 🧹 Maintenance


- Config_manager.py


- Game_page.py


- Main.py


- Main_window.py


- Binary files and clean up main.py and resource_.py


- Me3_info.py


- Game launch logic and version to 1.0.7



---
## 📦 Release Linux-0.0.1
**Released:** July 15, 2025


### 🧹 Maintenance


- Setup_linux.py


- Main_window.py



---
## 📦 Release 1.0.6
**Released:** July 14, 2025


---
[1.3.0]: https://github.com/2Pz/me3-manager/compare/1.2.3..1.3.0
[1.2.3]: https://github.com/2Pz/me3-manager/compare/1.2.2..1.2.3
[1.2.2]: https://github.com/2Pz/me3-manager/compare/1.2.1..1.2.2
[1.2.1]: https://github.com/2Pz/me3-manager/compare/1.2.0..1.2.1
[1.2.0]: https://github.com/2Pz/me3-manager/compare/1.1.9..1.2.0
[1.1.9]: https://github.com/2Pz/me3-manager/compare/1.1.8..1.1.9
[1.1.8]: https://github.com/2Pz/me3-manager/compare/1.1.7..1.1.8
[1.1.7]: https://github.com/2Pz/me3-manager/compare/1.1.6..1.1.7
[1.1.6]: https://github.com/2Pz/me3-manager/compare/1.1.5..1.1.6
[1.1.5]: https://github.com/2Pz/me3-manager/compare/1.1.4..1.1.5
[1.1.4]: https://github.com/2Pz/me3-manager/compare/1.1.3..1.1.4
[1.1.3]: https://github.com/2Pz/me3-manager/compare/1.1.2..1.1.3
[1.1.2]: https://github.com/2Pz/me3-manager/compare/1.1.1..1.1.2
[1.1.1]: https://github.com/2Pz/me3-manager/compare/1.1.0..1.1.1
[1.1.0]: https://github.com/2Pz/me3-manager/compare/1.0.9..1.1.0
[1.0.9]: https://github.com/2Pz/me3-manager/compare/1.0.8..1.0.9
[1.0.8]: https://github.com/2Pz/me3-manager/compare/1.0.7..1.0.8
[1.0.7]: https://github.com/2Pz/me3-manager/compare/Linux-0.0.1..1.0.7
[Linux-0.0.1]: https://github.com/2Pz/me3-manager/compare/1.0.6..Linux-0.0.1
[1.0.6]: https://github.com/2Pz/me3-manager/compare/1.0.5..1.0.6

