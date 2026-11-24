# Macro Hub: Design Document

Status: v1. Generator, runner, GUI and exe packaging are built.

## 1. Goal
A small Windows tool where a user binds Helldivers 2 stratagem codes to input buttons (keyboard and mouse). The tool generates an AutoHotkey (AHK) script from those bindings and runs it.

## 2. Scope
In scope:
- Stratagem catalog (name, code, category) loaded from `data/stratagems.json`.
- Binding editor: pick a stratagem, pick a trigger (single button or button chain), save to a profile.
- AHK script generation from a profile.
- Run, stop and reload the generated script.
- Profiles saved as JSON.

Out of scope for v1: gamepad triggers, one trigger running several stratagems, memory reading, injecting into the game process, any automation beyond sending the stratagem key sequence on a button press (no aimbot, no auto-throw, no timing from game state).

## 3. Data source
The source is a saved copy of https://helldivers.wiki.gg/wiki/Stratagems. `extract_stratagems.py <saved.html>` parses the tables and arrow images into `data/stratagems.json` and `data/stratagems.csv`.

Record fields: `name`, `code` (string of U/D/L/R), `permit`, `category`, `cooldown`, `cost`, `unlock`.

Result: 120 stratagems. Exact duplicates are dropped. `SSSD Delivery` is listed with two different codes, so both are kept as `SSSD Delivery (DDDDDUU)` and `SSSD Delivery (DDDUU)`. Codes run 3 to 9 inputs. Nine-input codes (Orbital Confetti, Eagle Fly By, TD-110 Maelstrom, TD-220 Bastion, Call In Super Destroyer, NUX-223 Hellbomb, Aquifer Drill) come from the wiki and are kept as is. Re-run the extractor when the wiki is re-saved.

## 4. Architecture
```
wiki HTML --extract_stratagems.py--> stratagems.json
                                          |
              Hub UI (editor) <-----------+
                   | saves
               profile.json
                   | generator
               macros.ahk --> AutoHotkey v2 runs it
```
Components:
1. Extractor (done).
2. Hub UI: lists stratagems, captures the trigger button, shows current bindings.
3. Generator: pure function from profile JSON to AHK text.
4. Runner: launches `AutoHotkey64.exe macros.ahk`, tracks the process, stops or restarts it.

## 5. Profile format
```json
{
  "version": 1,
  "settings": { "menuKey": "LCtrl", "menuMode": "hold", "keyDelayMs": 30,
                "chainTimeoutMs": 1000, "passThrough": true, "gameExe": "helldivers2.exe",
                "arrowKeys": {"U":"Up","D":"Down","L":"Left","R":"Right"} },
  "bindings": [
    { "trigger": ["XButton1"],        "stratagem": "Orbital Precision Strike" },
    { "trigger": ["F1", "F2"],        "stratagem": "Eagle Airstrike" }
  ]
}
```
`trigger` is always a list. One element is a single button. Two or more elements is a chain, pressed in order. A binding maps to exactly one stratagem.

Validation rules (enforced by the generator and the UI):
- A trigger (the full list) can be used once. One trigger, one stratagem.
- A stratagem may have more than one trigger.
- A button used as a single trigger cannot appear anywhere in a chain, and the reverse. Otherwise the script cannot tell "pressed alone" from "part of a chain" without a delay. See section 6b.
- Triggers cannot use the menu key or the four direction keys, because the script sends those itself.
- Chains share prefixes only when no chain is a strict prefix of another (e.g. `F1,F2` and `F1,F2,F3` conflict).
- Chain buttons must be valid AHK key names from the generator's table.
## 6. AHK generation
Target AutoHotkey v2. For each binding, emit:
```ahk
XButton1:: CallStratagem("RRU")
```
Shared helper:
```ahk
CallStratagem(code) {
    Send "{LCtrl down}"
    Sleep 50
    for ch in StrSplit(code) {
        Send "{" Keys[ch] " down}"
        Sleep 30
        Send "{" Keys[ch] " up}"
        Sleep 30
    }
    Send "{LCtrl up}"
}
```
Rules:
- Add `#HotIf WinActive("ahk_exe helldivers2.exe")` so hotkeys only fire in the game.
- Use `SendEvent` or `SendInput` per testing. The menu key is held (Ctrl down, arrows, Ctrl up).
- Prefix triggers with `*` so modifiers do not block them.
- Validate trigger names against the AHK key list. The generator never interpolates free text into the script.
- Header comment with the profile name. The script is overwritten on each generate.

