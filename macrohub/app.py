"""Macro Hub GUI: bind stratagems to buttons, then save the profile, generate the AHK script and run it."""
import ctypes
import json
import pathlib
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

import webbrowser

from . import generator, keys, paths, runner

PROFILES = paths.PROFILES
DEFAULT_PROFILE = paths.DEFAULT_PROFILE
SCRIPT = paths.SCRIPT
AHK_DOWNLOAD = "https://www.autohotkey.com/download/"
MOUSE_BUTTONS = ["XButton1", "XButton2", "MButton", "RButton", "LButton", "WheelUp", "WheelDown"]
ARROWS = {"U": "\u2191", "D": "\u2193", "L": "\u2190", "R": "\u2192"}

# Tk keysyms that the Windows virtual-key table below cannot tell apart.
_KEYSYM = {
    "Control_L": "LCtrl", "Control_R": "RCtrl", "Shift_L": "LShift", "Shift_R": "RShift",
    "Alt_L": "LAlt", "Alt_R": "RAlt", "KP_Enter": "NumpadEnter",
}
# Windows virtual-key code -> AHK key name. On Windows, Tk's event.keycode is the VK code.
_VK = {0x20: "Space", 0x09: "Tab", 0x0D: "Enter", 0x08: "Backspace", 0x2E: "Delete",
       0x2D: "Insert", 0x24: "Home", 0x23: "End", 0x21: "PgUp", 0x22: "PgDn",
       0x26: "Up", 0x28: "Down", 0x25: "Left", 0x27: "Right", 0x14: "CapsLock",
       0x91: "ScrollLock", 0x13: "Pause", 0x1B: "Escape", 0x6E: "NumpadDot",
       0x6F: "NumpadDiv", 0x6A: "NumpadMult", 0x6B: "NumpadAdd", 0x6D: "NumpadSub"}
_VK.update({0x41 + i: chr(ord("a") + i) for i in range(26)})
_VK.update({0x30 + i: str(i) for i in range(10)})
_VK.update({0x60 + i: f"Numpad{i}" for i in range(10)})
_VK.update({0x70 + i: f"F{i + 1}" for i in range(24)})
_MOUSE_NUM = {1: "LButton", 2: "MButton", 3: "RButton", 4: "XButton1", 5: "XButton2"}


def key_from_event(keysym, keycode):
    """AHK key name for a Tk key event, or None if the key is not supported."""
    return _KEYSYM.get(keysym) or _VK.get(keycode)


def arrows(code):
    return " ".join(ARROWS[c] for c in code)


def trigger_text(trigger):
    return " > ".join(trigger)


