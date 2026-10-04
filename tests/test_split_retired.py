"""Spec 0005 task 10 — the canonical/stakeholder split is retired:
`validation_sync_check.py` leaves both settings templates and survives only
as a legacy shim (FR-03, NFR-05, AC-02, AC-08).
"""
import glob
import json
import os
import shutil
import unittest

from helpers import HOOKS, REPO, TempCase

SPLIT = {"canonical_lang": "English", "stakeholder_lang": "Portuguese", "stakeholder_lang_code": "pt"}
BODY = "## Business context\nwhy\n\n## Functional requirements\n- FR-01: x\n\n## Reconciliation\n"


class TestSplitRetired(TempCase):
    def setUp(self):
        super().setUp()
        self.repo = os.path.join(self.tmp, "app")
        self.hooks = os.path.join(self.repo, ".claude", "hooks")
        shutil.copytree(HOOKS, self.hooks, ignore=shutil.ignore_patterns("__pycache__"))
        self.spec = os.path.join(self.repo, "docs", "product", "specs", "0001-x.md")
        self.write(self.spec, "---\nstatus: approved\n---\n" + BODY)
        self.config = os.path.join(self.repo, ".claude", "project-config.json")

    def run_shim(self):
        payload = {"tool_name": "Edit", "tool_input": {"file_path": self.spec}}
        return self.hook(self.hooks, "validation_sync_check.py", payload, self.repo)

    def test_l20_settings_templates_do_not_wire_the_hook(self):  # FR-03, AC-02
        for name in ("settings.example.json", "settings.multi-project.json.example"):
            path = os.path.join(REPO, ".claude", name)
            text = self.read(path)
            self.assertNotIn("validation_sync_check", text, name)
            json.loads(text.replace("{{PYTHON}}", "python").replace("{{HOOKS_DIR}}", "/h"))

    def test_l20_shim_is_silent_without_split_keys(self):  # NFR-05
        for config in (None, {}, {"canonical_lang": "English"}, {**SPLIT, "stakeholder_lang": "English"}):
            if config is not None:
                self.write(self.config, json.dumps(config))
            result = self.run_shim()
            self.assertEqual((result.returncode, result.stdout.strip()), (0, ""), config)

    def test_l20_shim_acts_with_split_keys_and_no_setup_language(self):  # NFR-05, AC-08
        self.write(self.config, json.dumps(SPLIT))
        result = self.run_shim()
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn(".validation-pt.md", context)

    def test_l20_shim_is_silent_once_the_setup_has_a_language(self):  # FR-03
        self.write(self.config, json.dumps({**SPLIT, "language": "Portuguese", "language_code": "pt"}))
        self.assertEqual(self.run_shim().stdout.strip(), "")

    def test_l20_shim_never_deletes_a_validation_companion(self):  # AC-08
        companion = self.spec[:-3] + ".validation-pt.md"
        self.write(companion, "---\nsource_hash: stale\n---\nresumo\n")
        for config in (SPLIT, {**SPLIT, "language": "Portuguese"}, {}):
            self.write(self.config, json.dumps(config))
            self.run_shim()
            self.assertTrue(os.path.isfile(companion), config)
        self.assertEqual(len(glob.glob(os.path.join(os.path.dirname(self.spec), "*.validation-*.md"))), 1)

    def test_l20_template_is_gone(self):  # FR-03
        self.assertFalse(os.path.exists(os.path.join(REPO, "docs", "product", "validation-summary-template.md")))


if __name__ == "__main__":
    unittest.main()
