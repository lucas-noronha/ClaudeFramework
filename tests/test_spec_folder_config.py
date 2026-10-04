"""Spec 0006 task 11: shipped settings templates and translation names."""
import json
import os
import re
import sys
import unittest

from helpers import REPO, SCRIPTS

sys.path.insert(0, SCRIPTS)
import translation  # noqa: E402

CLAUDE = os.path.join(REPO, ".claude")


def load(name):
    with open(os.path.join(CLAUDE, name), encoding="utf-8") as f:
        return json.load(f)


def glob_match(pattern, path):
    """Claude Code rule glob: `*` stays inside one segment, `**` crosses `/`."""
    rx = "".join(".*" if p == "**" else "[^/]*" if p == "*" else re.escape(p)
                 for p in re.split(r"(\*\*|\*)", pattern))
    return re.fullmatch(rx, path) is not None


def inner(rule):
    return re.fullmatch(r"\w+\((.*)\)", rule).group(1)


def spec_ifs(settings):
    out = []
    for groups in settings["hooks"].values():
        for g in groups:
            for h in g["hooks"]:
                if "specs" in h.get("if", ""):
                    out.append(h["if"])
    return out


LEGACY = "docs/product/specs/0006-x.md"
FOLDER = "docs/product/specs/0006-x/tasks.md"
DEEPER = "docs/product/specs/0006-x/sub/tasks.md"


class SpecFolderPermissionsAndFilters(unittest.TestCase):
    def test_s15_mode_a_permissions_cover_legacy_and_folder(self):  # FR-19, AC-15
        rules = [inner(r) for r in load("settings.example.json")["permissions"]["allow"]]
        self.assertIn("docs/product/specs/*", rules)
        self.assertIn("docs/product/specs/*/*", rules)
        self.assertTrue(any(glob_match(r, LEGACY) for r in rules))
        self.assertTrue(any(glob_match(r, FOLDER) for r in rules))
        # `*` and `*/*` are exactly one level: a deeper path is not permitted (ADR 0024 s1)
        self.assertFalse(any(glob_match(r, DEEPER) for r in rules))

    def test_s15_mode_a_if_filters_match_folder_files(self):  # FR-19, AC-15
        filters = spec_ifs(load("settings.example.json"))
        self.assertTrue(filters)
        for f in filters:
            pat = inner(f)
            self.assertTrue(glob_match(pat, LEGACY), f)
            self.assertTrue(glob_match(pat, FOLDER), f)
            # `**` lets deeper writes through; the resolver enforces depth (ADR 0024 s1)
            self.assertTrue(glob_match(pat, DEEPER), f)

    def test_s15_multi_project_permissions_cover_folder(self):  # FR-19, AC-15
        rules = [inner(r).replace("{{PROJECTS_ROOT_PERMISSION_PATH}}", "//home/u/projects")
                 for r in load("settings.multi-project.json.example")["permissions"]["allow"]]
        legacy = "//home/u/projects/app/product/specs/0006-x.md"
        folder = "//home/u/projects/app/product/specs/0006-x/spec.md"
        self.assertTrue(any(glob_match(r, legacy) for r in rules))
        self.assertTrue(any(glob_match(r, folder) for r in rules))
        self.assertFalse(any(glob_match(r, folder + "/x") for r in rules))

    def test_installer_takes_permission_from_template(self):  # FR-19
        with open(os.path.join(SCRIPTS, "install_user_level.py"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("{{PROJECTS_ROOT_PERMISSION_PATH}}", text)
        self.assertNotIn("product/specs/*", text)


PT_SOURCE = (
    "# Especificacao\n\n"
    "Os arquivos spec.md, plan.md, tasks.md e reconciliation.md ficam na pasta.\n\n"
    "## Tasks\n\n- [ ] T1\n\n## Reconciliation\n"
)


class TranslationKeepsFileNames(unittest.TestCase):
    def rules(self, tr):
        return [r["rule"] for r in translation.check(PT_SOURCE, tr)]

    def test_s14_names_and_headings_stay_english(self):  # FR-09, NFR-04, AC-14
        self.assertEqual(translation.check(PT_SOURCE, PT_SOURCE), [])
        for name in ("spec.md", "plan.md", "tasks.md", "reconciliation.md"):
            self.assertIn(name, translation.LITERALS)
        self.assertEqual(translation.RUNTIME_TOKEN_LIST, (
            "<backend dir>", "<build_test_cmd>", "<frontend dir>", "<language>",
            "<main_integration_branch>", "<project name>"))

    def test_s14_check_rejects_translated_file_name(self):  # FR-09, NFR-04, AC-14
        for name, pt in (("spec.md", "especificacao.md"), ("plan.md", "plano.md"),
                         ("tasks.md", "tarefas.md"), ("reconciliation.md", "conciliacao.md")):
            tr = PT_SOURCE.replace(name, pt)
            self.assertIn("English literals", self.rules(tr), name)

    def test_s14_check_rejects_dropped_file_name_count(self):  # FR-09, NFR-04
        tr = PT_SOURCE + "\nVeja tambem tasks.md.\n"
        self.assertIn("English literals", self.rules(tr))

    def test_s14_translated_prose_with_verbatim_names_passes(self):  # FR-09, AC-14
        tr = PT_SOURCE.replace("Os arquivos", "Os ficheiros").replace("ficam na pasta", "ficam na pasta da spec")
        self.assertEqual(translation.check(PT_SOURCE, tr), [])


if __name__ == "__main__":
    unittest.main()
