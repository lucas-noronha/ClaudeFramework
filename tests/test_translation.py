"""`translation.py` core (framework spec 0005 task 3, framework ADR 0023
section 2): the record, `plan` and `apply`. Hand-written Portuguese
fixtures; no model is ever called.
"""
import json
import os
import unittest

from helpers import SCRIPTS, TempCase

SCRIPT = os.path.join(SCRIPTS, "translation.py")
PT = ("--language-code", "pt-BR")


class TranslationCase(TempCase):
    def setUp(self):
        super().setUp()
        self.src = os.path.join(self.tmp, "pristine")
        self.stage = os.path.join(self.tmp, "staging")
        self.record = os.path.join(self.tmp, "out", "translation-record.json")
        self.write(os.path.join(self.src, "commands", "spec.md"), "# Spec\n\nWrite the spec.\n")
        self.write(os.path.join(self.src, "docs", "guide.md.template"), "# Guide\n\nHello {{NAME}}.\n")
        self.write(os.path.join(self.src, "skills", "README.md"), "# generated index\n")
        self.write(os.path.join(self.src, "settings.json"), "{}\n")
        self.write(os.path.join(self.src, "hooks", "x.py"), "print(1)\n")
        self.write(os.path.join(self.src, "a.md.example"), "x\n")

    def plan(self, *extra, code="pt-BR"):
        out = self.run_py(SCRIPT, "plan", "--source", self.src, "--record", self.record,
                          "--language-code", code, *extra).stdout
        return json.loads(out)

    def apply(self, rel, text, dest=None, policy="replace", code="pt-BR", extra=()):
        staged = os.path.join(self.stage, rel)
        self.write(staged, text)
        args = ["apply", "--source", self.src, "--record", self.record, "--language-code", code,
                "--language", "Portuguese", "--path", rel, "--staged", staged, "--policy", policy, *extra]
        if dest:
            args += ["--dest", dest]
        return json.loads(self.run_py(SCRIPT, *args).stdout)

    def paths(self, report, key="new"):
        return sorted(i["path"] for i in report[key])

    def load(self):
        with open(self.record, encoding="utf-8") as f:
            return json.load(f)


class TestPlan(TranslationCase):
    def test_l06_plan_lists_only_translatable_new_and_changed(self):  # FR-06, NFR-06, AC-09
        first = self.plan()
        self.assertEqual(self.paths(first), ["commands/spec.md", "docs/guide.md.template"])
        self.assertGreater(first["estimated_tokens"], 0)
        self.assertEqual(first["token_heuristic"], "chars/4")
        dest = os.path.join(self.tmp, "installed")
        self.apply("commands/spec.md", "# Spec\n\nEscreva a spec.\n", os.path.join(dest, "spec.md"))
        self.apply("docs/guide.md.template", "# Guia\n\nOla {{NAME}}.\n", os.path.join(dest, "guide.md"))
        again = self.plan()
        self.assertTrue(again["noop"])
        self.assertEqual((again["new"], again["changed"], again["estimated_tokens"]), ([], [], 0))
        self.write(os.path.join(self.src, "commands", "spec.md"), "# Spec\n\nWrite the spec well.\n")
        self.write(os.path.join(self.src, "commands", "new.md"), "# New\n")
        changed = self.plan()
        self.assertEqual(self.paths(changed, "changed"), ["commands/spec.md"])
        self.assertEqual(self.paths(changed, "new"), ["commands/new.md"])

    def test_l06_crlf_only_difference_is_not_a_change(self):  # FR-06, NFR-06
        self.apply("commands/spec.md", "# Spec\n\nEscreva.\n", os.path.join(self.tmp, "o", "spec.md"))
        with open(os.path.join(self.src, "commands", "spec.md"), "wb") as f:
            f.write(b"\xef\xbb\xbf# Spec\r\n\r\nWrite the spec.\r\n")  # BOM + CRLF
        self.assertNotIn("commands/spec.md", self.paths(self.plan(), "changed"))

    def test_l07_english_plan_and_apply_are_noops_and_write_no_record(self):  # AC-09, NFR-06
        for code in ("en", "en-US"):
            report = self.plan(code=code)
            self.assertTrue(report["noop"])
            self.assertEqual((report["new"], report["changed"]), ([], []))
            dest = os.path.join(self.tmp, "out", "spec.md")
            self.assertTrue(self.apply("commands/spec.md", "x\n", dest, code=code)["noop"])
            self.assertFalse(os.path.exists(dest))
            self.assertFalse(os.path.exists(self.record))


