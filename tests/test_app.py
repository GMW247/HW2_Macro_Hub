import json
import pathlib
import tempfile
import time
import tkinter as tk
import types
import unittest

from macrohub import app, generator, runner


class KeyMapping(unittest.TestCase):
    def test_keys(self):
        self.assertEqual(app.key_from_event("l", 0x4C), "l")
        self.assertEqual(app.key_from_event("L", 0x4C), "l")  # shifted letter
        self.assertEqual(app.key_from_event("F1", 0x70), "F1")
        self.assertEqual(app.key_from_event("KP_1", 0x61), "Numpad1")
        self.assertEqual(app.key_from_event("KP_Enter", 0x0D), "NumpadEnter")
        self.assertEqual(app.key_from_event("Return", 0x0D), "Enter")
        self.assertEqual(app.key_from_event("Control_L", 0x11), "LCtrl")
        self.assertIsNone(app.key_from_event("odd", 0xFF))

    def test_all_mapped_names_are_allowed(self):
        names = list(app._VK.values()) + list(app._KEYSYM.values()) + app.MOUSE_BUTTONS
        for n in names:
            self.assertEqual(app.keys.canon(n), n, n)


def wait_for(pred, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.1)
    return False


@unittest.skipUnless(runner.find_ahk(), "AutoHotkey v2 not installed")
class RunnerTest(unittest.TestCase):
    def test_start_detect_stop(self):
        with tempfile.TemporaryDirectory() as d:
            s = pathlib.Path(d, "r.ahk")
            s.write_text("#Requires AutoHotkey v2.0\nPersistent\n", encoding="utf-8-sig")
            r = runner.Runner(s)
            self.assertFalse(r.is_running())
            p = r.start(runner.find_ahk())
            try:
                self.assertTrue(wait_for(r.is_running), "script window not found")
                self.assertEqual(r.stop(), 1)
                self.assertTrue(wait_for(lambda: not r.is_running()), "script did not stop")
                p.wait(timeout=5)
            finally:
                if p.poll() is None:
                    p.kill()


class AppTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = pathlib.Path(self.tmp.name)
        self.profile = d / "p.json"
        self.profile.write_text(json.dumps({"version": 1, "settings": {"gameExe": "notepad.exe"},
                                            "bindings": [{"trigger": ["l"], "stratagem": "AX/ARC-3 K-9"}]}))
        self.script = d / "macros.ahk"
        self.errors = []
        self._orig = app.messagebox
        app.messagebox = types.SimpleNamespace(
            showerror=lambda t, m: self.errors.append(m), showwarning=lambda t, m: self.errors.append(m),
            askyesno=lambda *a: True, askyesnocancel=lambda *a: False)
        self.root = tk.Tk()
        self.root.withdraw()
        self.a = app.App(self.root, self.profile, self.script)

    def tearDown(self):
        self.a.runner.stop()
        wait_for(lambda: not self.a.runner.is_running())
        self.root.destroy()
        app.messagebox = self._orig
        self.tmp.cleanup()

    def select(self, name):
        i = next(i for i, r in enumerate(self.a.catalog_rows) if r["name"] == name)
        self.a.search.set("")
        self.a.category.set("All")
        self.a._fill_catalog()
        self.a.cat_tree.selection_set(str(i))

    def key(self, keysym, vk):
        return self.a._on_key(types.SimpleNamespace(keysym=keysym, keycode=vk))

    def test_loads_profile(self):
        self.assertEqual(self.a.bindings, [{"trigger": ["l"], "stratagem": "AX/ARC-3 K-9"}])
        self.assertEqual(self.a.game_exe.get(), "notepad.exe")
        self.assertFalse(self.a.dirty)

    def test_search_filter(self):
        self.a.search.set("rocket sentry")
        self.assertEqual(len(self.a.cat_tree.get_children()), 1)

    def test_record_chain_and_add(self):
        self.select("Eagle Airstrike")
        self.a.toggle_record()
        self.assertEqual(self.key("F1", 0x70), "break")
        self.key("F2", 0x71)
        self.assertEqual(self.a.trigger_var.get(), "F1 > F2")
        self.a.add_binding()
        self.assertFalse(self.a.recording)
        self.assertEqual(self.a.bindings[-1], {"trigger": ["F1", "F2"], "stratagem": "Eagle Airstrike"})
        self.assertTrue(self.a.dirty)
        self.assertEqual(self.errors, [])

    def test_mouse_button(self):
        self.select("Reinforce")
        self.a.mouse_var.set("XButton2")
        self.a.add_mouse()
        self.a.add_binding()
        self.assertEqual(self.a.bindings[-1]["trigger"], ["XButton2"])

    def test_rejects_conflicts(self):
        self.select("Reinforce")
        self.a.trigger = ["l"]
        self.a.add_binding()
        self.assertIn("already bound", self.errors[-1])
        self.a.trigger = ["Up"]
        self.a.add_binding()
        self.assertIn("cannot be a trigger", self.errors[-1])
        self.assertEqual(len(self.a.bindings), 1)

    def test_remove(self):
        self.a.bind_tree.selection_set("0")
        self.a.remove_binding()
        self.assertEqual(self.a.bindings, [])

    def test_bad_setting_blocks_save(self):
        self.a.chain_timeout.set(1)
        self.assertFalse(self.a.save_profile())
        self.assertIn("chainTimeoutMs", self.errors[-1])

    @unittest.skipUnless(runner.find_ahk(), "AutoHotkey v2 not installed")
    def test_save_generate_run(self):
        self.select("ARC-3 Arc Thrower")
        self.a.trigger = ["o"]
        self.a.add_binding()
        self.a.save_generate_run()
        self.assertEqual(self.errors, [])
        saved = json.loads(self.profile.read_text())
        self.assertEqual([b["trigger"] for b in saved["bindings"]], [["l"], ["o"]])
        text = self.script.read_text(encoding="utf-8-sig")
        self.assertIn('~*o:: CallStratagem("DRDULL")', text)
        self.assertIn('ahk_exe notepad.exe', text)
        self.assertTrue(wait_for(self.a.runner.is_running), "macro script did not start")
        self.a.stop_macros()
        self.assertTrue(wait_for(lambda: not self.a.runner.is_running()), "macro script did not stop")


if __name__ == "__main__":
    unittest.main()
