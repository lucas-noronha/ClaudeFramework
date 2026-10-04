"""Spec folders: companion-file frontmatter and context-budget hooks (framework ADR 0024 section 5)."""
import json
import os
import unittest

from helpers import HOOKS, TempCase

SPEC_FM = "---\ndoc_type: spec\nstatus: draft\ncontext_budget: ~500\n---\n\n# Spec\n"


def companion(extra="", doc_type="plan", spec="0001", summary="summary: What is the plan?\n", budget="context_budget: ~300\n"):
    return f"---\ndoc_type: {doc_type}\nspec: {spec}\n{summary}{budget}{extra}---\n\n# Body\n"


class SpecFolderFrontmatterTests(TempCase):
    def check(self, hook, name, text, files=None):
        repo = self.make_repo("app")
        folder = os.path.join(repo, "docs", "product", "specs", "0001-thing")
        self.write(os.path.join(folder, "spec.md"), SPEC_FM)
        doc = os.path.join(folder, name)
        self.write(doc, text)
        out = self.hook(HOOKS, hook, {"tool_input": {"file_path": doc}}, repo).stdout.strip()
        return json.loads(out)["systemMessage"] if out else ""

    def test_s08_companion_complete_without_status_is_clean(self):  # FR-03, AC-16
        self.assertEqual(self.check("frontmatter_check.py", "plan.md", companion()), "")

    def test_s08_companion_asks_for_doc_type_spec_summary_budget_not_status(self):  # FR-03, FR-04, AC-16
        msg = self.check("frontmatter_check.py", "tasks.md", "---\ntier: standard\n---\n\n# T\n")
        for key in ("doc_type", "spec", "summary", "context_budget"):
            self.assertIn(key, msg)
        self.assertNotIn("status", msg)
        self.assertNotIn("tier", msg)

    def test_s08_summary_alias_is_accepted_on_a_companion(self):  # FR-04
        self.assertEqual(self.check("frontmatter_check.py", "reconciliation.md", companion(summary="resumo: Qual o plano?\n", doc_type="reconciliation")), "")

    def test_s08_extra_spec_note_with_summary_is_accepted(self):  # FR-05, AC-16
        self.assertEqual(self.check("frontmatter_check.py", "research.md", companion(doc_type="spec-note")), "")

    def test_s08_extra_spec_note_without_summary_is_nudged(self):  # FR-05
        msg = self.check("frontmatter_check.py", "research.md", companion(doc_type="spec-note", summary=""))
        self.assertIn("summary", msg)

    def test_s08_tier_is_a_known_key(self):  # FR-03
        self.assertEqual(self.check("frontmatter_check.py", "plan.md", companion(extra="tier: trivial\n")), "")

    def test_s08_spec_md_keeps_status_rule(self):  # FR-03
        msg = self.check("frontmatter_check.py", "spec.md", "---\ndoc_type: spec\ncontext_budget: ~500\n---\n")
        self.assertIn("status", msg)
        self.assertNotIn("summary", msg)

    def test_s08_legacy_single_file_keeps_status_rule(self):  # FR-03
        repo = self.make_repo("app")
        doc = os.path.join(repo, "docs", "product", "specs", "0002-old.md")
        self.write(doc, "---\ndoc_type: spec\ncontext_budget: ~500\n---\n")
        out = self.hook(HOOKS, "frontmatter_check.py", {"tool_input": {"file_path": doc}}, repo).stdout
        self.assertIn("status", out)
        self.assertNotIn("spec,", out)

    def test_s08_context_budget_judges_each_folder_file_on_its_own(self):  # NFR-03
        big = companion(budget="context_budget: ~10\n") + "word " * 200
        self.assertIn("context_budget", self.check("context_budget_check.py", "plan.md", big))

    def test_s08_context_budget_quiet_within_the_files_own_budget(self):  # NFR-03
        self.assertEqual(self.check("context_budget_check.py", "plan.md", companion(budget="context_budget: ~5000\n") + "word " * 200), "")


if __name__ == "__main__":
    unittest.main()
