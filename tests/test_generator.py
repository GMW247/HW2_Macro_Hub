import json, os, pathlib, subprocess, tempfile, unittest

from macrohub import generator as g

CAT = {"Orbital Precision Strike": "RRU", "Eagle Airstrike": "RDRD", "Reinforce": "UDRLU",
       "Orbital Gatling Barrage": "RDLUU"}
AHK = pathlib.Path(r"C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe")


def prof(*binds, **settings):
    return {"version": 1, "settings": settings,
            "bindings": [{"trigger": t, "stratagem": s} for t, s in binds]}


class Validation(unittest.TestCase):
    def bad(self, p, text):
        with self.assertRaises(g.ProfileError) as c:
            g.validate(p, CAT)
        self.assertIn(text, str(c.exception))

    def test_ok(self):
        s, b = g.validate(prof((["xbutton1"], "Reinforce"), (["F1", "F2"], "Eagle Airstrike")), CAT)
        self.assertEqual(b[0]["trigger"], ["XButton1"])
        self.assertEqual(s["chainTimeoutMs"], 1000)

    def test_unknown_stratagem(self):
        self.bad(prof((["F1"], "Nope")), "unknown stratagem")

    def test_disallowed_key(self):
        self.bad(prof((["F1\nSend x"], "Reinforce")), "not allowed")

    def test_empty_trigger(self):
        self.bad(prof(([], "Reinforce")), "non-empty")

    def test_reserved_keys(self):
        self.bad(prof((["Up"], "Reinforce")), "cannot be a trigger")
        self.bad(prof((["LCtrl"], "Reinforce")), "cannot be a trigger")

    def test_duplicate_trigger(self):
        self.bad(prof((["F1"], "Reinforce"), (["f1"], "Eagle Airstrike")), "already bound")

    def test_same_stratagem_two_triggers_ok(self):
        g.validate(prof((["F1"], "Reinforce"), (["F2"], "Reinforce")), CAT)

    def test_single_and_chain_conflict(self):
        self.bad(prof((["F1"], "Reinforce"), (["F2", "F1"], "Eagle Airstrike")), "single trigger and inside a chain")

    def test_chain_prefix(self):
        self.bad(prof((["F1", "F2"], "Reinforce"), (["F1", "F2", "F3"], "Eagle Airstrike")), "prefix")

    def test_chains_sharing_start_ok(self):
        g.validate(prof((["F1", "F2"], "Reinforce"), (["F1", "F3"], "Eagle Airstrike")), CAT)

    def test_bad_settings(self):
        for s in ({"chainTimeoutMs": 0}, {"keyDelayMs": "x"}, {"gameExe": 'a" b.exe'},
                  {"menuKey": "F1"}, {"menuMode": "toggle"}, {"passThrough": 1}):
            with self.assertRaises(g.ProfileError, msg=s):
                g.validate(prof(**s), CAT)

    def test_bad_version(self):
        with self.assertRaises(g.ProfileError):
            g.validate({"version": 2}, CAT)


class Output(unittest.TestCase):
    def test_contents(self):
        out = g.generate(prof((["XButton1"], "Orbital Precision Strike"), (["F1", "F2"], "Eagle Airstrike")), CAT)
        self.assertIn("#Requires AutoHotkey v2.0", out)
        self.assertIn('#HotIf WinActive("ahk_exe helldivers2.exe")', out)
        self.assertIn('~*XButton1:: CallStratagem("RRU")', out)
        self.assertIn('Chains["f1|f2|"] := "RDRD"', out)
        self.assertIn("ChainTimeoutMs := 1000", out)
        self.assertIn('MenuKey := "LCtrl"', out)

    def test_no_pass_through(self):
        out = g.generate(prof((["F5"], "Reinforce"), passThrough=False), CAT)
        self.assertIn("*F5::", out)
        self.assertNotIn("~*F5::", out)

    def test_profile_name_cannot_inject(self):
        out = g.generate(prof(), CAT, "x\nMsgBox 1")
        self.assertNotIn("\nMsgBox", out)

    def test_real_catalog(self):
        cat = g.load_catalog()
        self.assertEqual(len(cat), 120)
        self.assertEqual(cat["Orbital Precision Strike"], "RRU")


