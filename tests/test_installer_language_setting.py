"""Spec 0005 task 9 — the installer sets Claude Code's `language` setting
(FR-07, AC-06; ADR 0023 section 7). Recorded scalar keys in the manifest.
"""
import json
import os
import unittest

from test_installer_language import LanguageCase, PT


class TestInstallerLanguageSetting(LanguageCase):
    @property
    def settings_path(self):
        return os.path.join(self.config, "settings.json")

    def settings(self):
        return json.loads(self.read(self.settings_path))

    def put_language(self, value):
        data = json.loads(self.original_settings)
        data["language"] = value
        self.original_settings = json.dumps(data, indent=2) + "\n"
        self.write(self.settings_path, self.original_settings)

    def raw(self):
        with open(self.settings_path, "rb") as f:
            return f.read()

    def test_l19_absent_is_set_and_recorded(self):  # FR-07, AC-06
        self.build_cache()
        self.install("--apply", *PT)
        self.assertEqual(self.settings()["language"], "Portuguese")
        self.assertEqual(self.manifest()["settings"]["added_scalars"], {"language": "Portuguese"})
        self.install("--apply")  # idempotent upgrade keeps it
        self.assertEqual(self.settings()["language"], "Portuguese")

    def test_l19_english_install_writes_nothing(self):  # FR-07
        self.install("--apply")
        self.assertNotIn("language", self.settings())
        self.assertNotIn("added_scalars", self.manifest()["settings"])

    def test_l19_equal_value_is_not_recorded(self):  # FR-07
        self.put_language("Portuguese")
        self.build_cache()
        self.install("--apply", *PT)
        self.assertNotIn("added_scalars", self.manifest()["settings"])
        self.uninstall("--apply")
        self.assertEqual(self.raw(), self.original_settings.encode())

    def test_l19_different_value_is_shown_and_left_alone_without_the_flag(self):  # FR-07, AC-06
        self.put_language("Spanish")
        self.build_cache()
        dry = self.install(*PT)
        self.assertIn("'Spanish', left alone", dry.stdout)
        self.install("--apply", *PT)
        self.assertEqual(self.settings()["language"], "Spanish")
        self.assertNotIn("added_scalars", self.manifest()["settings"])
        self.uninstall("--apply")
        self.assertEqual(self.raw(), self.original_settings.encode())

    def test_l19_flag_overwrites_and_uninstall_restores_the_previous_value(self):  # FR-07, AC-06
        self.put_language("Spanish")
        self.build_cache()
        self.install("--apply", *PT, "--set-language-setting")
        self.assertEqual(self.settings()["language"], "Portuguese")
        self.install("--apply")  # the overwrite sticks on upgrade without the flag
        self.assertEqual(self.settings()["language"], "Portuguese")
        self.uninstall("--apply")
        self.assertEqual(self.raw(), self.original_settings.encode())

    def test_l19_overwrite_is_not_sticky_once_the_user_changed_the_value(self):  # FR-07, AC-06
        self.put_language("Spanish")
        self.build_cache()
        self.install("--apply", *PT, "--set-language-setting")
        settings = self.settings()
        settings["language"] = "French"  # the user changed it since the overwrite
        self.write(self.settings_path, json.dumps(settings, indent=2) + "\n")
        dry = self.install(*PT)
        self.assertIn("'French', left alone", dry.stdout)
        self.install("--apply", *PT)
        self.assertEqual(self.settings()["language"], "French")

    def test_l19_uninstall_removes_it_only_while_unchanged(self):  # FR-07, AC-06
        self.build_cache()
        self.install("--apply", *PT)
        settings = self.settings()
        settings["language"] = "French"  # the user changed it since
        self.write(self.settings_path, json.dumps(settings, indent=2) + "\n")
        self.uninstall("--apply")
        self.assertEqual(self.settings()["language"], "French")

    def test_l19_uninstall_restores_settings_byte_for_byte(self):  # FR-07, AC-06
        self.build_cache()
        self.install("--apply", *PT)
        self.uninstall("--apply")
        self.assertEqual(self.raw(), self.original_settings.encode())


if __name__ == "__main__":
    unittest.main()
