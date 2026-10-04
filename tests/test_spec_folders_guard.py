"""The number guard `spec_number_guard.py` across spec layouts (framework
spec 0006 task 3, framework ADR 0024 section 3): S06, FR-11, AC-06.
"""
import json
import os
import unittest

from helpers import HOOKS, TempCase


class NumberGuardCase(TempCase):
    def setUp(self):
        super().setUp()
        self.repo = os.path.join(self.tmp, "repo")
        self.specs = os.path.join(self.repo, "docs", "product", "specs")
        self.write(os.path.join(self.specs, "0001-legacy-thing.md"), "---\nid: 0001\n---\n")
        self.write(os.path.join(self.specs, "0002-folder-thing", "spec.md"), "---\nid: 0002\n---\n")
        self.write(os.path.join(self.specs, "0003-quick-fix", "spec.md"), "---\nid: 0003\nlite: true\n---\n")
        self.write(os.path.join(self.specs, "0004-half.md"), "---\nid: 0004\n---\n")
        self.write(os.path.join(self.specs, "0004-half", "spec.md"), "---\nid: 0004\n---\n")

    def guard(self, *rel):
        path = os.path.join(self.specs, *rel)
        result = self.hook(HOOKS, "spec_number_guard.py", {"tool_input": {"file_path": path}}, self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else None

    def assertDenied(self, out, num, other):
        self.assertIsNotNone(out, "expected a deny")
        hso = out["hookSpecificOutput"]
        self.assertEqual(hso["permissionDecision"], "deny")
        self.assertIn(f"Spec number {num} is already used by {other}", hso["permissionDecisionReason"])

    # S06 (FR-11, AC-06)
    def test_denies_collision_with_a_folder(self):
        self.assertDenied(self.guard("0002-other-name.md"), "0002", "0002-folder-thing")
        self.assertDenied(self.guard("0002-other-name", "spec.md"), "0002", "0002-folder-thing")

    def test_denies_collision_with_a_lite_folder(self):
        self.assertDenied(self.guard("0003-another.md"), "0003", "0003-quick-fix")

    def test_denies_collision_with_a_legacy_file(self):
        self.assertDenied(self.guard("0001-new-thing.md"), "0001", "0001-legacy-thing.md")
        self.assertDenied(self.guard("0001-new-thing", "spec.md"), "0001", "0001-legacy-thing.md")

    def test_denies_collision_with_a_half_migrated_spec(self):
        out = self.guard("0004-other.md")
        self.assertIsNotNone(out)
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIsNotNone(self.guard("0004-other", "spec.md"))

    def test_allows_companion_files_inside_an_existing_folder(self):
        for name in ("plan.md", "tasks.md", "reconciliation.md", "notes.md"):
            self.assertIsNone(self.guard("0002-folder-thing", name), name)
            self.assertIsNone(self.guard("0003-quick-fix", name), name)
        self.assertIsNone(self.guard("0004-half", "plan.md"))

    def test_allows_editing_an_existing_spec_and_a_free_number(self):
        self.assertIsNone(self.guard("0001-legacy-thing.md"))
        self.assertIsNone(self.guard("0002-folder-thing", "spec.md"))
        self.assertIsNone(self.guard("0004-half.md"))
        self.assertIsNone(self.guard("0005-brand-new.md"))
        self.assertIsNone(self.guard("0005-brand-new", "spec.md"))

    def test_ignores_files_outside_the_specs_folder(self):
        path = os.path.join(self.repo, "docs", "product", "0002-x.md")
        result = self.hook(HOOKS, "spec_number_guard.py", {"tool_input": {"file_path": path}}, self.repo)
        self.assertEqual(result.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
