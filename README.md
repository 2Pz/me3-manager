## Mod Engine 3 Manager


![Screenshot](https://i.ibb.co/GQygXRQF/Screenshot-2025-06-18-202933.png)
![Screenshot](https://i.ibb.co/nqDyCq2r/Screenshot-2025-06-18-205547.png)

hey so this is just a simple mod manager i made for Mod Engine 3. nothing fancy but it works pretty good


what it does:/n
drag and drop your mods (super easy)
turn mods on/off with one click
edit config files dirctly in the app
launch your games

---

## Download

Downlaod and install Me3 [Mod Engine 3](https://github.com/garyttierney/me3/releases/latest) 
Get the latest version for the manager from the [Releases](https://github.com/2pz/me3-manager/releases) tab.

---

## How to Use

1. Download and extract the `.zip` from [Releases](https://github.com/2pz/me3-manager/releases).
2. Run `ModEngine3Manager.exe`
3. Pick a game from the sidebar
4. Drag `.dll` mod files into the window
5. Click **Launch** to start the game

---

## Notes

- Mods are stored in: `%LocalAppData%\garyttierney\me3\`
- Supports `.ini` config editing per mod
- Also works with external mods (outside the mods folder)

---

## Need Help?

If something isn’t working, open an [Issue](https://github.com/2Pz/me3-manager/issues).

---

## For Developers

To run from source:

```bash
pip install PyQt6
python main.py