class TestApply(TranslationCase):
    def test_l11_apply_retranslates_only_changed_replace_sources(self):  # FR-06, NFR-06
        dest = os.path.join(self.tmp, "installed", "spec.md")
        self.apply("commands/spec.md", "# Spec\n\nEscreva a spec.\n", dest)
        entry = self.load()["files"]["commands/spec.md"]
        self.assertEqual((entry["status"], entry["policy"], entry["dest"]), ("translated", "replace", dest.replace("\\", "/")))
        self.assertEqual(len(entry["source_sha256"]), 64)
        self.assertEqual(len(entry["output_sha256"]), 64)
        self.assertEqual(self.load()["language_code"], "pt-BR")
        self.assertNotIn("commands/spec.md", self.paths(self.plan()) + self.paths(self.plan(), "changed"))
        self.write(os.path.join(self.src, "commands", "spec.md"), "# Spec\n\nChanged.\n")
        self.assertEqual(self.paths(self.plan(), "changed"), ["commands/spec.md"])
        self.apply("commands/spec.md", "# Spec\n\nMudou.\n", dest)
        self.assertIn("Mudou", self.read(dest))
        self.assertNotIn("commands/spec.md", self.paths(self.plan(), "changed"))

    def test_l11_keep_file_is_translated_only_on_create(self):  # FR-06, NFR-06
        dest = os.path.join(self.tmp, "installed", "guide.md")
        self.apply("docs/guide.md.template", "# Guia\n", dest, policy="keep")
        self.assertEqual(self.read(dest), "# Guia\n")
        self.write(dest, "# Guia editado\n")  # the user's own edit
        self.write(os.path.join(self.src, "docs", "guide.md.template"), "# Guide v2\n")
        report = self.plan()
        self.assertEqual(report["changed"], [])
        self.assertEqual(report["skipped_keep"], ["docs/guide.md.template"])
        result = self.apply("docs/guide.md.template", "# Guia v2\n", dest, policy="keep")
        self.assertEqual(result["status"], "existing")
        self.assertEqual(self.read(dest), "# Guia editado\n")

    def test_keep_existing_destination_is_not_overwritten_on_first_apply(self):  # FR-06
        dest = os.path.join(self.tmp, "installed", "guide.md")
        self.write(dest, "# Meu\n")
        self.apply("docs/guide.md.template", "# Guia\n", dest, policy="keep")
        self.assertEqual(self.read(dest), "# Meu\n")
        self.assertEqual(self.paths(self.plan(), "new"), ["commands/spec.md"])

    def test_mode_c_apply_writes_cache_beside_record_without_dest_fields(self):  # ADR 0023 section 2
        self.apply("commands/spec.md", "# Spec pt\n")
        cached = os.path.join(os.path.dirname(self.record), "commands", "spec.md")
        self.assertEqual(self.read(cached), "# Spec pt\n")
        entry = self.load()["files"]["commands/spec.md"]
        self.assertNotIn("dest", entry)
        self.assertNotIn("output_sha256", entry)

    def test_terms_placeholders_and_english_status_are_recorded(self):  # ADR 0023 section 2
        terms = os.path.join(self.tmp, "terms.json")
        ph = os.path.join(self.tmp, "ph.json")
        self.write(terms, json.dumps({"spec": "especificacao"}))
        self.write(ph, json.dumps({"NAME": "Acme"}))
        self.apply("commands/spec.md", "x\n", extra=("--terms", terms, "--placeholders", ph,
                                                     "--status", "english", "--reason", "heading count"))
        record = self.load()
        self.assertEqual((record["terms"], record["placeholders"]), ({"spec": "especificacao"}, {"NAME": "Acme"}))
        entry = record["files"]["commands/spec.md"]
        self.assertEqual((entry["status"], entry["reason"]), ("english", "heading count"))
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(self.record), "commands", "spec.md")))
        self.assertNotIn("commands/spec.md", self.paths(self.plan()) + self.paths(self.plan(), "changed"))

    def test_new_language_retranslates_every_replace_file(self):  # ADR 0023 rules
        self.apply("commands/spec.md", "x\n")
        self.assertEqual(self.paths(self.plan(), "changed"), [])
        self.assertEqual(self.paths(self.plan(code="es"), "changed"), ["commands/spec.md"])

    def test_non_translatable_source_is_rejected(self):
        staged = os.path.join(self.stage, "s.json")
        self.write(staged, "{}")
        result = self.run_py(SCRIPT, "apply", "--source", self.src, "--record", self.record,
                             "--language-code", "pt", "--language", "Portuguese", "--path", "settings.json",
                             "--staged", staged, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(os.path.exists(self.record))


if __name__ == "__main__":
    unittest.main()