## 6b. Chain handling
A chain is a small state machine in the generated script. Each chain button is a hotkey that checks the current chain state.
- Pressing the first button of any chain starts a pending state and starts a timer of `chainTimeoutMs` (1000 ms, a maximum gap between presses).
- Each next press must match the next button of at least one chain. Matching moves forward. A wrong press resets the state.
- Reaching the end of a chain calls `CallStratagem(code)` and resets.
- Timeout resets the state.
- Chain buttons are sent through to the game (`~` prefix) so they keep their normal in-game function. Make this a per-binding option later if it causes trouble.
- Chain hotkeys only fire inside the game window.

## 7. UI options
| Option | Pros | Cons |
|---|---|---|
| A. Python + Tkinter | No extra dependencies, simple, packs into one exe | Plain look |
| B. Local web page (HTML/JS) | Nicer UI, easy search | Needs a small server or file download to write the script |
| C. AHK GUI only | Single dependency | Harder to build a searchable catalog |

Chosen: A. The generator is separate so the UI can change later.

## 8. Key capture
Tkinter captures keyboard keys while its window is focused. Mouse buttons are picked from a dropdown. Chains are captured by recording presses in order. Gamepad is out of scope for v1. Hotkey name mapping lives in one table in the generator.

## 9. Risks
- Anti-cheat: AHK that sends keys is commonly used with this game, but check the current Arrowhead and nProtect GameGuard policy yourself. Keep one key press per stratagem input, with no game-state reading.
- Game input method: if the game ignores injected keys, try `SendEvent` with a higher key delay.
- Elevation: AHK may need admin rights if the game runs elevated.
- Wiki data may change when the game updates.

## 10. Decisions
| # | Decision |
|---|---|
| 1 | UI is Python + Tkinter. |
| 2 | Target AutoHotkey v2. |
| 3 | No gamepad in v1. Triggers are keyboard and mouse only. |
| 4 | In-game menu key is Ctrl, held. In-game stratagem inputs are the arrow keys (Up/Down/Left/Right). |
| 5 | One trigger maps to exactly one stratagem. Button chains (several buttons pressed in order) are supported and trigger one stratagem. |
| 6 | Chain gap max 1000 ms. Trigger keys pass through to the game. A stratagem may have several triggers. Game exe is `helldivers2.exe`. |

The direction keys stay configurable in the profile (`arrowKeys`), for players who use WASD.

## 11. Open questions
None.

## 12. Milestones
1. Design doc and catalog extraction (done).
2. Generator and profile format, with tests (done).
3. Runner (done): `macrohub/runner.py`. Finds `AutoHotkey64.exe` (v2), starts the script, detects it by its AutoHotkey window title (so it also sees copies started by double-click), stops it with the tray "Exit" command (WM_COMMAND 65307).
4. GUI (done): `macrohub/app.py`, launched by `MacroHub.pyw`.
5. Packaging (done): `build_exe.ps1` -> `release\MacroHub.exe` + `README.txt` + `MacroHub.zip`. The exe stores user files in Documents\MacroHub. AutoHotkey v2 must be installed separately.

## 13. GUI layout
- Top: Open profile, Save profile as, current profile name (`*` = unsaved).
- Left: "1. Pick a stratagem": search box, category filter, list with arrow codes.
- Right: "2. Set the trigger": Record keys (captures key presses on the hub window until Stop recording; one key = single, several = chain), mouse button dropdown + Add mouse button, Clear. "3. Add binding" validates the whole profile first and shows the error if a rule is broken.
- Right: Bindings list with Remove selected. Settings: menu key, key delay, chain max gap, game exe, pass-through.
- Bottom: status (running/stopped, polled every second), Save profile, Save generate & run macros (save profile -> write `macros.ahk` -> start AHK v2; replaces a running copy via #SingleInstance Force), Stop macros.
- Mouse buttons come from a dropdown because Tk 8.6 does not reliably report side buttons.


