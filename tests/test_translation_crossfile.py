"""`translation.py` cross-file step and placeholder recovery (framework spec 0005
task 5, FR-06, FR-11; framework ADR 0023 sections 2, 3, 5). Hand-written
fixtures; no model is ever called.
"""
import json
import os
import sys
import unittest

from helpers import SCRIPTS, TempCase

sys.path.insert(0, SCRIPTS)
import install_user_level  # noqa: E402
import translation  # noqa: E402

CLAUDE_TPL = """# {{PROJECT_NAME}}

| I need... | Read | Cost |
|---|---|---|
| Spec helper. | `docs/a.md` | ~100 tok |
| Old text. | `docs/b.md` | ~200 tok |
| No summary doc. | `docs/c.md` | ~50 tok |
"""

DOC_A = "---\nsummary: Ajudante de specs.\n---\n# A\n"
DOC_B = "---\nresumo: Texto novo.\n---\n# B\n"
DOC_C = "---\ntitle: C\n---\n# C\n"


class CrossFile(TempCase):
    def write(self, rel, text, base=None):
        path = os.path.join(base or self.tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        return path

    def test_l12_cross_file_step_copies_summaries_into_index_rows_fr11(self):
        md = self.write("CLAUDE.md", CLAUDE_TPL.replace("\n", "\r\n"))
        self.write("docs/a.md", DOC_A)
        self.write("docs/b.md", DOC_B)
        self.write("docs/c.md", DOC_C)
        report = translation.sync_index(md, self.tmp)
        self.assertEqual(report["updated"], ["docs/a.md", "docs/b.md"])
        self.assertEqual(report["skipped"], ["docs/c.md"])
        with open(md, "rb") as f:
            raw = f.read().decode("utf-8")
        self.assertIn("| Ajudante de specs. | `docs/a.md` | ~100 tok |\r\n", raw)
        self.assertIn("| Texto novo. | `docs/b.md` | ~200 tok |\r\n", raw)  # alias `resumo`
        self.assertIn("| No summary doc. | `docs/c.md` | ~50 tok |\r\n", raw)  # untouched
        self.assertEqual(translation.sync_index(md, self.tmp)["updated"], [])  # idempotent

    def test_l13_recover_placeholders_rebuilds_map_fr06(self):
        src, res = os.path.join(self.tmp, "src"), os.path.join(self.tmp, "res")
        rec = os.path.join(self.tmp, "record.json")
        self.write("CLAUDE.md.template", "# {{PROJECT_NAME}}\nBranch {{BRANCH}}.\n", src)
        self.write("docs/x.md", "Project {{PROJECT_NAME}} on {{BRANCH}}\n", src)
        self.write("CLAUDE.md", "# Acme\nBranch main.\n".replace("\n", "\r\n"), res)  # renamed
        self.write("docs/x.md", "Project Acme on main\n", res)
        report = translation.recover_placeholders(src, res, rec)
        self.assertTrue(report["ok"])
        self.assertEqual(report["placeholders"], {"PROJECT_NAME": "Acme", "BRANCH": "main"})
        with open(rec, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["placeholders"], report["placeholders"])

    def test_l13_recover_placeholders_reports_non_match_and_disagreement_fr06(self):
        src, res = os.path.join(self.tmp, "src"), os.path.join(self.tmp, "res")
        rec = os.path.join(self.tmp, "record.json")
        self.write("docs/x.md", "Project {{PROJECT_NAME}}\n", src)
        self.write("docs/y.md", "Name {{PROJECT_NAME}}\n", src)
        self.write("docs/z.md", "Edited {{BRANCH}} here\n", src)
        self.write("docs/x.md", "Project Acme\n", res)
        self.write("docs/y.md", "Name Other\n", res)  # PROJECT_NAME disagrees
        self.write("docs/z.md", "Something else entirely\n", res)  # non-match
        report = translation.recover_placeholders(src, res, rec)
        self.assertFalse(report["ok"])
        self.assertEqual(report["non_matches"][0]["path"], "docs/z.md")
        self.assertEqual(set(report["disagreements"]["PROJECT_NAME"]), {"Acme", "Other"})
        self.assertNotIn("PROJECT_NAME", report["placeholders"])

    def test_runtime_token_list_equals_installer_tokens(self):
        expected = sorted(set(install_user_level.RUNTIME_TOKENS.values()) | {"<language>"})
        self.assertEqual(sorted(translation.RUNTIME_TOKEN_LIST), expected)
        self.assertEqual(translation._runtime_tokens(), sorted(translation.RUNTIME_TOKEN_LIST))


if __name__ == "__main__":
    unittest.main()
