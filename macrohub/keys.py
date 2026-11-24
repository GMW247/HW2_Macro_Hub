"""Key name allowlist. Only names listed here may reach the generated AHK script."""
import re

_SINGLE = set("abcdefghijklmnopqrstuvwxyz0123456789")
_FKEYS = {f"F{i}" for i in range(1, 25)}
_NUMPAD = {f"Numpad{i}" for i in range(10)} | {
    "NumpadDot", "NumpadDiv", "NumpadMult", "NumpadAdd", "NumpadSub", "NumpadEnter"}
_MOUSE = {"LButton", "RButton", "MButton", "XButton1", "XButton2", "WheelUp", "WheelDown"}
_NAMED = {"Space", "Tab", "Enter", "Backspace", "Delete", "Insert", "Home", "End",
          "PgUp", "PgDn", "Up", "Down", "Left", "Right", "CapsLock", "ScrollLock",
          "Pause", "Escape"}
_MODIFIERS = {"LCtrl", "RCtrl", "LShift", "RShift", "LAlt", "RAlt"}

TRIGGER_KEYS = _SINGLE | _FKEYS | _NUMPAD | _MOUSE | _NAMED | _MODIFIERS
MENU_KEYS = {"LCtrl", "RCtrl", "LShift", "RShift", "LAlt", "RAlt"}
DIRECTION_KEYS = {"Up", "Down", "Left", "Right"}
_CANON = {k.lower(): k for k in TRIGGER_KEYS}
GAME_EXE_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}\.exe$")


def canon(name):
    """Return the canonical spelling of a key name, or None if not allowed."""
    return _CANON.get(name.lower()) if isinstance(name, str) else None
