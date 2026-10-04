"""The spec layout resolver `_spec_layout.py` (framework spec 0006 task 1,
framework ADR 0024 sections 1 and 7).
"""
import json
import os
import sys
import unittest

from helpers import HOOKS, TempCase, posix

sys.path.insert(0, HOOKS)
import _spec_layout as layout  # noqa: E402

SCRIPT = os.path.join(HOOKS, "_spec_layout.py")


def spec_text(spec_id, lite=False, eol="\n", bom=False):
    lines = ["---", "id: " + spec_id, "status: approved"]
    if lite:
        lines.append("lite: true")
    lines += ["---", "", "# Spec", "", "## Tasks", "- [ ] one", "", "## Reconciliation", "ok", ""]
    return ("﻿" if bom else "") + eol.join(lines)


class LayoutCase(TempCase):
    def setUp(self):
        super().setUp()
        self.specs = os.path.join(self.tmp, "repo", "docs", "product", "specs")
        self.write_raw("0001-legacy-thing.md", spec_text("0001"))
        self.write_raw("0002-folder-thing/spec.md", spec_text("0002"))
        self.write_raw("0002-folder-thing/plan.md", "# Plan\n")
        self.write_raw("0002-folder-thing/tasks.md", "## Tasks\n- [ ] a\n")
        self.write_raw("0002-folder-thing/reconciliation.md", "# R\n")
        self.write_raw("0002-folder-thing/scratch.md", "notes\n")
        self.write_raw("0002-folder-thing/deep/more.md", "deep\n")
        self.write_raw("0003-quick-fix/spec.md", spec_text("0003", lite=True))
        self.write_raw("README.md", "index\n")

    def p(self, rel):
        return os.path.join(self.specs, *rel.split("/"))

    def write_raw(self, rel, text):
        path = self.p(rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)

    def cli(self, *args):
        return self.run_py(SCRIPT, *args, "--specs-dir", self.specs, check=False)


class TestClassify(LayoutCase):
    def test_s01_classify_legacy_folder_roles_lite_and_id(self):
        # FR-01, FR-03, FR-06, FR-15
        legacy = layout.classify(self.specs, self.p("0001-legacy-thing.md"))
        self.assertEqual((legacy["layout"], legacy["id"], legacy["role"]), ("legacy", "0001", "spec"))
        self.assertEqual(legacy["tasks"]["file"], self.p("0001-legacy-thing.md"))
        roles = {name: layout.classify(self.specs, self.p("0002-folder-thing/" + name))["role"]
                 for name in ("spec.md", "plan.md", "tasks.md", "reconciliation.md", "scratch.md")}
        self.assertEqual(roles, {"spec.md": "spec", "plan.md": "plan", "tasks.md": "tasks",
                                 "reconciliation.md": "reconciliation", "scratch.md": "note"})
        ref = layout.classify(self.specs, self.p("0002-folder-thing/tasks.md"))
        self.assertEqual((ref["layout"], ref["id"]), ("folder", "0002"))
        self.assertEqual(ref["status_file"], self.p("0002-folder-thing/spec.md"))
        self.assertEqual(ref["tasks"]["file"], self.p("0002-folder-thing/tasks.md"))
        self.assertEqual(ref["reconciliation"]["file"], self.p("0002-folder-thing/reconciliation.md"))
        lite = layout.classify(self.specs, self.p("0003-quick-fix/spec.md"))
        self.assertEqual((lite["layout"], lite["lite"]), ("lite", True))
        self.assertEqual(lite["tasks"], {"file": self.p("0003-quick-fix/spec.md"), "section": "Tasks"})
        self.assertEqual(lite["reconciliation"]["section"], "Reconciliation")

    def test_s01_lite_is_detected_by_frontmatter_not_name(self):
        # FR-06
        self.write_raw("0004-plain-name/spec.md", spec_text("0004", lite=True))
        self.write_raw("0005-quick-but-not/spec.md", spec_text("0005"))
        self.assertEqual(layout.classify(self.specs, self.p("0004-plain-name/spec.md"))["layout"], "lite")
        self.assertEqual(layout.classify(self.specs, self.p("0005-quick-but-not/spec.md"))["layout"], "folder")

    def test_s01_id_from_frontmatter_else_prefix_and_ignored_paths(self):
        # FR-15, FR-01
        self.write_raw("0007-no-fm.md", "# no frontmatter\n")
        self.write_raw("0008-other/spec.md", spec_text("0099"))
        self.assertEqual(layout.classify(self.specs, self.p("0007-no-fm.md"))["id"], "0007")
        self.assertEqual(layout.classify(self.specs, self.p("0008-other/spec.md"))["id"], "0099")
        for rel in ("0002-folder-thing/deep/more.md", "README.md", "notes.md", ".0009-x/spec.md",
                    "0002-folder-thing/image.png"):
            self.assertIsNone(layout.classify(self.specs, self.p(rel)), rel)
        self.assertIsNone(layout.classify(self.specs, os.path.join(self.tmp, "elsewhere", "0001-x.md")))

    def test_s01_crlf_and_bom_parse(self):
        # FR-15
        self.write_raw("0010-crlf.md", spec_text("0010", eol="\r\n", bom=True))
        self.write_raw("0011-crlf-lite/spec.md", spec_text("0011", lite=True, eol="\r\n", bom=True))
        self.assertEqual(layout.classify(self.specs, self.p("0010-crlf.md"))["id"], "0010")
        lite = layout.classify(self.specs, self.p("0011-crlf-lite/spec.md"))
        self.assertTrue(lite["lite"])
        body = layout.section(layout.read_text(self.p("0011-crlf-lite/spec.md")), "Tasks")
        self.assertIn("- [ ] one", body)
        self.assertNotIn("\r", body)


