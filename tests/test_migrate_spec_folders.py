"""Spec 0006 task 9: migrate_spec_folders.py (FR-16, NFR-04, NFR-05, AC-10).
Everything runs in temp dirs; this repo's real specs are never touched."""
import codecs
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, ".claude", "scripts", "migrate_spec_folders.py")
sys.path.insert(0, os.path.dirname(SCRIPT))
import migrate_spec_folders as mig  # noqa: E402

LEGACY = """---
doc_type: spec
id: 0042
status: draft
area: demo
relates_to: []
summary: A demo spec.
context_budget: ~350 tokens
---

# Demo

## Feature name
Demo

## Functional requirements
- FR-01: see [other](0041-other.md)

## Reconciliation

task 1: Approved

## {plan}

**Tier:** standard. **ADR:** none

### Approach
```
## not a heading
### nor this
```

### Test plan
- S01: x

## Tasks

- [ ] 1. do it
"""


def make_project(tmp, files):
    specs = os.path.join(tmp, "docs", "product", "specs")
    os.makedirs(specs)
    for name, content in files.items():
        with open(os.path.join(specs, name), "wb") as f:
            f.write(content if isinstance(content, bytes) else content.encode("utf-8"))
    return specs


def run(specs, *extra, apply=False):
    cmd = [sys.executable, SCRIPT, "--specs-dir", specs] + list(extra) + (["--apply"] if apply else [])
    env = dict(os.environ, CLAUDE_PROJECT_DIR=os.path.dirname(os.path.dirname(os.path.dirname(specs))))
    p = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return p.returncode, json.loads(p.stdout) if p.stdout.strip() else {}


def read(path):
    with open(path, "rb") as f:
        return f.read()


class MigrateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_S11_dry_run_by_default_writes_nothing(self):
        # FR-16
        specs = make_project(self.tmp, {"0042-demo.md": LEGACY.format(plan="Technical plan")})
        code, rep = run(specs)
        self.assertEqual(code, 0)
        self.assertTrue(rep["dry_run"])
        self.assertEqual(rep["results"][0]["action"], "migrate")
        self.assertEqual(sorted(os.listdir(specs)), ["0042-demo.md"])

    def test_S11_apply_splits_on_english_headings_and_is_lossless(self):
        # FR-16, NFR-05, AC-10
        for eol in ("\n", "\r\n"):
            with self.subTest(eol=repr(eol)):
                with tempfile.TemporaryDirectory() as tmp:
                    text = LEGACY.format(plan="Technical plan").replace("\n", eol)
                    specs = make_project(tmp, {"0042-demo.md": text})
                    code, rep = run(specs, apply=True)
                    self.assertEqual(code, 0, rep)
                    folder = os.path.join(specs, "0042-demo")
                    self.assertFalse(os.path.exists(os.path.join(specs, "0042-demo.md")))
                    self.assertEqual(sorted(os.listdir(folder)),
                                     ["plan.md", "reconciliation.md", "spec.md", "tasks.md"])
                    spec = read(os.path.join(folder, "spec.md")).decode()
                    plan = read(os.path.join(folder, "plan.md")).decode()
                    self.assertIn("status: draft", spec)
                    self.assertIn("tier: standard", spec)
                    self.assertNotIn("Technical plan", spec)
                    self.assertIn("doc_type: spec-plan", plan)
                    self.assertIn(eol + "# Technical plan" + eol, plan)
                    self.assertIn("## Approach", plan)
                    self.assertIn("## not a heading", plan)  # inside a fence: untouched
                    self.assertIn("doc_type: spec-reconciliation", read(os.path.join(folder, "reconciliation.md")).decode())
                    self.assertIn("## Tasks", read(os.path.join(folder, "tasks.md")).decode())
                    # every original content line appears in exactly one file (exact bytes)
                    out = b""
                    for n in ("spec.md", "plan.md", "tasks.md", "reconciliation.md"):
                        out += read(os.path.join(folder, n))
                    out_lines = out.decode().split(eol)
                    for line in text.split(eol):
                        if line.startswith("#"):
                            continue  # plan headings change level
                        if line.strip() in ("", "---"):  # blanks and the added frontmatter fences
                            continue
                        self.assertEqual(out_lines.count(line), text.split(eol).count(line), line)
                    self.assertTrue(rep["index"])
                    self.assertIn("0042", read(os.path.join(specs, "README.md")).decode())

    def test_S11_companion_context_budget_computed_from_real_size(self):
        # NFR-03, AC-13: ~N tokens = ceil(chars/4) up to the next 50, never a fixed 300
        self.assertEqual(mig.companion_budget(1), 50)
        self.assertEqual(mig.companion_budget(200), 50)
        self.assertEqual(mig.companion_budget(201), 100)
        specs = make_project(self.tmp, {"0042-demo.md": LEGACY.format(plan="Technical plan") + "x" * 8000})
        code, rep = run(specs, apply=True)
        self.assertEqual(code, 0, rep)
        folder = os.path.join(specs, "0042-demo")
        for name in ("plan.md", "tasks.md", "reconciliation.md"):
            text = read(os.path.join(folder, name)).decode()
            budget = int(re.search(r"^context_budget: ~(\d+) tokens", text, re.M).group(1))
            self.assertGreaterEqual(budget, len(text) / 4, name)
            self.assertLessEqual(budget, len(text) / 4 + 50, name)
        tasks = read(os.path.join(folder, "tasks.md")).decode()
        self.assertNotIn("~300 tokens", tasks)

    def test_S11_plan_heading_option_for_translated_spec(self):
        # FR-16
        specs = make_project(self.tmp, {"0042-demo.md": LEGACY.format(plan="Plano tecnico")})
        code, rep = run(specs, "--plan-heading", "Plano tecnico", apply=True)
        self.assertEqual(code, 0, rep)
        folder = os.path.join(specs, "0042-demo")
        self.assertTrue(os.path.isfile(os.path.join(folder, "plan.md")))
        self.assertNotIn("Plano tecnico", read(os.path.join(folder, "spec.md")).decode())

    def test_S12_translated_plan_without_heading_stays_in_spec_and_is_reported(self):
        # FR-16, NFR-04
        specs = make_project(self.tmp, {"0042-demo.md": LEGACY.format(plan="Plano tecnico")})
        code, rep = run(specs, apply=True)
        self.assertEqual(code, 0, rep)
        folder = os.path.join(specs, "0042-demo")
        self.assertFalse(os.path.exists(os.path.join(folder, "plan.md")))
        self.assertIn("## Plano tecnico", read(os.path.join(folder, "spec.md")).decode())
        res = rep["results"][0]
        self.assertIn("Plano tecnico", res["unclassified_sections"])
        self.assertTrue(any("plan" in w for w in res["warnings"]))

    def test_S11_refuses_existing_target_and_both_layouts(self):
        # FR-16
        specs = make_project(self.tmp, {"0042-demo.md": LEGACY.format(plan="Technical plan"),
                                        "0043-x.md": LEGACY.format(plan="Technical plan")})
        os.makedirs(os.path.join(specs, "0042-demo"))
        os.makedirs(os.path.join(specs, "0043-y"))
        code, rep = run(specs, apply=True)
        self.assertEqual(code, 1)
        self.assertEqual([r["action"] for r in rep["results"]], ["refuse", "refuse"])
        self.assertTrue(os.path.isfile(os.path.join(specs, "0042-demo.md")))
        self.assertTrue(os.path.isfile(os.path.join(specs, "0043-x.md")))

    def test_S11_skips_migrated_and_is_idempotent(self):
        # FR-16
        specs = make_project(self.tmp, {"0042-demo.md": LEGACY.format(plan="Technical plan")})
        run(specs, apply=True)
        before = read(os.path.join(specs, "0042-demo", "spec.md"))
        code, rep = run(specs, apply=True)
        self.assertEqual(code, 0)
        self.assertEqual(rep["results"][0]["action"], "skip")
        self.assertEqual(read(os.path.join(specs, "0042-demo", "spec.md")), before)

    def test_S11_reports_breaking_links_without_rewriting(self):
        # FR-16, NFR-05
        specs = make_project(self.tmp, {
            "0042-demo.md": LEGACY.format(plan="Technical plan") + "\nSee [a](../x.md)\n",
            "0041-other.md": "---\nid: 0041\nstatus: draft\n---\nSee [d](0042-demo.md)\n",
        })
        _, rep = run(specs, "--spec", "42", apply=True)
        res = rep["results"][0]
        self.assertIn("docs/product/specs/0041-other.md:5".replace("docs/product/specs/", ""),
                      [r.replace("product/specs/", "") for r in res["references_to_old_path"]])
        self.assertIn("../x.md", res["relative_links_one_level_deeper"])
        self.assertIn("(0042-demo.md)", read(os.path.join(specs, "0041-other.md")).decode())
        self.assertTrue(os.path.isfile(os.path.join(specs, "0041-other.md")))  # --spec: only 0042 migrated

    def test_S11_legacy_lite_moves_whole_to_quick_folder(self):
        # FR-16
        lite = "---\nid: 0050\nstatus: approved\nlite: true\n---\n## Tasks\n- [ ] 1. x\n## Reconciliation\n"
        specs = make_project(self.tmp, {"0050-fix.md": lite, "0051-quick-b.md": lite.replace("0050", "0051")})
        code, rep = run(specs, apply=True)
        self.assertEqual(code, 0, rep)
        self.assertEqual(read(os.path.join(specs, "0050-quick-fix", "spec.md")), lite.encode())
        self.assertTrue(os.path.isdir(os.path.join(specs, "0051-quick-b")))
        first = rep["results"][0]
        self.assertEqual(first["branch_change"], "task/fix -> task/quick-fix")
        self.assertTrue(any("approved" in w for w in first["warnings"]))

    def _inproc(self, specs, *extra):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = mig.main(["--specs-dir", specs, "--apply"] + list(extra))
        return code, json.loads(buf.getvalue())

    def test_S11_locked_original_reports_applied_original_kept(self):
        # FR-16: remove() fails after the rename
        specs = make_project(self.tmp, {"0042-demo.md": LEGACY.format(plan="Technical plan")})
        with mock.patch.object(mig.os, "remove", side_effect=PermissionError("locked")):
            code, rep = self._inproc(specs)
        res = rep["results"][0]
        self.assertEqual(res["action"], "applied_original_kept")
        self.assertTrue(res["applied"])
        self.assertTrue(os.path.isdir(os.path.join(specs, "0042-demo")))
        self.assertTrue(any("by hand" in w for w in res["warnings"]))

    def test_S11_rename_permission_error_keeps_original_and_removes_staging(self):
        # FR-16, NFR-05
        specs = make_project(self.tmp, {"0042-demo.md": LEGACY.format(plan="Technical plan")})
        with mock.patch.object(mig.os, "rename", side_effect=PermissionError("denied")):
            code, rep = self._inproc(specs)
        self.assertEqual(code, 1)
        self.assertEqual(rep["results"][0]["action"], "refuse")
        self.assertEqual(sorted(os.listdir(specs)), ["0042-demo.md"])

    def test_S11_verify_rejects_tampered_output_and_original_is_kept(self):
        # NFR-05
        raw = LEGACY.format(plan="Technical plan").encode()
        plan = mig.build_outputs(raw, "0042", ["Technical plan"], "Tier")
        good = {n: mig.render(e, plan["has_bom"]) for n, e in plan["files"].items()}
        mig.verify(plan, good)
        bad = dict(good, **{"tasks.md": good["tasks.md"].replace(b"do it", b"do IT")})
        with self.assertRaises(mig.Refused):
            mig.verify(plan, bad)
        dropped = dict(good, **{"spec.md": good["spec.md"].replace(b"- FR-01", b"- FR-0")})
        with self.assertRaises(mig.Refused):
            mig.verify(plan, dropped)
        specs = make_project(self.tmp, {"0042-demo.md": raw})
        real = mig.build_outputs

        def corrupt(*a, **k):
            out = real(*a, **k)
            entries = out["files"]["tasks.md"]
            entries[-1] = ("orig", entries[-1][1], b"tampered\n")
            return out
        with mock.patch.object(mig, "build_outputs", corrupt):
            code, rep = self._inproc(specs)
        self.assertEqual(code, 1)
        self.assertEqual(sorted(os.listdir(specs)), ["0042-demo.md"])
        self.assertEqual(read(os.path.join(specs, "0042-demo.md")), raw)

    def test_S11_bom_source_keeps_bom_in_every_file(self):
        # NFR-05
        raw = codecs.BOM_UTF8 + LEGACY.format(plan="Technical plan").encode()
        specs = make_project(self.tmp, {"0042-demo.md": raw})
        code, rep = self._inproc(specs)
        self.assertEqual(code, 0, rep)
        for n in ("spec.md", "plan.md", "tasks.md", "reconciliation.md"):
            data = read(os.path.join(specs, "0042-demo", n))
            self.assertTrue(data.startswith(codecs.BOM_UTF8 + b"---"), n)

    def test_S11_tier_label_translated(self):
        # FR-16
        text = LEGACY.format(plan="Plano tecnico").replace("**Tier:** standard", "**Nivel:** Structural.")
        specs = make_project(self.tmp, {"0042-demo.md": text})
        code, rep = self._inproc(specs, "--plan-heading", "Plano tecnico", "--tier-label", "Nivel")
        self.assertEqual(code, 0, rep)
        self.assertIn("tier: structural", read(os.path.join(specs, "0042-demo", "spec.md")).decode())

    def test_S11_invalid_tier_not_written_and_existing_tier_key_kept(self):
        # FR-16
        text = LEGACY.format(plan="Technical plan").replace("**Tier:** standard", "**Tier:** weird")
        specs = make_project(self.tmp, {"0042-demo.md": text,
                                        "0043-b.md": LEGACY.format(plan="Technical plan").replace(
                                            "id: 0042", "id: 0043\ntier:")})
        code, rep = self._inproc(specs)
        self.assertEqual(code, 0, rep)
        first, second = rep["results"]
        self.assertTrue(first["tier_missing"])
        self.assertNotIn("tier:", read(os.path.join(specs, "0042-demo", "spec.md")).decode())
        spec2 = read(os.path.join(specs, "0043-b", "spec.md")).decode()
        self.assertEqual(spec2.count("tier:"), 1)
        self.assertTrue(second["tier_missing"])


if __name__ == "__main__":
    unittest.main()
