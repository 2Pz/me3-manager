# 📜 Me3 Manager - Release History

> A comprehensive changelog for the Mod Engine 3 Manager application.
> All notable changes to this project are documented here.

## 📦 Release 1.3.1
**Released:** January 22, 2026


### 🔧 Bug Fixes

- UI text readability at low scale factors ([8fa6473](https://github.com/2Pz/me3-manager/commit/8fa6473dbabe1f5878ba6d85d40b16343faee251))

- Fix(ci) resolve broken pipe in changelog extraction and partial version matching ([98c9218](https://github.com/2Pz/me3-manager/commit/98c9218669f40e9b9afcd6c068a0b5d098c8373a))



---
## 📦 Release 1.3.0
**Released:** January 18, 2026


### ✨ New Features

- Nexus API support, refactor mod installation, and improve UI ([1683359](https://github.com/2Pz/me3-manager/commit/168335937b4121632b585b86ffc8d361076a3eaf))

- Nexus UI overhaul with SSO login, avatar display, and mod search ([e3d7eba](https://github.com/2Pz/me3-manager/commit/e3d7ebac7e28b1a1e4ee3aac128df9b704f1d638))

- Browser download watcher fallback for Nexus installs ([7db77f3](https://github.com/2Pz/me3-manager/commit/7db77f3f6e6dc26bf29b9a67566d8fa3fb23d8db))

- Auto-check mod updates on startup `[nexus]` ([322dcb3](https://github.com/2Pz/me3-manager/commit/322dcb37ef9f3951f6f40afb31f70d984f118298))

- Add multi-archive format support (ZIP, RAR, 7z, and more) ([e721fd9](https://github.com/2Pz/me3-manager/commit/e721fd9dda806085347c9b851ff333f3649a0e96))

- Mods rename `[mods]` ([9539ac0](https://github.com/2Pz/me3-manager/commit/9539ac0fca06391140d60382361a430e4277aaaf))



### 🔧 Bug Fixes

- Ci.yml ([bf854db](https://github.com/2Pz/me3-manager/commit/bf854db71bfa98474eeb47a45f9eb949a29fb2f5))

- Auto-launch steam silently on app startup ([28dcf3c](https://github.com/2Pz/me3-manager/commit/28dcf3c2cd136e84fb11cc12a369005bd88b6b71))

- Permissive mod detection and validation ([d6d1d06](https://github.com/2Pz/me3-manager/commit/d6d1d067f369cbadc38282c909ca9ceed493ca41))

- Prevent sidebar mod details from being clipped when mod list shrinks ([956f66d](https://github.com/2Pz/me3-manager/commit/956f66d80b4795809c130bb26766512de6603d61))

- Auto-correct game executable names on startup and improve translation clarity ([483bc42](https://github.com/2Pz/me3-manager/commit/483bc4223c5623efa6a66d1fa93670261ab88e27))

- Fix check-unused-translations.py ([dfbefaa](https://github.com/2Pz/me3-manager/commit/dfbefaa4d1f8d639e559cc9886d529c355bf0502))

- URL opening in AppImage ([f43b2a8](https://github.com/2Pz/me3-manager/commit/f43b2a87d2a93659040005754a08f4d3d0cf7d97))



### 🎨 User Interface

- Implement user-configurable UI scaling ([9c9985f](https://github.com/2Pz/me3-manager/commit/9c9985fbe17a1997bda5ceb94526048805caa368))



### ♻️ Code Refactoring

- Eliminate all duplicate code detected ([86a805a](https://github.com/2Pz/me3-manager/commit/86a805a7da9d72f9bc5794ccfba33579511c3bce))



### 🧹 Maintenance

- Documentation link to the new GitHub Pages URL. ([6ac2331](https://github.com/2Pz/me3-manager/commit/6ac23319611ea180731229e2f93b889af11e9234))

- Add unused translation key checker ([272ee8a](https://github.com/2Pz/me3-manager/commit/272ee8a7fa274b0e1f6f335e259ce3a9e0dc6856))



---
## 📦 Release 1.2.3
**Released:** December 24, 2025


### ✨ New Features

- Add 'load_early' option for native modules and update UI `[mod_manager]` ([1635624](https://github.com/2Pz/me3-manager/commit/16356242e22c2be75a6c0bbda6a5f086274dd7dd))



### 🧹 Maintenance

- Bump version to 1.2.3 ([20a0748](https://github.com/2Pz/me3-manager/commit/20a0748c3b19b4948d26f03eab54cf7b68e35bde))



---
## 📦 Release 1.2.2
**Released:** December 13, 2025


### ✨ New Features

- Add savefile choice and apply imported profile options `[profile]` ([6152074](https://github.com/2Pz/me3-manager/commit/6152074d6b5ddbee63657371516ecd86667f423b))



### 🔧 Bug Fixes

- Handle unreadable mod folders during scan `[mod_manager]` ([69c40a7](https://github.com/2Pz/me3-manager/commit/69c40a7121b29720fb5f72c3387eeeeeb809d96e))



### 🧹 Maintenance

- Bump version to 1.2.2 ([80721ec](https://github.com/2Pz/me3-manager/commit/80721ec9b6e6debca8a18b89c9429c52210b9408))



---
## 📦 Release 1.2.1
**Released:** November 04, 2025


### ✨ New Features

- Allow disabling active regulation.bin `[mod-regulation]` ([a1ebba6](https://github.com/2Pz/me3-manager/commit/a1ebba653184b3b5f2beb7760478a566697866a4))

- Add external package mod support ([0b89e5c](https://github.com/2Pz/me3-manager/commit/0b89e5c9801d6c47a1a82235cc4d116a63a0c9d9))



### 🔧 Bug Fixes

- Enforce single active regulation.bin across internal and external packages `[core/mod_manager]` ([13dfe71](https://github.com/2Pz/me3-manager/commit/13dfe714903b1faee6f00f610965f381f13d9c02))

- Auto-expand Game Options dialog on checkbox toggle `[ui]` ([43cd608](https://github.com/2Pz/me3-manager/commit/43cd608abb9f3720e56d63c5b8da3d9e67c57cff))

- Fix(regulation): re-activate using full path; include external packages
- Pass full mod_path to set_regulation_active to avoid “Mod folder not found”.
- Update disable_all_regulations to handle internal and tracked external packages. ([9253d7f](https://github.com/2Pz/me3-manager/commit/9253d7fd6bd5f7384dfcf76d22d3a95fc52157fa))



---
## 📦 Release 1.2.0
**Released:** October 28, 2025


### ✨ New Features

- Add app update checker and notification ([02a1c61](https://github.com/2Pz/me3-manager/commit/02a1c61faf06dc71a2ea503968522a459730e3be))



### 🔧 Bug Fixes

- Install dropped valid mod folder as a single package `[drag-drop]` ([64eb795](https://github.com/2Pz/me3-manager/commit/64eb7955821eae33514b71f4555ebe6b818e0bd5))

- Improve mod installation process for dropped packages `[mod-installer]` ([146a762](https://github.com/2Pz/me3-manager/commit/146a7624c6504867a3115813adf4fba1b467583e))



### 🧹 Maintenance

- Bump version to 1.2.0 ([c3c97b6](https://github.com/2Pz/me3-manager/commit/c3c97b633bc8016fc5a71474ff1cf18e83d21f92))



---
## 📦 Release 1.1.9
**Released:** October 21, 2025


### ✨ New Features

- Add profile comparison dialog ([d764dd4](https://github.com/2Pz/me3-manager/commit/d764dd4e624d1ef3ce8cf2a6684f333e16e4795c))

- Default installer path for ME3 executable in platform_utils.py ([85dba18](https://github.com/2Pz/me3-manager/commit/85dba18bde99ffb58af9103f0272cc9adbd83d6a))

- Savefile warnings in Profile Settings and Game Page ([bdc2147](https://github.com/2Pz/me3-manager/commit/bdc21476e4161e8cd41020593a704e6441fb83e7))



### 🔧 Bug Fixes

- Steam Deck Game Mode config detection (XDG fallback + login-shell retry) ([dbc09e8](https://github.com/2Pz/me3-manager/commit/dbc09e8149c9dd98c58b60a331fb1318e299756a))

- Resolve absolute me3 path so SteamOS Game Mode detects ME3 `[linux]` ([fd4b536](https://github.com/2Pz/me3-manager/commit/fd4b536d92186075d4c83b865f810896823f196f))



### 🧹 Maintenance

- Bump version to 1.1.9 ([103acd7](https://github.com/2Pz/me3-manager/commit/103acd71ba0f3ed67e87bbe6a4ba9b1388951305))



---
## 📦 Release 1.1.8
**Released:** October 12, 2025


### ✨ New Features

- Documentation link to Help About dialog ([752eaf6](https://github.com/2Pz/me3-manager/commit/752eaf6c35af45f4048a55b37f64add8d4acbc24))



### 🔧 Bug Fixes

- Image link ([b0dca0a](https://github.com/2Pz/me3-manager/commit/b0dca0a3c6cf65cbec53668e0d96f4bf4aac7c14))



### 🧹 Maintenance

- Version to 1.1.8 ([9ceb2bb](https://github.com/2Pz/me3-manager/commit/9ceb2bb3bea020e5176a9139bb2e7d0215871cd2))



---
## 📦 Release 1.1.7
**Released:** October 03, 2025


### ✨ New Features

- Add support section handling for profile versioning `[profile]` ([4b7e26b](https://github.com/2Pz/me3-manager/commit/4b7e26b876c3106e9bf414c39b77ca3fcb428cab))

- Add Steam integration for profile shortcuts `[profile]` ([f0eb640](https://github.com/2Pz/me3-manager/commit/f0eb640482f4586fd619eb899926c2067e8f20f4))

- Route updates for portable ME3 to ZIP installer `[windows]` ([2cd1757](https://github.com/2Pz/me3-manager/commit/2cd1757cc697f6a214c47ba9388343accaa64ee9))



### 🔧 Bug Fixes

- Improve error handling for profile directory and file creation `[config]` ([071bedb](https://github.com/2Pz/me3-manager/commit/071bedb80df3e18121c46b78a326c53a285aae73))

- Detect ME3 without admin; preserve drag-and-drop `[windows]` ([5af7606](https://github.com/2Pz/me3-manager/commit/5af7606ff327823850b91e08a15fc6ad39bb2bd4))



### 🧹 Maintenance

- README ([4cedcf1](https://github.com/2Pz/me3-manager/commit/4cedcf1745b106acea3e7f9970115a8231475809))



---
## 📦 Release 1.1.6
**Released:** September 21, 2025


### 🔧 Bug Fixes

- Enforce unique mod folders for profiles ([9675a36](https://github.com/2Pz/me3-manager/commit/9675a3670fb7964ac95d4d19636195246c06e42a))

- Use dotted key notation instead of nested tables ([1c6b033](https://github.com/2Pz/me3-manager/commit/1c6b033a2679272b3cd0438d45ada2333d6a735c))

- Reliably open paths/dirs in PyInstaller/Flatpak builds `[linux]` ([2e918ba](https://github.com/2Pz/me3-manager/commit/2e918ba325a17d5d536f5f145f7339689cc2d201))

- Correct rendering position in DraggableGameButton for drag operations ([f5cb87e](https://github.com/2Pz/me3-manager/commit/f5cb87ef21b1bc189c119b5fa7f3437368139548))

- Resolve resources relative to project root or _MEIPASS ([78c6174](https://github.com/2Pz/me3-manager/commit/78c6174e01fd46128d031c1b15bbd58992aa84df))

- PATH installation failure by correcting endswith() syntax ([8779d8f](https://github.com/2Pz/me3-manager/commit/8779d8f58c375fc8a92785bc441f63496c154536))

- Use canonical game slugs in me3.toml and migrate legacy keys `[config]` ([fdf784e](https://github.com/2Pz/me3-manager/commit/fdf784ebbec6d09427c48c35e1945c75daa1cd47))



### ♻️ Code Refactoring

- Migrate from PyQt6 to PySide6, update dependencies, and add export functionality ([37beb71](https://github.com/2Pz/me3-manager/commit/37beb715f67dc26991d1166a522c65ee9fe94646))



### 🧹 Maintenance

- Requirements ([0d5708f](https://github.com/2Pz/me3-manager/commit/0d5708f4fedb6b873c9974e2b93a1c13baac48ed))

- Dependencies & requirements ([49d960d](https://github.com/2Pz/me3-manager/commit/49d960de6d2c41ea2f55907fbca9e4416eeddec5))

- Version to 1.1.6 and enhance command execution in Linux environment ([d24db43](https://github.com/2Pz/me3-manager/commit/d24db43f6a236f3bd9548259cf828a148cd53f98))



---
## 📦 Release 1.1.5
**Released:** September 11, 2025


### ✨ New Features

- Script to sync requirements.txt ([9f9e03d](https://github.com/2Pz/me3-manager/commit/9f9e03d971d2843f24e8085251fe4316be3cbf40))

- Cache me3 info output to improve performance ([4a96025](https://github.com/2Pz/me3-manager/commit/4a96025b9c2a3f3f0c0abdc07471be75975244d7))



### 🔧 Bug Fixes

- Outdated types ([cea203a](https://github.com/2Pz/me3-manager/commit/cea203a34715729251a08ec1eb9ac3d2c3c5c0a9))

- Wrong key in translation ([800e502](https://github.com/2Pz/me3-manager/commit/800e5024665d6c37f442c0165fb012d03afb4975))

- Regex for valid mod names to exclude illegal characters ([5bd9497](https://github.com/2Pz/me3-manager/commit/5bd9497af460c9fc9e29910b1f4eae207e01f8aa))



### 🧹 Maintenance

- Rules ([fe2660b](https://github.com/2Pz/me3-manager/commit/fe2660b7885768056c701e6ced709a49efedf6aa))



### Fix

- Save optional dependency state for Package mods ([bebc155](https://github.com/2Pz/me3-manager/commit/bebc155b4ce5353b7ea34f677b6e398c23ea7809))



---
## 📦 Release 1.1.4
**Released:** September 11, 2025


### 🔧 Bug Fixes

- Https://github.com/2Pz/me3-manager/issues/41 ([dcfa28e](https://github.com/2Pz/me3-manager/commit/dcfa28e5348393905bf694112ab34621d883fa7f))



### 🧹 Maintenance

- Linter rules for logging ([f8bf067](https://github.com/2Pz/me3-manager/commit/f8bf067f08981bdd38ee39d047e34ab273920798))



---
## 📦 Release 1.1.3
**Released:** September 10, 2025


### ✨ New Features

- .python-version and pyproject.toml files for project configuration ([27b6ee6](https://github.com/2Pz/me3-manager/commit/27b6ee63d9c03a3c811c93bdcba25e7425e8f2f3))

- Language name to translation files and improve language retrieval logic ([cb32034](https://github.com/2Pz/me3-manager/commit/cb32034bf4628a2ca24d78bfda911696eaa7b3ca))

- Translation support for tooltips and UI strings across multiple modules ([1de1a20](https://github.com/2Pz/me3-manager/commit/1de1a209539e4e6c8777e663f0917509aa27ce22))

- Translations and improve UI for advanced mod options ([0a8149e](https://github.com/2Pz/me3-manager/commit/0a8149e6d39936ea2a1d5457bf5b3819d0ddc2e3))

- Ruff dev dep ([f684e1a](https://github.com/2Pz/me3-manager/commit/f684e1a501757f7ebae44d07f6f6500443f88671))

- CI lint/format check ([f2b4883](https://github.com/2Pz/me3-manager/commit/f2b4883304a310d22ac00a59e516a40a2dca64b2))

- Isort rule ([29072ec](https://github.com/2Pz/me3-manager/commit/29072ec396482ac69d6d9bf7e25c5ad73864c1c5))

- __init__.py to indicate package ([600c9a8](https://github.com/2Pz/me3-manager/commit/600c9a8b87cfd4127a35b1617a56b2125b8b5fc6))

- Uv entry point ([82e48c0](https://github.com/2Pz/me3-manager/commit/82e48c02303c1b0c7ef33cee877a7511c164d909))

- More dev instructions ([af397ff](https://github.com/2Pz/me3-manager/commit/af397fff198d3aee379f548519f5d9102600c437))

- .git-blame-ignore-revs ([146ea11](https://github.com/2Pz/me3-manager/commit/146ea11051ba762b31e19d46a8343ed76574e21f))

- Rules for logging ([2708f03](https://github.com/2Pz/me3-manager/commit/2708f03ef8bf35773fd1f1b55e9887c226b6878c))

- Logging to main.py ([03eac5c](https://github.com/2Pz/me3-manager/commit/03eac5c7423284607bdf836e01c4306466414103))

- Get_me3_binary_path method to PathManager and update ME3VersionManager to use it ([0c2688d](https://github.com/2Pz/me3-manager/commit/0c2688d220b7960e31252209af7efccb45585f22))

- Validation and error handling for mod installation process ([ae73c5f](https://github.com/2Pz/me3-manager/commit/ae73c5f2895a861b4d0d4bd2fb484b62af10fddc))



### 🔧 Bug Fixes

- Lint/format errors ([f88d349](https://github.com/2Pz/me3-manager/commit/f88d349f73032658da1019400d8c80d21c782214))

- Concurrency groups ([633296c](https://github.com/2Pz/me3-manager/commit/633296cb74e2ea709f593c523bc7f42d61425ad2))

- Import paths for HelpAboutDialog and GamePage in main window and game page modules ([599de3e](https://github.com/2Pz/me3-manager/commit/599de3e04c908c013259d587502502b36a435cbe))

- No module named 'winreg' on linux ([1d7db46](https://github.com/2Pz/me3-manager/commit/1d7db4604f4e5cae670f73b5270a9dd1891d2411))

- A bug with filter does not work after last refactor ([8a9249b](https://github.com/2Pz/me3-manager/commit/8a9249baed7892424b72d306d9d7b8efa4ec4374))



### 🧹 Maintenance

- .gitignore to include AppDir contents ([0b9df9a](https://github.com/2Pz/me3-manager/commit/0b9df9a1c5c22eadff5ca8588a524ad0c1e4e552))

- README.md ([228ac0b](https://github.com/2Pz/me3-manager/commit/228ac0bf4191e8db6b233764e43da42c405e187b))

- README.md ([4c187c3](https://github.com/2Pz/me3-manager/commit/4c187c354dd746e483a628286a007411534db4a7))

- Main.py ([e4fc6c9](https://github.com/2Pz/me3-manager/commit/e4fc6c90476aad631122e9e0d9813a4e6205546e))

- Build-appimage.sh ([fd4d21b](https://github.com/2Pz/me3-manager/commit/fd4d21bcdac2e4f9a48ce3dcc19c111a9d72860f))

- Windows build script ([5185012](https://github.com/2Pz/me3-manager/commit/5185012e7f2be7b55ed9545e839d5e7998a958d1))

- Config_facade.py ([705a18e](https://github.com/2Pz/me3-manager/commit/705a18e0cc16e98e32292e6c55fbd388a5d164e7))

- Config_facade.py ([05f0fb5](https://github.com/2Pz/me3-manager/commit/05f0fb53562ce523a12cf3e0825d911cd0ede85b))

- Path_manager.py ([4c44dc2](https://github.com/2Pz/me3-manager/commit/4c44dc21494b186083daf2357132ca86e7a900e0))

- Translation placeholders and improve TOML config handling ([2a56ad6](https://github.com/2Pz/me3-manager/commit/2a56ad68eb079a54aff0e1e36b99cfcd47a62e30))



### Fixes

- Steam Deck users can now launch games from both desktop and game mode again ([2e640b0](https://github.com/2Pz/me3-manager/commit/2e640b09932cd0d0b733247010d80b7591c83ded))



---
## 📦 Release 1.1.2
**Released:** August 16, 2025


### ✨ New Features

- Update custom ME3 installer path to match official structure ([d56956b](https://github.com/2Pz/me3-manager/commit/d56956bed9685e98b749e42226bf518a3491b546))

- Add ME3 installation check before game launch ([4971518](https://github.com/2Pz/me3-manager/commit/497151812d35686641d8e3297f6d4a8ae6f2c27c))



### 🔧 Bug Fixes

- UI ([335099e](https://github.com/2Pz/me3-manager/commit/335099e5eccbf1345252b6f95dc31cf1f0725397))

- Profile paths with spaces cause excessive shell quoting in launch commands ([97db4ae](https://github.com/2Pz/me3-manager/commit/97db4ae166a4d42dcd413f569e402249b2911ac5))

- Profile paths with spaces cause excessive shell quoting in launch commands ([a54c585](https://github.com/2Pz/me3-manager/commit/a54c5858af4d26f27385c815edd3ff5340984210))

- Handle system-wide ME3 configs on Linux without permission errors ([0ee6d7b](https://github.com/2Pz/me3-manager/commit/0ee6d7b03f6ba0e6a1b799981ac420bcb3198e0f))



### Https

- //github.com/2Pz/me3-manager/issues/5 ([8fe0c0e](https://github.com/2Pz/me3-manager/commit/8fe0c0e8d8fe7a7b0b2f5da148062bcb5afb3e3c))



---
## 📦 Release 1.1.1
**Released:** August 06, 2025


### 🧹 Maintenance

- README.md ([3d5438e](https://github.com/2Pz/me3-manager/commit/3d5438e8fe5a3af125b98463922da477c352abae))

- Config_manager.py ([41ceecd](https://github.com/2Pz/me3-manager/commit/41ceecdc17aaa59b20aeee8bc41ed47a256965af))

- Mod_manager.py ([4535c71](https://github.com/2Pz/me3-manager/commit/4535c718c8c3e336f281ad2d5357e51f96305af5))

- Mod_manager.py ([b4ff8f3](https://github.com/2Pz/me3-manager/commit/b4ff8f35e073087eeed70015ab8eb689fbd51e75))

- Mod_manager.py ([facb61a](https://github.com/2Pz/me3-manager/commit/facb61aaedd6018389cdfcb11b7f4eebaf652c3b))

- Mod_manager.py ([b6658e1](https://github.com/2Pz/me3-manager/commit/b6658e157a1f73bdee70a955703b25f21f2bc635))

- Mod_manager.py ([445c923](https://github.com/2Pz/me3-manager/commit/445c923da237ca0a5c3d4687266c528404f61352))



---
## 📦 Release 1.1.0
**Released:** August 01, 2025


### ✨ New Features

- Add support for custom ME3 config paths in ConfigManager ([c05293d](https://github.com/2Pz/me3-manager/commit/c05293d39aecc70a8620bd226bdb57c4459d4fc7))

- Bump version to 1.1.0 ([c0d423d](https://github.com/2Pz/me3-manager/commit/c0d423d726560003fd7daf09d0d9919d3a0801bb))

- Enhance ME3 config management with improved path validation and user options ([4cf6b57](https://github.com/2Pz/me3-manager/commit/4cf6b57fe97f106478b170a844fe3b94083181a5))



---
## 📦 Release 1.0.9
**Released:** July 31, 2025


### ✨ New Features

- Add advanced mod options dialog and dependency management ([de8f1d0](https://github.com/2Pz/me3-manager/commit/de8f1d0534536bcef4fee307984c733a66ba84f5))

- Implement ModManager for improved mod handling and UI integration ([486a889](https://github.com/2Pz/me3-manager/commit/486a8898c40db048224476631f9a6e4614c19384))

- Enhance command preparation for cross-platform compatibility and update game options dialog description ([9b80d37](https://github.com/2Pz/me3-manager/commit/9b80d379b63aa2fab388e8d23d724cd845f93a7f))

- Update build scripts for single executable generation and enhance game options dialog size ([8133259](https://github.com/2Pz/me3-manager/commit/81332595108902798486f140d0395436ce79d73b))

- Enhance primary config path retrieval and implement default config creation ([baee202](https://github.com/2Pz/me3-manager/commit/baee20236c7d752ec186fb9b038bf5f2563fe1a2))

- Update profile management icon to new design ([0e5a7b0](https://github.com/2Pz/me3-manager/commit/0e5a7b0ca9ccdcc9be1081d413796307353400f6))

- Implement installation monitoring for ME3 with version change detection ([9f61b12](https://github.com/2Pz/me3-manager/commit/9f61b12c2036f10b3946053eaf52f6a147660451))

- Increase game options dialog size for better usability ([bf89bf4](https://github.com/2Pz/me3-manager/commit/bf89bf4be63fa534059834f14302744c70b73fd7))

- Adjust items per page spinbox range to allow a minimum of 1 ([c5996a3](https://github.com/2Pz/me3-manager/commit/c5996a3e8e4a01781b4d3add399f3f79b9b769c1))

- Update video links in Help dialog for platform-specific guidance and remove custom installer button ([89866d8](https://github.com/2Pz/me3-manager/commit/89866d8f51ccffc1ea614c02336bef69c061f93d))

- Update settings icon to enhance visual consistency ([d802210](https://github.com/2Pz/me3-manager/commit/d8022100f157ac7292067488d8c9535c1f104a48))

- Increase Advanced Options dialog height for improved usability ([0271f22](https://github.com/2Pz/me3-manager/commit/0271f22c461870a2d3df914720fa8643adae9225))

- Enhance Game Options dialog with ME3 config file management features ([243254a](https://github.com/2Pz/me3-manager/commit/243254a5204faeefa4961e113da79c73ed5dbe5d))

- Implement expandable tree structure for mod display and enhance mod item widget ([e2662cd](https://github.com/2Pz/me3-manager/commit/e2662cd0838bcadb4ba712ba461b90962e7294bb))

- Increase Game Options dialog width for improved layout ([2f5c9a5](https://github.com/2Pz/me3-manager/commit/2f5c9a5b90bf3400acca7549b939f935853b898d))

- Refactor ModItem layout and button styles for improved UI consistency ([4f998bc](https://github.com/2Pz/me3-manager/commit/4f998bc7b937c9f86d3300ac2834a4e6030aa351))



### 🔧 Bug Fixes

- Simplify description text in game options dialog ([9377763](https://github.com/2Pz/me3-manager/commit/93777631653128d916fd4715d669c1642b0f306b))



### 🧹 Maintenance

- Bump version to 1.0.9 ([5be31bc](https://github.com/2Pz/me3-manager/commit/5be31bce33e3225f22a1c6bfe472d62421e147ac))



---
## 📦 Release 1.0.8
**Released:** July 25, 2025


### ✨ New Features

- Implement centralized ME3 version management and update settings ([e5b8b55](https://github.com/2Pz/me3-manager/commit/e5b8b552f1e1b09264b530464464c48a458cbb8e))



### ♻️ Code Refactoring

- Improve mod syncing logic and variable naming for clarity ([1ac1529](https://github.com/2Pz/me3-manager/commit/1ac152902573fa32d30c55b73d681696122f1b1c))

- Enhance syntax highlighting in profile editor for improved readability and consistency ([3cb03e3](https://github.com/2Pz/me3-manager/commit/3cb03e3f5c0cb092f81caf866358b63977f70c16))

- Remove extra spaces in TOML configuration formatting for consistency ([b092af6](https://github.com/2Pz/me3-manager/commit/b092af6366a3fb383c1080c21565264ea311a141))

- Clean up logging in file watcher updates for improved readability ([a08eb77](https://github.com/2Pz/me3-manager/commit/a08eb77da58c0e44f269446aa61545227e680ccc))



### 🧹 Maintenance

- Update version to 1.0.8 ([c1aee4f](https://github.com/2Pz/me3-manager/commit/c1aee4fa24e5d634d050074996c893dbfd5b919b))



---
## 📦 Release 1.0.7
**Released:** July 23, 2025


### ✨ New Features

- Steam deck support ([68c2442](https://github.com/2Pz/me3-manager/commit/68c2442bfd0989390acbc299fe38eb491cdcd7c6))

- New icon assets: add, arrow-down, delete, edit, play, and settings ([fd72c3d](https://github.com/2Pz/me3-manager/commit/fd72c3d6a22c4b0d5b7799c98157120cd922df75))



### 🔧 Bug Fixes

- Formatting in GamePage class to improve code readability ([4e57e21](https://github.com/2Pz/me3-manager/commit/4e57e21f093d3868e4d9c9368f0801147834e074))



### 🧹 Maintenance

- Config_manager.py ([e5b9a79](https://github.com/2Pz/me3-manager/commit/e5b9a798af8a35d54925f91d38479fbd1d03237c))

- Game_page.py ([7bece60](https://github.com/2Pz/me3-manager/commit/7bece60a7c8d2025a178c1930ceefd71fa8aacde))

- Main.py ([c9cf207](https://github.com/2Pz/me3-manager/commit/c9cf2073f2bd03e9dd9dd08e3da0dd00da1e5907))

- Main_window.py ([8e4cbf7](https://github.com/2Pz/me3-manager/commit/8e4cbf7414bee6fa3ed31461fc1b9d4a928a91ef))

- Main_window.py ([528d610](https://github.com/2Pz/me3-manager/commit/528d610748063a3f73922294e4a71e3048353b16))

- Main_window.py ([b490611](https://github.com/2Pz/me3-manager/commit/b490611eaddbb127c84b8de189c1f04125499237))

- Main_window.py ([78c762c](https://github.com/2Pz/me3-manager/commit/78c762cf2ea02a9880824cee2687e43b118feb9c))

- Main_window.py ([f20e8f0](https://github.com/2Pz/me3-manager/commit/f20e8f0b3f0ae96e3e9115c0ff2371225c28e3ca))

- Binary files and clean up main.py and resource_.py ([502662d](https://github.com/2Pz/me3-manager/commit/502662db9bd07ea62f630298d7ce5d662eefef60))

- Me3_info.py ([bcf4c8d](https://github.com/2Pz/me3-manager/commit/bcf4c8de651b2be902905c88fc82fc3c8cb97b66))

- Game_page.py ([1a8630f](https://github.com/2Pz/me3-manager/commit/1a8630fd4614ab1aa856a8669f3fa306785ecb52))

- Game_page.py ([ab765ee](https://github.com/2Pz/me3-manager/commit/ab765ee139bce674e65fe98bdbad8cbae83916d8))

- Game_page.py ([00d2815](https://github.com/2Pz/me3-manager/commit/00d28151f0b96a45668f8c6500c31ad5f47a9410))

- Me3_info.py ([a52a630](https://github.com/2Pz/me3-manager/commit/a52a630133d91c126cf7d0906f8ba273b78e542e))

- Me3_info.py ([8b5c8dc](https://github.com/2Pz/me3-manager/commit/8b5c8dc746e680ab4cbce05459bfac8f76bc05ff))

- Main_window.py ([90c0b91](https://github.com/2Pz/me3-manager/commit/90c0b91674263659582c676fb7ecb6faf7feacec))

- Game launch logic and version to 1.0.7 ([d265f40](https://github.com/2Pz/me3-manager/commit/d265f40cdea2f350064047d3beeb7603ded82992))



---
## 📦 Release Linux-0.0.1
**Released:** July 15, 2025


### 🧹 Maintenance

- Setup_linux.py ([7174cdd](https://github.com/2Pz/me3-manager/commit/7174cdd2dcad840e2fc339228102bfdb5603241e))

- Main_window.py ([619fe1a](https://github.com/2Pz/me3-manager/commit/619fe1aa2022269374dff1950739ca78fa54caee))



---
## 📦 Release 1.0.6
**Released:** July 14, 2025


---
[1.3.1]: https://github.com/2Pz/me3-manager/compare/1.3.0..1.3.1
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

