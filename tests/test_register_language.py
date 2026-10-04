"""Spec 0005 task 11 — registration no longer asks for or writes a language
(FR-01, NFR-05, AC-01; ADR 0023 sections 1 and 6).
"""
import json
import os
import unittest

from test_installer_language import LanguageCase, PT

RETIRED = ("--canonical-lang", "Spanish", "--stakeholder-lang", "French", "--stakeholder-lang-code", "fr")


class TestRegisterLanguage(LanguageCase):
    def register(self, repo, name, *extra, plan=None):
        script = os.path.join(self.ns, "scripts", "register_project.py")
        return self.run_py(script, "--repo", repo, "--name", name, "--today", "2026-10-03", *extra, "--apply")

    def subtree_config(self, name):
        return json.loads(self.read(os.path.join(self.ns, "docs", name, "project-config.json")))

    def test_l03_writes_no_language_and_fills_the_setup_language(self):  # FR-01, AC-01
        self.build_cache()
        self.install("--apply", *PT)
        result = self.register(self.make_repo("orders", {"Orders.sln": ""}), "orders")
        self.assertEqual(result.stderr, "")
        config = self.subtree_config("orders")
        for key in ("canonical_lang", "stakeholder_lang", "stakeholder_lang_code", "language", "language_code"):
            self.assertNotIn(key, config)
        text = self.read(os.path.join(self.ns, "docs", "orders", "CLAUDE.md"))
        self.assertNotIn("{{LANGUAGE}}", text)
        self.assertIn("Portuguese", text)
        self.assertNotIn("{{STAKEHOLDER", text)

    def test_l03_retired_flags_are_accepted_ignored_and_warned_about(self):  # NFR-05, AC-01
        self.install("--apply")
        result = self.register(self.make_repo("orders", {"Orders.sln": ""}), "orders", *RETIRED)
        for flag in ("--canonical-lang", "--stakeholder-lang", "--stakeholder-lang-code"):
            self.assertIn(flag, result.stderr)
        config = self.subtree_config("orders")
        self.assertFalse({"canonical_lang", "stakeholder_lang", "stakeholder_lang_code"} & set(config))
        text = self.read(os.path.join(self.ns, "docs", "orders", "CLAUDE.md"))
        self.assertNotIn("Spanish", text)
        self.assertNotIn("French", text)

    def test_l03_retired_flags_are_hidden_from_help(self):  # NFR-05
        script = os.path.join(self.ns, "scripts", "register_project.py")
        self.install("--apply")
        helptext = self.run_py(script, "--help").stdout
        self.assertNotIn("canonical-lang", helptext)
        self.assertNotIn("stakeholder", helptext)

    def test_l03_retired_plan_keys_are_ignored_and_warned_about(self):  # NFR-05
        self.install("--apply")
        repo = self.make_repo("orders", {"Orders.sln": ""})
        plan = os.path.join(self.tmp, "plan.json")
        self.write(plan, json.dumps({"shared": {"canonical_lang": "Spanish", "stakeholder_lang": "French",
                                                 "stakeholder_lang_code": "fr"},
                                     "projects": [{"repo": repo, "name": "orders", "canonical_lang": "German"}]}))
        script = os.path.join(self.ns, "scripts", "register_project.py")
        result = self.run_py(script, "--plan", plan, "--today", "2026-10-03", "--apply")
        for key in ("canonical_lang", "stakeholder_lang", "stakeholder_lang_code"):
            self.assertIn(key, result.stderr)
        self.assertFalse({"canonical_lang", "stakeholder_lang", "stakeholder_lang_code"} & set(self.subtree_config("orders")))


if __name__ == "__main__":
    unittest.main()
