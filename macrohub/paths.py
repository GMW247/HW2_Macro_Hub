"""Where Macro Hub reads bundled data and writes user files.

From source: everything lives in the project folder.
As a PyInstaller exe: bundled data is unpacked to a temp folder (sys._MEIPASS),
so user files (profiles, macros.ahk) go to Documents\\MacroHub instead.
"""
import ctypes
import json
import pathlib
import sys

FROZEN = getattr(sys, "frozen", False)
PROJECT = pathlib.Path(__file__).resolve().parent.parent
BUNDLE = pathlib.Path(getattr(sys, "_MEIPASS", PROJECT))
DATA_FILE = BUNDLE / "data" / "stratagems.json"


def _documents():
    buf = ctypes.create_unicode_buffer(260)
    # CSIDL_PERSONAL = 5; follows OneDrive or other folder redirection.
    if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:
        return pathlib.Path(buf.value)
    return pathlib.Path.home() / "Documents"


USER_DIR = _documents() / "MacroHub" if FROZEN else PROJECT
PROFILES = USER_DIR / "profiles"
SCRIPT = USER_DIR / "macros.ahk"
DEFAULT_PROFILE = PROFILES / ("default.json" if FROZEN else "sample.json")


def ensure_user_files():
    """Create the user folder and an empty default profile on first run. Never overwrites."""
    PROFILES.mkdir(parents=True, exist_ok=True)
    if not DEFAULT_PROFILE.exists():
        DEFAULT_PROFILE.write_text(json.dumps({"version": 1, "settings": {}, "bindings": []}, indent=2) + "\n",
                                   encoding="utf-8")
