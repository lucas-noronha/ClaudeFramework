"""Spec 0005 task 2 — routing keys: primary + read aliases (FR-12, AC-10)."""
import json
import os
import sys
import unittest

from helpers import HOOKS, TempCase

sys.path.insert(0, HOOKS)
import _project_paths  # noqa: E402

ARCH_FM = "---\ndoc_type: architecture\nstatus: active\ncontext_budget: ~400 tokens\n{extra}---\n"


class TestRoutingKeys(TempCase):
    def test_l04_defaults_are_summary_and_notfor_with_aliases(self):  # FR-12, AC-10
        repo = self.make_repo("app")
        keys = _project_paths.routing_keys(repo)
        self.assertEqual(keys["summary"], {"key": "summary", "aliases": ["resumo"]})
        self.assertEqual(keys["notFor"], {"key": "notFor", "aliases": ["naoResponde"]})

    def test_l04_project_override_replaces_the_primary_only(self):  # FR-12, AC-10
        repo = self.make_repo("app")
        self.write(os.path.join(repo, ".claude", "project-config.json"),
                   json.dumps({"routing_keys": {"summary": "answers", "not_for": "excludes"}}))
        keys = _project_paths.routing_keys(repo)
        self.assertEqual(keys["summary"], {"key": "answers", "aliases": ["resumo"]})
        self.assertEqual(keys["notFor"], {"key": "excludes", "aliases": ["naoResponde"]})

    def test_l04_override_naming_the_alias_is_not_listed_twice(self):  # FR-12
        repo = self.make_repo("app")
        self.write(os.path.join(repo, ".claude", "project-config.json"), json.dumps({"routing_keys": {"summary": "resumo"}}))
        self.assertEqual(_project_paths.routing_keys(repo)["summary"], {"key": "resumo", "aliases": []})

    def test_l04_primary_wins_over_an_alias(self):  # FR-12, AC-10
        repo = self.make_repo("app")
        doc = os.path.join(repo, "docs", "architecture", "overview.md")
        self.write(doc, ARCH_FM.format(extra="resumo: Old question?\nsummary: New question?\n"))
        self.write(os.path.join(repo, "CLAUDE.md"), "| Old question? | `docs/architecture/overview.md` | ~400 tok |\n")
        out = self.hook(HOOKS, "claude_md_index_check.py", {"tool_input": {"file_path": doc}}, repo).stdout
        self.assertIn("New question?", out)
        self.assertNotIn("Old question?\"", out)
        self.write(os.path.join(repo, "CLAUDE.md"), "| New question? | `docs/architecture/overview.md` | ~400 tok |\n")
        self.assertEqual(self.hook(HOOKS, "claude_md_index_check.py", {"tool_input": {"file_path": doc}}, repo).stdout.strip(), "")

    def test_l05_frontmatter_check_accepts_the_alias_and_names_the_primary(self):  # FR-12, AC-10
        repo = self.make_repo("app")
        doc = os.path.join(repo, "docs", "architecture", "overview.md")
        self.write(doc, ARCH_FM.format(extra="resumo: What is the shape?\nnaoResponde: Nothing.\n"))
        self.assertEqual(self.hook(HOOKS, "frontmatter_check.py", {"tool_input": {"file_path": doc}}, repo).stdout.strip(), "")
        self.write(doc, ARCH_FM.format(extra=""))
        self.assertIn("`summary`", self.hook(HOOKS, "frontmatter_check.py", {"tool_input": {"file_path": doc}}, repo).stdout)

    def test_l05_index_check_reads_resumo_alias_as_before(self):  # FR-12, AC-10
        repo = self.make_repo("app")
        doc = os.path.join(repo, "docs", "architecture", "overview.md")
        self.write(doc, ARCH_FM.format(extra="resumo: What is the shape?\n"))
        self.write(os.path.join(repo, "CLAUDE.md"), "| Architecture overview | `docs/architecture/overview.md` | ~400 tok |\n")
        out = self.hook(HOOKS, "claude_md_index_check.py", {"tool_input": {"file_path": doc}}, repo).stdout
        self.assertIn("The doc wins", out)
        self.assertIn("`summary`", out)
        self.write(os.path.join(repo, "CLAUDE.md"), "| What is the shape? | `docs/architecture/overview.md` | ~400 tok |\n")
        self.assertEqual(self.hook(HOOKS, "claude_md_index_check.py", {"tool_input": {"file_path": doc}}, repo).stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