class TestCli(LayoutCase):
    def test_s02_resolve_by_path_folder_and_number_across_layouts(self):
        # FR-11, FR-15
        by_path = json.loads(self.cli("resolve", self.p("0002-folder-thing/plan.md")).stdout)
        self.assertEqual((by_path["layout"], by_path["role"], by_path["id"]), ("folder", "plan", "0002"))
        by_folder = json.loads(self.cli("resolve", self.p("0002-folder-thing")).stdout)
        self.assertEqual(by_folder["status_file"], self.p("0002-folder-thing/spec.md"))
        self.assertIn("tasks.md", by_folder["files"])
        by_name = json.loads(self.cli("resolve", "0002-folder-thing").stdout)
        self.assertEqual(by_name["folder"], by_folder["folder"])
        for number, expected in (("0001", "legacy"), ("0002", "folder"), ("0003", "lite")):
            self.assertEqual(json.loads(self.cli("resolve", number).stdout)["layout"], expected)
        self.assertEqual(self.cli("resolve", "0042").returncode, 1)

    def test_s02_next_number_spans_layouts(self):
        # FR-11
        self.assertEqual(self.cli("next-number").stdout.strip(), "0004")
        self.write_raw("0020-legacy-high.md", spec_text("0020"))
        self.assertEqual(self.cli("next-number").stdout.strip(), "0021")
        self.write_raw("0030-folder-high/note.md", "no spec file\n")
        self.assertEqual(self.cli("next-number").stdout.strip(), "0031")

    def test_s02_next_number_empty_and_default_specs_dir(self):
        # FR-11
        repo = os.path.join(self.tmp, "proj")
        os.makedirs(os.path.join(repo, "docs", "product", "specs"))
        result = self.run_py(SCRIPT, "next-number", project_dir=repo)
        self.assertEqual(result.stdout.strip(), "0001")
        sys.path.insert(0, HOOKS)
        import _project_paths
        self.assertEqual(posix(_project_paths.specs_dir(repo)), posix(os.path.join(repo, "docs", "product", "specs")))


class TestBranch(LayoutCase):
    def test_s10_branch_short_name_drops_number_and_keeps_quick(self):
        # FR-14, AC-12
        self.write_raw("0012-quick-foo/spec.md", spec_text("0012", lite=True))
        self.write_raw("0004-worktree-sessions.md", spec_text("0004"))
        quick = json.loads(self.cli("resolve", "0012").stdout)
        self.assertEqual((quick["short_name"], quick["branch"]), ("quick-foo", "task/quick-foo"))
        legacy = json.loads(self.cli("resolve", "0004").stdout)
        self.assertEqual((legacy["short_name"], legacy["branch"]), ("worktree-sessions", "task/worktree-sessions"))
        folder = json.loads(self.cli("resolve", "0002").stdout)
        self.assertEqual(folder["short_name"], "folder-thing")


if __name__ == "__main__":
    unittest.main()
