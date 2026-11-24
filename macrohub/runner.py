"""Find AutoHotkey v2 and start, stop or check the generated macro script.

The running script is found by its AutoHotkey main window (class "AutoHotkey",
title "<full script path> - AutoHotkey v2..."). This also finds a copy that was
started by double-clicking, not only copies started from the hub.
"""
import ctypes
import ctypes.wintypes as wt
import os
import pathlib
import shutil
import subprocess

CANDIDATES = [
    r"C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\AutoHotkey\v2\AutoHotkey64.exe"),
]

WM_COMMAND = 0x0111
ID_FILE_EXIT = 65307  # same as tray menu "Exit"

_user32 = ctypes.windll.user32
_EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
_user32.EnumWindows.argtypes = [_EnumProc, wt.LPARAM]
_user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
_user32.GetWindowTextLengthW.argtypes = [wt.HWND]
_user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
_user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]


def find_ahk():
    """Path to AutoHotkey64.exe (v2), or None."""
    for c in CANDIDATES:
        if os.path.isfile(c):
            return c
    return shutil.which("AutoHotkey64.exe")


def _script_windows(script):
    target = str(pathlib.Path(script).resolve()).lower() + " - autohotkey"
    found = []

    def cb(hwnd, _):
        cls = ctypes.create_unicode_buffer(64)
        _user32.GetClassNameW(hwnd, cls, 64)
        if cls.value == "AutoHotkey":
            n = _user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            _user32.GetWindowTextW(hwnd, buf, n + 1)
            if buf.value.lower().startswith(target):
                found.append(hwnd)
        return True

    _user32.EnumWindows(_EnumProc(cb), 0)
    return found


class Runner:
    def __init__(self, script):
        self.script = pathlib.Path(script).resolve()
        self.proc = None  # last process started by this hub

    def is_running(self):
        return bool(_script_windows(self.script))

    def start(self, ahk_exe):
        """Run the script. #SingleInstance Force in the script replaces an older copy."""
        if self.proc is not None:
            self.proc.poll()  # reap the old handle
        self.proc = subprocess.Popen([ahk_exe, str(self.script)], cwd=str(self.script.parent))
        return self.proc

    def stop(self):
        """Ask every running copy of the script to exit. Returns how many were asked."""
        hwnds = _script_windows(self.script)
        for h in hwnds:
            _user32.PostMessageW(h, WM_COMMAND, ID_FILE_EXIT, 0)
        return len(hwnds)
