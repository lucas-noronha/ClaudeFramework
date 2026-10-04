"""Spec 0007 task 8, test P17: the shipped prompts and settings carry the
rules; both templates wire SubagentStart, SubagentStop and the guard; the
mode C merge records them for uninstall (FR-10, FR-11, FR-18, AC-10).
"""
import json
import os
import unittest

from helpers import REPO, TempCase

TEMPLATES = {
    "mode A": os.path.join(REPO, ".claude", "settings.example.json"),
    "mode B/C": os.path.join(REPO, ".claude", "settings.multi-project.json.example"),
}
INSTALLER = os.path.join(REPO, ".claude", "scripts", "install_user_level.py")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def commands(groups):
    return [h["command"] for g in groups for h in g["hooks"]]


class TemplateWiring(unittest.TestCase):
    def test_p17_subagent_start_runs_pipeline_metrics(self):  # FR-11
        for label, path in TEMPLATES.items():
            groups = load(path)["hooks"]["SubagentStart"]
            self.assertEqual(len(groups), 1, label)
            self.assertIn("pipeline_metrics.py", commands(groups)[0], label)

    def test_p17_subagent_stop_gate_first_then_metrics(self):  # FR-11, FR-18
        for label, path in TEMPLATES.items():
            groups = load(path)["hooks"]["SubagentStop"]
            self.assertEqual(len(groups), 2, label)
            self.assertIn("run_build_test.py", commands(groups[:1])[0], label)
            self.assertIn("pipeline_metrics.py", commands(groups[1:])[0], label)

    def test_p17_guard_on_bash_and_powershell_without_if(self):  # FR-10
        for label, path in TEMPLATES.items():
            found = [g for g in load(path)["hooks"]["PreToolUse"]
                     if any("subagent_git_guard.py" in h["command"] for h in g["hooks"])]
            self.assertEqual(len(found), 1, label)
            self.assertEqual(found[0]["matcher"], "Bash|PowerShell", label)
            for h in found[0]["hooks"]:
                self.assertNotIn("if", h, label)
                self.assertNotIn("if", found[0], label)

    def test_p17_templates_wire_the_same_new_events(self):
        events = [set(load(p)["hooks"]) for p in TEMPLATES.values()]
        self.assertEqual(events[0], events[1])


class ModeCMerge(TempCase):
    def setUp(self):
        super().setUp()
        self.config = os.path.join(self.home, ".claude")
        self.original = '{\n  "hooks": {"SubagentStop": [{"hooks": [{"type": "command", "command": "echo mine"}]}]}\n}\n'
        self.write(os.path.join(self.config, "settings.json"), self.original)
        self.ns = os.path.join(self.config, "cfw")
        self.run_py(INSTALLER, "--config-dir", self.config, "--today", "2026-10-04", "--apply")

    def settings(self):
        return load(os.path.join(self.config, "settings.json"))

    def test_p17_install_wires_and_records_for_uninstall(self):  # FR-10, FR-11, AC-10
        hooks = self.settings()["hooks"]
        self.assertTrue(any("pipeline_metrics.py" in c for c in commands(hooks["SubagentStart"])))
        stop = commands(hooks["SubagentStop"])
        self.assertEqual(stop[0], "echo mine")
        self.assertEqual(sum("pipeline_metrics.py" in c for c in stop), 1)
        self.assertEqual(sum("run_build_test.py" in c for c in stop), 1)
        self.assertTrue(any("subagent_git_guard.py" in c for c in commands(hooks["PreToolUse"])))
        self.assertTrue(os.path.isfile(os.path.join(self.ns, "hooks", "subagent_git_guard.py")))
        self.assertTrue(os.path.isfile(os.path.join(self.ns, "hooks", "_subagents.py")))
        recorded = load(os.path.join(self.ns, "manifest.json"))["settings"]["added_groups"]
        for event in ("SubagentStart", "SubagentStop", "PreToolUse"):
            self.assertTrue(any(r["event"] == event for r in recorded), event)
        self.assertTrue(any(r["event"] == "PreToolUse" and "subagent_git_guard.py" in json.dumps(r["group"])
                            for r in recorded))

    def test_p17_rerun_is_idempotent_and_uninstall_restores(self):
        before = self.settings()
        self.run_py(INSTALLER, "--config-dir", self.config, "--today", "2026-10-04", "--apply")
        self.assertEqual(before, self.settings())
        self.run_py(os.path.join(self.ns, "scripts", "uninstall.py"), "--apply")
        with open(os.path.join(self.config, "settings.json"), "rb") as f:
            self.assertEqual(f.read(), self.original.encode())


if __name__ == "__main__":
    unittest.main()
