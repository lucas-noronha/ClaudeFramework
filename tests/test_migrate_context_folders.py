"""Spec 0006 FR-18 / AC-11 — migrate_context.py imports specs as folders."""
import json
import os
import unittest

from helpers import REPO, TempCase

SCRIPT = os.path.join(REPO, ".claude", "scripts", "migrate_context.py")

FULL_SPEC = (
    "---\ntitulo: Checkout\n---\n# Checkout\n\n## Business context\nWhy. See [arch](../arch/orders.md).\n\n"
    "## Technical plan\n**Tier:** standard\n\n### Approach\nDo it.\n\n"
    "## Tasks\n- [ ] 1. Build it\n\n## Reconciliation\nAll good.\n"
)


class TestMigrateContextFolders(TempCase):
    def run_import(self, src, dest, *extra):
        return json.loads(self.run_py(SCRIPT, "--source", src, "--dest", dest,
                                      "--rename-key", "titulo=title", *extra, check=False).stdout)

    def make_source(self):
        src = os.path.join(self.tmp, "context")
        self.write(os.path.join(src, "specs", "checkout.md"), FULL_SPEC)
        self.write(os.path.join(src, "specs", "simple.md"), "# Simple\n\n## Business context\nJust this.\n")
        self.write(os.path.join(src, "arch", "orders.md"), "# Orders\nSee [checkout](../specs/checkout.md).\n")
        return src

    def test_s13_import_with_plan_and_tasks_lands_as_folder_fr18_ac11(self):
        src = self.make_source()
        before = self.snapshot(src)
        dest = os.path.join(self.tmp, "subtree")
        dry = self.run_import(src, dest)
        self.assertFalse(os.path.exists(dest))
        self.assertEqual(dry["spec_folders"], ["product/specs/0001-checkout", "product/specs/0002-simple"])
        report = self.run_import(src, dest, "--apply")
        self.assertEqual((report["broken_links_introduced"], report["docs_missing_required_keys"]), ([], []))
        self.assertTrue(report["source_unchanged"])
        self.assertEqual(before, self.snapshot(src))
        folder = os.path.join(dest, "product", "specs", "0001-checkout")
        self.assertEqual(sorted(os.listdir(folder)), ["plan.md", "reconciliation.md", "spec.md", "tasks.md"])
        spec = self.read(os.path.join(folder, "spec.md"))
        self.assertIn("title: Checkout", spec)
        self.assertIn("id: 0001", spec)
        self.assertIn("tier: standard", spec)
        self.assertNotIn("## Tasks", spec)
        self.assertIn("(../../../architecture/orders.md)", spec)
        self.assertIn("- [ ] 1. Build it", self.read(os.path.join(folder, "tasks.md")))
        self.assertIn("# Technical plan", self.read(os.path.join(folder, "plan.md")))
        self.assertEqual(os.listdir(os.path.join(dest, "product", "specs", "0002-simple")), ["spec.md"])
        self.assertIn("(../product/specs/0001-checkout/spec.md)", self.read(os.path.join(dest, "architecture", "orders.md")))


if __name__ == "__main__":
    unittest.main()
