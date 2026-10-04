"""Spec 0005 task 8 — the mode C installer reads the translation cache
(ADR 0023 section 2). Fixtures are hand-written Portuguese lines appended to
the English sources; no model is involved.
"""
import json
import os
import sys
import unittest

from helpers import REPO, SCRIPTS, posix
from test_user_level_install import InstallCase

sys.path.insert(0, SCRIPTS)
import install_user_level  # noqa: E402
import translation  # noqa: E402

MARKER = "Texto de teste em português (fixture)."
PT = ("--language", "Portuguese", "--language-code", "pt-BR")


class LanguageCase(InstallCase):
    @property
    def cache(self):
        return os.path.join(self.ns, "translations")

    def build_cache(self, only=None):
        """Translate (fixture) every shipped source the installer reads, via translation.apply."""
        staged = os.path.join(self.tmp, "staged.md")
        record = os.path.join(self.cache, "record.json")
        for rel in translation.list_sources(REPO):
            if not rel.startswith((".claude/", "docs/", "CLAUDE.md.template")):
                continue
            with open(os.path.join(REPO, rel), "rb") as f:
                source = translation.normalized_text(f.read())
            self.write(staged, source + "\n" + MARKER + "\n")
            result = translation.apply(REPO, record, "Portuguese", "pt-BR", rel, staged)
            self.assertNotIn("error", result)

    def manifest(self):
        with open(os.path.join(self.ns, "manifest.json"), encoding="utf-8") as f:
            return json.load(f)

    def record(self):
        return translation.load_record(os.path.join(self.cache, "record.json"))


class TestInstallerLanguage(LanguageCase):
    def test_l16_fresh_cache_installs_translated_bytes_and_is_idempotent(self):  # FR-05, NFR-02, AC-05
        self.build_cache()
        self.install("--apply", *PT)
        spec = self.read(os.path.join(self.config, "commands", "cfw-spec.md"))
        self.assertIn(MARKER, spec)
        self.assertNotRegex(spec, r"(?<![\w./-])/(plan|tasks|review|quick)(?![\w-])")  # rewrite ran on the translation
        self.assertIn("name: cfw-coder", self.read(os.path.join(self.config, "agents", "cfw-coder.md")))
        self.assertIn(MARKER, self.read(os.path.join(self.ns, "docs", "workflow", "ai-first-development.md")))
        cfg = self.framework()
        self.assertEqual((cfg["language"], cfg["language_code"]), ("Portuguese", "pt-BR"))
        entry = self.manifest()["files"][posix(os.path.join(self.config, "commands", "cfw-spec.md"))]
        self.assertEqual(entry["translation"], "translated")
        self.assertEqual(entry["source_sha256"], translation.file_sha256(os.path.join(REPO, ".claude", "commands", "spec.md")))
        hook = self.manifest()["files"][posix(os.path.join(self.ns, "hooks", "_project_paths.py"))]
        self.assertEqual(hook["translation"], "none")
        before = self.snapshot(self.config)
        # Idempotent, language kept across upgrades without repeating the flags.
        self.install("--apply")
        self.assertEqual(before, self.snapshot(self.config))
        self.assertEqual(self.framework()["language_code"], "pt-BR")

    def test_l16_hand_edit_of_a_translated_file_is_still_refused(self):  # NFR-02
        self.build_cache()
        self.install("--apply", *PT)
        path = os.path.join(self.config, "commands", "cfw-spec.md")
        self.write(path, self.read(path) + "edit\n")
        result = self.install("--apply", check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("edited by hand", result.stderr)

    def test_l16_english_status_entry_reads_the_source(self):  # FR-06
        self.build_cache()
        rel = ".claude/commands/spec.md"
        record_path = os.path.join(self.cache, "record.json")
        translation.apply(REPO, record_path, "Portuguese", "pt-BR", rel, "", status="english", reason="fixture")
        self.install("--apply", *PT)
        self.assertNotIn(MARKER, self.read(os.path.join(self.config, "commands", "cfw-spec.md")))
        entry = self.manifest()["files"][posix(os.path.join(self.config, "commands", "cfw-spec.md"))]
        self.assertEqual(entry["translation"], "english")

    def test_l17_stale_cache_entry_aborts_before_any_write(self):  # FR-06
        self.build_cache()
        record_path = os.path.join(self.cache, "record.json")
        record = self.record()
        record["files"][".claude/commands/spec.md"]["source_sha256"] = "0" * 64
        translation.save_record(record_path, record)
        before = self.snapshot(self.config)
        result = self.install("--apply", *PT, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn(".claude/commands/spec.md", result.stderr)
        self.assertEqual(before, self.snapshot(self.config))
        self.assertFalse(os.path.exists(os.path.join(self.ns, "manifest.json")))

    def test_l17_missing_cache_entry_aborts_before_any_write(self):  # FR-06
        self.build_cache()
        record_path = os.path.join(self.cache, "record.json")
        record = self.record()
        del record["files"]["docs/workflow/ai-first-development.md"]
        translation.save_record(record_path, record)
        before = self.snapshot(self.config)
        result = self.install("--apply", *PT, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("docs/workflow/ai-first-development.md", result.stderr)
        self.assertEqual(before, self.snapshot(self.config))

    def test_l17_no_cache_at_all_aborts(self):  # FR-06
        before = self.snapshot(self.config)
        result = self.install("--apply", *PT, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(before, self.snapshot(self.config))

    def test_l17_existing_keep_file_needs_no_cache_entry(self):  # ADR 0023 section 2
        self.build_cache()
        self.install("--apply", *PT)
        record_path = os.path.join(self.cache, "record.json")
        record = self.record()
        del record["files"]["docs/constitution.md"]
        translation.save_record(record_path, record)
        self.install("--apply")  # constitution.md exists and is `keep`: not required

    def test_language_flags_go_together(self):
        result = self.install("--language", "Portuguese", check=False)
        self.assertEqual(result.returncode, 2)

    def test_l18_english_install_is_identical_to_today(self):  # NFR-01, AC-08
        self.install("--apply")
        base = self.snapshot(self.config)
        self.assertNotIn("language", self.framework())
        self.assertFalse(os.path.isdir(self.cache))
        self.assertFalse(os.path.exists(os.path.join(self.config, "agents", "cfw-translator.md")))
        # A poisoned pt-BR cache must not be read for English, however it is requested.
        self.build_cache()
        for extra in (("--language", "English", "--language-code", "en"),
                      ("--language", "English", "--language-code", "en-GB")):
            self.install("--apply", *extra)
            now = self.snapshot(self.config)
            for key, data in base.items():
                if key.endswith(("cfw/framework.json", "cfw/manifest.json")):
                    continue
                self.assertEqual(data, now[key], key)
            self.assertNotIn(MARKER.encode("utf-8"), b"".join(v for k, v in now.items() if "translations/" not in k))

    def test_translator_agent_is_excluded_from_the_install(self):
        self.assertIn("translator", install_user_level.EXCLUDED_AGENTS)
        self.assertNotIn("translator", install_user_level.inventory()[0])

    def test_uninstall_removes_the_translation_cache(self):  # FR-05
        self.build_cache()
        self.install("--apply", *PT)
        self.assertTrue(os.path.isdir(self.cache))
        self.uninstall("--apply")
        self.assertFalse(os.path.exists(self.cache))
        self.assertFalse(os.path.exists(os.path.join(self.ns, "manifest.json")))


if __name__ == "__main__":
    unittest.main()
