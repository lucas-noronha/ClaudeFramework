"""The setup-language lookup in `_project_paths.py` (framework spec 0005
task 1, framework ADR 0023 section 1).
"""
import json
import os
import shutil
import unittest

from helpers import HOOKS, TempCase, posix


class LanguageCase(TempCase):
    def setUp(self):
        super().setUp()
        self.claude = os.path.join(self.tmp, "fw", ".claude")
        os.makedirs(os.path.join(self.claude, "hooks"))
        shutil.copy(os.path.join(HOOKS, "_project_paths.py"), os.path.join(self.claude, "hooks"))
        self.script = os.path.join(self.claude, "hooks", "_project_paths.py")
        self.repo = os.path.join(self.tmp, "my-app")
        os.makedirs(os.path.join(self.repo, "docs"))

    def put(self, name, data):
        self.write(os.path.join(self.claude, name), json.dumps(data))

    def put_project(self, data):
        # The project's own config (mode A location), apart from the setup's.
        self.write(os.path.join(self.repo, ".claude", "project-config.json"), json.dumps(data))

    def describe(self):
        return json.loads(self.run_py(self.script, "describe", self.repo).stdout)


class TestSetupLanguage(LanguageCase):
    def test_l01_lookup_order_framework_json_then_setup_config_then_legacy_then_english(self):
        # FR-02, NFR-05
        self.assertEqual(self.describe()["language"], {"name": "English", "code": "en", "source": "default"})
        self.put_project({"canonical_lang": "Spanish"})
        self.assertEqual(self.describe()["language"], {"name": "Spanish", "code": None, "source": "legacy"})
        self.put("project-config.json", {"language": "Portuguese", "language_code": "pt-BR"})
        self.assertEqual(self.describe()["language"],
                         {"name": "Portuguese", "code": "pt-BR", "source": "project-config"})
        self.put("framework.json", {"language": "French", "language_code": "fr"})
        self.assertEqual(self.describe()["language"], {"name": "French", "code": "fr", "source": "framework.json"})

    def test_l02_describe_reports_language_and_legacy_split(self):
        # FR-02
        self.assertFalse(self.describe()["legacy_split"])
        self.put_project({"canonical_lang": "English", "stakeholder_lang": "Portuguese",
                          "stakeholder_lang_code": "pt"})
        described = self.describe()
        self.assertTrue(described["legacy_split"])
        self.assertEqual(described["language"]["source"], "legacy")
        self.put("project-config.json", {"language": "Portuguese", "language_code": "pt"})
        self.assertFalse(self.describe()["legacy_split"])
        self.assertEqual(posix(self.describe()["project_dir"]), posix(self.repo))

    def test_l02_no_actual_split_is_not_legacy_split(self):
        # FR-02, NFR-05
        for config in ({"canonical_lang": "English"},
                       {"canonical_lang": "English", "stakeholder_lang": "english", "stakeholder_lang_code": "en"}):
            self.put_project(config)
            self.assertFalse(self.describe()["legacy_split"], config)

    def test_l01_legacy_english_is_normalized(self):
        # FR-02, NFR-05
        for legacy in ("English", "english", "en", "en-US"):
            self.put_project({"canonical_lang": legacy})
            self.assertEqual(self.describe()["language"], {"name": "English", "code": "en", "source": "legacy"}, legacy)


if __name__ == "__main__":
    unittest.main()