@unittest.skipUnless(AHK.exists(), "AutoHotkey v2 not installed")
class AhkRuntime(unittest.TestCase):
    """Load the generated script in AHK v2 and drive ChainKey directly. CallStratagem is stubbed to print its code."""

    def run_ahk(self, p, calls):
        script = g.generate(p, CAT)
        # Swap the whole CallStratagem function for a stub, so no unreachable lines remain.
        start = script.index("CallStratagem(code) {")
        end = script.index("\n}\n", start) + 3
        self.assertIn("finally", script[start:end])  # sanity: we cut the real function
        script = script[:start] + 'CallStratagem(code) {\n    FileAppend code "`n", "*"\n}\n' + script[end:]
        head = script.split("#HotIf WinActive")[0]
        test = head + "\n" + calls + "\nExitApp\n"
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "t.ahk")
            pathlib.Path(f).write_text(test, encoding="utf-8-sig")
            r = subprocess.run([str(AHK), "/ErrorStdOut=UTF-8", f], capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout.split()

    P = prof((["F1", "F2"], "Eagle Airstrike"), (["F1", "F3"], "Orbital Gatling Barrage"),
             (["F4", "F5", "F6"], "Reinforce"))

    def test_chain_fires(self):
        self.assertEqual(self.run_ahk(self.P, 'ChainKey("f1")\nChainKey("f2")'), ["RDRD"])

    def test_shared_start(self):
        self.assertEqual(self.run_ahk(self.P, 'ChainKey("f1")\nChainKey("f3")'), ["RDLUU"])

    def test_three_button_chain(self):
        self.assertEqual(self.run_ahk(self.P, 'ChainKey("f4")\nChainKey("f5")\nChainKey("f6")'), ["UDRLU"])

    def test_wrong_key_resets_and_restarts(self):
        self.assertEqual(self.run_ahk(self.P, 'ChainKey("f1")\nChainKey("f6")\nChainKey("f2")'), [])
        self.assertEqual(self.run_ahk(self.P, 'ChainKey("f1")\nChainKey("f1")\nChainKey("f2")'), ["RDRD"])

    def test_partial_does_not_fire(self):
        self.assertEqual(self.run_ahk(self.P, 'ChainKey("f4")\nChainKey("f5")'), [])

    def test_timeout_resets(self):
        calls = 'ChainKey("f1")\nSleep 1300\nChainKey("f2")'
        self.assertEqual(self.run_ahk(self.P, calls), [])

    def test_within_timeout(self):
        calls = 'ChainKey("f1")\nSleep 700\nChainKey("f2")'
        self.assertEqual(self.run_ahk(self.P, calls), ["RDRD"])

    def test_empty_profile_stays_running(self):
        script = g.generate(prof(), CAT)
        with tempfile.TemporaryDirectory() as d:
            f = pathlib.Path(d, "e.ahk")
            f.write_text(script, encoding="utf-8-sig")
            proc = subprocess.Popen([str(AHK), str(f)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                with self.assertRaises(subprocess.TimeoutExpired, msg="empty script exited"):
                    proc.wait(timeout=2)
            finally:
                proc.kill()
                proc.wait()

    def test_full_script_loads(self):
        sample = pathlib.Path(g.DATA).parent.parent / "profiles" / "sample.json"
        script = g.generate(json.loads(sample.read_text(encoding="utf-8")), g.load_catalog())
        with tempfile.TemporaryDirectory() as d:
            f = pathlib.Path(d, "s.ahk")
            f.write_text(script, encoding="utf-8-sig")
            log = pathlib.Path(d, "out.txt")
            with open(log, "w") as out:
                proc = subprocess.Popen([str(AHK), "/ErrorStdOut=UTF-8", str(f)], stdout=out, stderr=out)
                try:
                    proc.wait(timeout=3)
                    exited = True
                except subprocess.TimeoutExpired:
                    exited = False  # still running means it loaded without error
                    proc.kill()
                    proc.wait()
            if exited:
                self.fail("script exited early: " + log.read_text(errors="replace"))

if __name__ == "__main__":
    unittest.main()