class App(ttk.Frame):
    def __init__(self, master, profile_path=DEFAULT_PROFILE, script=SCRIPT):
        super().__init__(master, padding=8)
        self.master = master
        self.catalog_rows = json.loads(generator.DATA.read_text(encoding="utf-8"))
        self.catalog = generator.load_catalog()
        self.runner = runner.Runner(script)
        self.script = pathlib.Path(script)
        self.profile_path = None
        self.settings = dict(generator.DEFAULT_SETTINGS)
        self.bindings = []
        self.trigger = []
        self.recording = False
        self.dirty = False
        self._build()
        self.pack(fill="both", expand=True)
        if pathlib.Path(profile_path).exists():
            self.load_profile(profile_path)
        self._poll_status()

    # ---------- layout ----------
    def px(self, n):
        """Scale a size given for a 100% display to the current display scaling."""
        return int(n * self.ui_scale)

    def _build(self):
        # Tk reports 1.333 points per pixel at 100% Windows scaling. Treeview row height and
        # column widths are in pixels and do not scale on their own.
        self.ui_scale = max(1.0, float(self.tk.call("tk", "scaling")) / (96 / 72))
        line = tkfont.nametofont("TkDefaultFont").metrics("linespace")
        style = ttk.Style(self)
        style.configure("Treeview", rowheight=line + self.px(6))
        style.configure("Treeview.Heading", padding=(self.px(4), self.px(2)))
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Button(top, text="Open profile...", command=self.open_profile).pack(side="left")
        ttk.Button(top, text="Save profile as...", command=self.save_profile_as).pack(side="left", padx=4)
        self.profile_label = ttk.Label(top, text="")
        self.profile_label.pack(side="left", padx=8)

        # Catalog
        cat = ttk.LabelFrame(self, text="1. Pick a stratagem", padding=6)
        cat.grid(row=1, column=0, sticky="nsew", padx=(0, 4))
        cat.columnconfigure(1, weight=1)
        cat.rowconfigure(1, weight=1)
        ttk.Label(cat, text="Search").grid(row=0, column=0, sticky="w")
        self.search = tk.StringVar()
        self.search.trace_add("write", lambda *_: self._fill_catalog())
        ttk.Entry(cat, textvariable=self.search, width=20).grid(row=0, column=1, sticky="ew", padx=4)
        cats = ["All"] + sorted({r["category"] for r in self.catalog_rows if r["category"]})
        self.category = tk.StringVar(value="All")
        cb = ttk.Combobox(cat, textvariable=self.category, values=cats, state="readonly", width=18)
        cb.grid(row=0, column=2)
        cb.bind("<<ComboboxSelected>>", lambda e: self._fill_catalog())
        self.cat_tree = ttk.Treeview(cat, columns=("name", "category", "code"), show="headings", selectmode="browse")
        for col, text, w in (("name", "Stratagem", 230), ("category", "Category", 120), ("code", "Code", 130)):
            self.cat_tree.heading(col, text=text)
            self.cat_tree.column(col, width=self.px(w), minwidth=self.px(60), anchor="w")
        self.cat_tree.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=4)
        sb = ttk.Scrollbar(cat, orient="vertical", command=self.cat_tree.yview)
        sb.grid(row=1, column=3, sticky="ns", pady=4)
        self.cat_tree.configure(yscrollcommand=sb.set)
        self.cat_tree.bind("<Double-1>", lambda e: self.add_binding())
        self._fill_catalog()

        right = ttk.Frame(self)
        right.grid(row=1, column=1, sticky="nsew", padx=(4, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        # Trigger capture
        trg = ttk.LabelFrame(right, text="2. Set the trigger button (or chain)", padding=6)
        trg.grid(row=0, column=0, sticky="ew")
        trg.columnconfigure(1, weight=1)
        self.trigger_var = tk.StringVar(value="(none)")
        ttk.Label(trg, text="Trigger:").grid(row=0, column=0, sticky="w")
        ttk.Label(trg, textvariable=self.trigger_var, font=("Segoe UI", 11, "bold")).grid(row=0, column=1, sticky="w")
        buttons = ttk.Frame(trg)
        buttons.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.record_btn = ttk.Button(buttons, text="Record keys", command=self.toggle_record)
        self.record_btn.pack(side="left")
        ttk.Button(buttons, text="Clear", command=self.clear_trigger).pack(side="left", padx=4)
        self.mouse_var = tk.StringVar(value=MOUSE_BUTTONS[0])
        ttk.Combobox(buttons, textvariable=self.mouse_var, values=MOUSE_BUTTONS, state="readonly",
                     width=10).pack(side="left", padx=(12, 4))
        ttk.Button(buttons, text="Add mouse button", command=self.add_mouse).pack(side="left")
        self.record_hint = ttk.Label(trg, text="One key = single button. Several keys = chain, pressed in order.",
                                     foreground="gray")
        self.record_hint.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Button(trg, text="3. Add binding  \u2192", command=self.add_binding).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        # Bindings
        bnd = ttk.LabelFrame(right, text="Bindings", padding=6)
        bnd.grid(row=1, column=0, sticky="nsew", pady=6)
        bnd.columnconfigure(0, weight=1)
        bnd.rowconfigure(0, weight=1)
        self.bind_tree = ttk.Treeview(bnd, columns=("trigger", "stratagem", "code"), show="headings")
        for col, text, w in (("trigger", "Trigger", 110), ("stratagem", "Stratagem", 210), ("code", "Code", 130)):
            self.bind_tree.heading(col, text=text)
            self.bind_tree.column(col, width=self.px(w), minwidth=self.px(60), anchor="w")
        self.bind_tree.grid(row=0, column=0, sticky="nsew")
        ttk.Button(bnd, text="Remove selected", command=self.remove_binding).grid(row=1, column=0, sticky="w", pady=(4, 0))

        # Settings
        st = ttk.LabelFrame(right, text="Settings", padding=6)
        st.grid(row=2, column=0, sticky="ew")
        self.menu_key = tk.StringVar()
        self.key_delay = tk.IntVar()
        self.chain_timeout = tk.IntVar()
        self.pass_through = tk.BooleanVar()
        self.game_exe = tk.StringVar()
        ttk.Label(st, text="Stratagem menu key (held)").grid(row=0, column=0, sticky="w")
        ttk.Combobox(st, textvariable=self.menu_key, values=sorted(keys.MENU_KEYS), state="readonly",
                     width=10).grid(row=0, column=1, sticky="w")
        ttk.Label(st, text="Key delay (ms)").grid(row=0, column=2, sticky="w", padx=(12, 0))
        ttk.Spinbox(st, textvariable=self.key_delay, from_=1, to=500, width=6).grid(row=0, column=3, sticky="w")
        ttk.Label(st, text="Chain max gap (ms)").grid(row=1, column=0, sticky="w")
        ttk.Spinbox(st, textvariable=self.chain_timeout, from_=100, to=5000, increment=100,
                    width=8).grid(row=1, column=1, sticky="w")
        ttk.Label(st, text="Game exe").grid(row=1, column=2, sticky="w", padx=(12, 0))
        ttk.Entry(st, textvariable=self.game_exe, width=18).grid(row=1, column=3, sticky="w")
        ttk.Checkbutton(st, text="Trigger keys still reach the game", variable=self.pass_through).grid(
            row=2, column=0, columnspan=4, sticky="w")
        for v in (self.menu_key, self.key_delay, self.chain_timeout, self.pass_through, self.game_exe):
            v.trace_add("write", lambda *_: self._set_dirty(True))

        # Run bar
        bar = ttk.Frame(self)
        bar.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.status = ttk.Label(bar, text="", font=("Segoe UI", 10, "bold"))
        self.status.pack(side="left")
        ttk.Button(bar, text="Stop macros", command=self.stop_macros).pack(side="right")
        ttk.Button(bar, text="Save, generate & run macros", command=self.save_generate_run).pack(side="right", padx=4)
        ttk.Button(bar, text="Save profile", command=self.save_profile).pack(side="right")

        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------- catalog ----------
    def _fill_catalog(self):
        self.cat_tree.delete(*self.cat_tree.get_children())
        q = self.search.get().lower()
        c = self.category.get()
        for i, r in enumerate(self.catalog_rows):
            if (q in r["name"].lower()) and (c == "All" or r["category"] == c):
                self.cat_tree.insert("", "end", iid=str(i), values=(r["name"], r["category"], arrows(r["code"])))

    def selected_stratagem(self):
        sel = self.cat_tree.selection()
        return self.catalog_rows[int(sel[0])]["name"] if sel else None

    # ---------- trigger capture ----------
    def toggle_record(self):
        self.recording = not self.recording
        if self.recording:
            self.record_btn.configure(text="Stop recording")
            self.record_hint.configure(text="Press keys now. Click 'Stop recording' when done.", foreground="red")
            # Bound on this frame (not "all") so it runs before Tab traversal and button keys.
            self.bind("<KeyPress>", self._on_key)
            self.focus_set()
        else:
            self.record_btn.configure(text="Record keys")
            self.record_hint.configure(text="One key = single button. Several keys = chain, pressed in order.",
                                       foreground="gray")
            self.unbind("<KeyPress>")

    def _on_key(self, event):
        k = key_from_event(event.keysym, event.keycode)
        if k is None:
            self.bell()
        else:
            self.trigger.append(k)
            self._show_trigger()
        return "break"

    def add_mouse(self):
        self.trigger.append(self.mouse_var.get())
        self._show_trigger()

    def clear_trigger(self):
        self.trigger = []
        self._show_trigger()

    def _show_trigger(self):
        self.trigger_var.set(trigger_text(self.trigger) if self.trigger else "(none)")

    # ---------- bindings ----------
    def add_binding(self):
        if self.recording:
            self.toggle_record()
        name = self.selected_stratagem()
        if not name:
            messagebox.showwarning("Macro Hub", "Pick a stratagem in the list first.")
            return
        if not self.trigger:
            messagebox.showwarning("Macro Hub", "Record a trigger key or add a mouse button first.")
            return
        new = {"trigger": list(self.trigger), "stratagem": name}
        try:
            generator.validate(self.build_profile(self.bindings + [new]), self.catalog)
        except generator.ProfileError as e:
            messagebox.showerror("Cannot add binding", str(e))
            return
        self.bindings.append(new)
        self.clear_trigger()
        self._fill_bindings()
        self._set_dirty(True)

    def remove_binding(self):
        sel = self.bind_tree.selection()
        if not sel:
            return
        for i in sorted((int(s) for s in sel), reverse=True):
            del self.bindings[i]
        self._fill_bindings()
        self._set_dirty(True)

    def _fill_bindings(self):
        self.bind_tree.delete(*self.bind_tree.get_children())
        for i, b in enumerate(self.bindings):
            code = self.catalog.get(b["stratagem"], "")
            self.bind_tree.insert("", "end", iid=str(i),
                                  values=(trigger_text(b["trigger"]), b["stratagem"], arrows(code)))

    # ---------- profile ----------
    def build_profile(self, bindings=None):
        s = dict(self.settings)
        s["menuKey"] = self.menu_key.get()
        s["passThrough"] = bool(self.pass_through.get())
        s["gameExe"] = self.game_exe.get().strip()
        for key, var in (("keyDelayMs", self.key_delay), ("chainTimeoutMs", self.chain_timeout)):
            try:
                s[key] = int(var.get())
            except (tk.TclError, ValueError):
                s[key] = None  # validator reports it
        return {"version": 1, "settings": s, "bindings": self.bindings if bindings is None else bindings}

    def load_profile(self, path):
        path = pathlib.Path(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            settings, _ = generator.validate(data, self.catalog)
        except (OSError, ValueError) as e:
            messagebox.showerror("Cannot open profile", f"{path.name}: {e}")
            return False
        self.settings = settings
        self.bindings = [{"trigger": list(b["trigger"]), "stratagem": b["stratagem"]} for b in data.get("bindings", [])]
        self.menu_key.set(settings["menuKey"])
        self.key_delay.set(settings["keyDelayMs"])
        self.chain_timeout.set(settings["chainTimeoutMs"])
        self.pass_through.set(settings["passThrough"])
        self.game_exe.set(settings["gameExe"])
        self.profile_path = path
        self._fill_bindings()
        self._set_dirty(False)
        return True

    def _write_profile(self, path, profile):
        path = pathlib.Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
        self.profile_path = path
        self._set_dirty(False)

    def _validated_profile(self):
        profile = self.build_profile()
        try:
            generator.validate(profile, self.catalog)
        except generator.ProfileError as e:
            messagebox.showerror("Profile has a problem", str(e))
            return None
        return profile

    def save_profile(self):
        if self.profile_path is None:
            return self.save_profile_as()
        profile = self._validated_profile()
        if profile is None:
            return False
        self._write_profile(self.profile_path, profile)
        return True

    def save_profile_as(self):
        profile = self._validated_profile()
        if profile is None:
            return False
        path = filedialog.asksaveasfilename(initialdir=PROFILES, defaultextension=".json",
                                            filetypes=[("Profile", "*.json")])
        if not path:
            return False
        self._write_profile(path, profile)
        return True

    def open_profile(self):
        if self.dirty and not messagebox.askyesno("Macro Hub", "Discard unsaved changes?"):
            return
        path = filedialog.askopenfilename(initialdir=PROFILES, filetypes=[("Profile", "*.json")])
        if path:
            self.load_profile(path)

    def _set_dirty(self, dirty):
        self.dirty = dirty
        name = self.profile_path.name if self.profile_path else "(unsaved profile)"
        self.profile_label.configure(text=f"Profile: {name}{' *' if dirty else ''}")
        self.master.title(f"Macro Hub - {name}{' *' if dirty else ''}")

    # ---------- run ----------
    def save_generate_run(self):
        if self.recording:
            self.toggle_record()
        if not self.save_profile():
            return
        try:
            script = generator.generate(self.build_profile(), self.catalog, self.profile_path.stem)
        except generator.ProfileError as e:
            messagebox.showerror("Profile has a problem", str(e))
            return
        self.script.write_text(script, encoding="utf-8-sig")
        ahk = runner.find_ahk()
        if not ahk:
            ans = messagebox.askyesnocancel(
                "AutoHotkey v2 needed",
                "Macro Hub needs AutoHotkey v2 to run the macros, and it was not found.\n\n"
                "Yes: open the AutoHotkey download page (install v2, then click this button again).\n"
                "No: locate AutoHotkey64.exe yourself.")
            if ans is None:
                return
            if ans:
                webbrowser.open(AHK_DOWNLOAD)
                return
            ahk = filedialog.askopenfilename(title="Find AutoHotkey64.exe (v2)",
                                             filetypes=[("AutoHotkey v2", "AutoHotkey64.exe")])
            if not ahk:
                return
            runner.CANDIDATES.insert(0, ahk)
        try:
            self.runner.start(ahk)
        except OSError as e:
            messagebox.showerror("Cannot start AutoHotkey", str(e))
            return
        self.status.configure(text="Starting...", foreground="orange")

    def stop_macros(self):
        self.runner.stop()
        self.status.configure(text="Stopping...", foreground="orange")

    def _poll_status(self):
        if self.runner.is_running():
            self.status.configure(text=f"\u25cf Macros running ({len(self.bindings)} bindings)", foreground="green")
        else:
            self.status.configure(text="\u25cb Macros stopped", foreground="gray")
        self.after(1000, self._poll_status)

    def on_close(self):
        if self.dirty:
            ans = messagebox.askyesnocancel("Macro Hub", "Save changes to the profile before closing?")
            if ans is None or (ans and not self.save_profile()):
                return
        self.master.destroy()


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    paths.ensure_user_files()
    root = tk.Tk()
    a = App(root)
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    w, h = min(a.px(1250), int(sw * 0.92)), min(a.px(760), int(sh * 0.85))
    root.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 3)}")
    root.minsize(min(a.px(1000), w), min(a.px(600), h))
    root.mainloop()


if __name__ == "__main__":
    main()
