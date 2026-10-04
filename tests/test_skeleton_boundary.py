"""The boundary between the framework's own evolution (its specs, ADRs,
changelog, tests) and the skeleton projects receive. See
`evolution/README.md`.

Shipped: `.claude/`, `docs/`, `CLAUDE.md.template`, `.mcp.json.example`,
`.gitignore.framework-additions`. Everything else is this repository's.
"""
import os
import re
import unittest

from helpers import REPO, TempCase

SHIPPED_ROOTS = [".claude", "docs"]
SHIPPED_FILES = ["CLAUDE.md.template", ".mcp.json.example", ".gitignore.framework-additions"]
TEXT = (".md", ".py", ".json", ".example", ".template", ".additions")


def shipped_text_files():
    for name in SHIPPED_FILES:
        yield os.path.join(REPO, name)
    for root in SHIPPED_ROOTS:
        for dirpath, dirnames, filenames in os.walk(os.path.join(REPO, root)):
            dirnames[:] = [d for d in dirnames if d not in ("__pycache__", "worktrees")]
            for name in filenames:
                if name.endswith(TEXT) and name != "settings.local.json":
                    yield os.path.join(dirpath, name)


class TestSkeletonBoundary(unittest.TestCase):
    def test_docs_carries_no_framework_spec_or_adr(self):
        decisions = os.listdir(os.path.join(REPO, "docs", "decisions"))
        self.assertEqual(decisions, ["0000-adr-template.md"])
        specs = os.path.join(REPO, "docs", "product", "specs")
        self.assertFalse(os.path.isdir(specs) and os.listdir(specs), "docs/product/specs/ must ship empty")

    def test_evolution_holds_them(self):
        adrs = os.listdir(os.path.join(REPO, "evolution", "decisions"))
        self.assertIn("0017-user-level-install-mechanics.md", adrs)
        self.assertNotIn("0000-adr-template.md", adrs)
        self.assertTrue(os.listdir(os.path.join(REPO, "evolution", "product", "specs")))

    def test_shipped_files_name_framework_documents_unambiguously(self):
        bare = re.compile(r"(?<!framework )(?<![\w-])ADR (00(?:0[1-9]|1[0-9]|20))\b")
        path = re.compile(r"(?:docs/)?decisions/00(?:0[1-9]|1[0-9]|20)-(?!(?:x|foo|bar)\.md)[\w-]+\.md|product/specs/000[123]-(?!(?:x|foo|bar)\.md)[\w-]+\.md")
        for full in shipped_text_files():
            with open(full, encoding="utf-8") as f:
                text = f.read()
            rel = os.path.relpath(full, REPO)
            self.assertEqual(bare.findall(text), [], f"{rel}: say 'framework ADR NNNN' — a bare number collides with the project's own ADRs")
            self.assertEqual(path.findall(text), [], f"{rel}: points into evolution/ content that projects never receive")


class TestInstallerShipsNoEvolution(TempCase):
    def test_install_output_has_no_framework_adr_or_spec(self):
        config = os.path.join(self.home, ".claude")
        self.run_py(os.path.join(REPO, ".claude", "scripts", "install_user_level.py"),
                    "--config-dir", config, "--today", "2026-10-03", "--apply")
        self.assertEqual(os.listdir(os.path.join(config, "cfw", "docs", "decisions")), ["0000-adr-template.md"])
        for dirpath, _, filenames in os.walk(config):
            self.assertNotIn("evolution", dirpath.replace("\\", "/").split("/"))
            for name in filenames:
                self.assertFalse(re.match(r"^00(?:0[1-9]|1[0-9]|20)-", name) and dirpath.endswith("decisions"), name)


if __name__ == "__main__":
    unittest.main()
