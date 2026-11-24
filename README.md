# HW2 Macro Hub

A small Windows app for Helldivers 2. Bind stratagems to keys or mouse buttons, then press one button in game and the hub enters the stratagem code for you. It holds the stratagem menu key and presses the arrow keys.

The hub writes an [AutoHotkey v2](https://www.autohotkey.com/) script from your bindings and runs it.

## Features
- Searchable list of 120 stratagems with their codes.
- Single-button triggers (keyboard keys, mouse buttons).
- Button chains: several buttons pressed in order trigger one stratagem (max 1 second between presses by default).
- Hotkeys only fire while the Helldivers 2 window is active.
- Profiles saved as JSON, so you can keep several loadouts.
- Checks for conflicts before saving (duplicate triggers, a key used both alone and in a chain, reserved keys).

## Requirements
- Windows 10 or 11
- [AutoHotkey v2](https://www.autohotkey.com/download/) installed
- In-game stratagem controls: menu key held (default Ctrl), directions on the arrow keys

## Use the exe
Download `MacroHub.exe` from the Releases page and double-click it. Windows may show "Windows protected your PC" because the exe is not signed; click **More info**, then **Run anyway**.

1. Pick a stratagem in the list.
2. Click **Record keys**, press a key (or several keys for a chain), then **Stop recording**. Mouse buttons are added from the dropdown.
3. Click **3. Add binding**.
4. Click **Save, generate & run macros**. **Stop macros** turns them off.

The exe saves profiles and the generated `macros.ahk` in `Documents\MacroHub`.

If the game ignores the keys, run the hub as administrator.

## Run from source
Python 3.10+ (Tkinter is included with the standard Windows installer).

```powershell
python MacroHub.pyw
```
From source, profiles live in `profiles\` and the script is written to `macros.ahk` in the project folder.

Generate a script without the GUI:
```powershell
python -m macrohub.generator profiles\sample.json macros.ahk
```

Run the tests (the AutoHotkey runtime tests are skipped if AutoHotkey v2 is not installed):
```powershell
python -m unittest tests.test_app tests.test_generator
```

## Build the exe
```powershell
powershell -ExecutionPolicy Bypass -File build_exe.ps1
```
This creates a separate `.build-venv` with PyInstaller and writes `release\MacroHub.exe`, `release\README.txt` and `release\MacroHub.zip`.

## Update the stratagem list
Save https://helldivers.wiki.gg/wiki/Stratagems from your browser, then:
```powershell
python extract_stratagems.py path\to\saved_page.html
```
This rewrites `data\stratagems.json` and `data\stratagems.csv`.

## Project layout
| Path | Purpose |
|---|---|
| `macrohub/app.py` | Tkinter GUI |
| `macrohub/generator.py` | Profile validation and AHK v2 script generation |
| `macrohub/runner.py` | Finds AutoHotkey v2, starts and stops the script |
| `macrohub/keys.py` | Allowed key names |
| `macrohub/paths.py` | File locations for source and exe |
| `data/` | Stratagem catalog |
| `profiles/` | Example profiles |
| `DESIGN.md` | Design notes |

## Notes
- Use at your own risk. Check the game's current rules on macros and third-party tools.
- Code is MIT licensed (see `LICENSE`).
- The stratagem data in `data/` comes from the [Helldivers Wiki](https://helldivers.wiki.gg/wiki/Stratagems) and is licensed separately under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) (see `data/README.md`).
- Not affiliated with Arrowhead Game Studios or Sony Interactive Entertainment.
