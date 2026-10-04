"""`translation.py` upgrade support and `sync-index` fixes (framework spec 0005 task 6,
FR-06, FR-10, AC-05; framework ADR 0023 sections 3, 4). Real `git` in temp repos,
Portuguese fixtures; no model is ever called.
"""
import json
import os
import subprocess
import sys

from helpers import SCRIPTS, TempCase

sys.path.insert(0, SCRIPTS)
import translation  # noqa: E402

SCRIPT = os.path.join(SCRIPTS, "translation.py")


def body(first, last):
    return first + "\n" + "".join(f"linha {i}\n" for i in range(1, 8)) + last + "\n"


class UpgradeModeA(TempCase):
    def run_json(self, *args, check=True):
        result = self.run_py(SCRIPT, *args, check=check)
        return json.loads(result.stdout)

    def test_l15_mode_a_upgrade_classifies_outputs_fr06_fr10(self):
        src = os.path.join(self.tmp, "new-checkout")
        out = os.path.join(self.tmp, "project")
        old = {"docs/untouched.md": "# Velho 1\n", "docs/edited.md": "# Velho 2\n", "docs/same.md": "# Igual\n",
               "docs/keep.md": "# Mantido\n", "docs/gone.md": "# Removido\n"}
        files = {}
        for rel, text in old.items():
            dest = os.path.join(out, rel)
            self.write(dest, "# PT " + text)
            files[rel] = {"source_sha256": translation.text_sha256(text), "status": "translated",
                          "policy": "keep" if rel == "docs/keep.md" else "replace",
                          "dest": dest.replace("\\", "/"), "output_sha256": translation.text_sha256("# PT " + text)}
        self.write(os.path.join(out, "docs/edited.md"), "# PT Velho 2\neditado pelo usuario\n")
        record = os.path.join(out, ".claude", "translation-record.json")
        translation.save_record(record, {"language_code": "pt-BR", "files": files})
        for rel, text in {"docs/untouched.md": "# Novo 1\n", "docs/edited.md": "# Novo 2\n", "docs/same.md": "# Igual\n",
                          "docs/keep.md": "# Mudou\n", "docs/added.md": "# Adicionado\n"}.items():
            self.write(os.path.join(src, rel), text)
        before = self.snapshot(out)
        report = self.run_json("upgrade-plan", "--mode", "a", "--source", src, "--record", record, "--language-code", "pt-BR")
        self.assertEqual(report["retranslate"], ["docs/untouched.md"])
        self.assertEqual(report["edited"], ["docs/edited.md"])
        self.assertEqual(report["keep"], ["docs/keep.md"])
        self.assertEqual(report["new"], ["docs/added.md"])
        self.assertEqual(report["unchanged"], ["docs/same.md"])
        self.assertEqual(report["deleted_upstream"], ["docs/gone.md"])
        self.assertEqual(self.snapshot(out), before)  # report only: nothing written or deleted
        self.assertTrue(os.path.isfile(os.path.join(out, "docs/gone.md")))

    def test_l15_mode_a_english_is_noop_fr06(self):
        report = translation.upgrade_plan_a(self.tmp, os.path.join(self.tmp, "r.json"), "en-GB")
        self.assertTrue(report["noop"])


class UpgradeModeB(TempCase):
    def merge(self, repo, branch):
        return subprocess.run(["git", "merge", "--no-commit", "--no-ff", branch], cwd=repo, capture_output=True,
                              text=True, env=self.env())

    def test_l14_mode_b_upgrade_retranslates_changed_paths_conflicted_or_not_fr06_ac05(self):
        a1, b1, c1 = body("# A", "fim a"), body("# B", "fim b"), body("# C", "fim c")
        repo = self.make_repo("adopter", {"docs/a.md": a1, "docs/b.md": b1, "docs/c.md": c1})
        record = os.path.join(repo, ".claude", "translation-record.json")
        translation.save_record(record, {"language_code": "pt-BR", "files": {
            rel: {"source_sha256": translation.text_sha256(t), "status": "translated", "policy": "replace"}
            for rel, t in (("docs/a.md", a1), ("docs/b.md", b1), ("docs/c.md", c1))}})
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-q", "-m", "record")
        self.git(repo, "branch", "upstream")
        # adopter: translated a (conflicts later), b (top only: merges cleanly), c (never touched upstream)
        self.write(os.path.join(repo, "docs/a.md"), body("# A (pt)", "fim a pt"))
        self.write(os.path.join(repo, "docs/b.md"), body("# B (pt)", "fim b"))
        self.write(os.path.join(repo, "docs/c.md"), body("# C (pt)", "fim c pt"))
        self.git(repo, "commit", "-qam", "translated")
        self.git(repo, "checkout", "-q", "upstream")
        a2, b2 = body("# A", "fim a novo"), body("# B", "fim b novo")
        self.write(os.path.join(repo, "docs/a.md"), a2)
        self.write(os.path.join(repo, "docs/b.md"), b2)
        self.write(os.path.join(repo, "docs/d.md"), "# D novo\n")
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-qm", "upstream release")
        self.git(repo, "checkout", "-q", "main")
        self.assertNotEqual(self.merge(repo, "upstream").returncode, 0)  # a.md conflicts

        plan = json.loads(self.run_py(SCRIPT, "upgrade-plan", "--mode", "b", "--repo", repo, "--record", record).stdout)
        self.assertEqual(plan["changed"], [{"path": "docs/a.md", "conflicted": True},
                                           {"path": "docs/b.md", "conflicted": False}])
        self.assertEqual(plan["unchanged"], ["docs/c.md"])
        self.assertEqual(plan["new"], ["docs/d.md"])

        taken = json.loads(self.run_py(SCRIPT, "take-upstream", "--repo", repo, "--path", "docs/a.md",
                                       "--path", "docs/b.md").stdout)
        self.assertEqual(taken["taken"], ["docs/a.md", "docs/b.md"])
        self.assertEqual(self.read(os.path.join(repo, "docs/a.md")), a2)  # no conflict markers
        self.assertEqual(self.read(os.path.join(repo, "docs/b.md")), b2)
        self.assertIn("pt", self.read(os.path.join(repo, "docs/c.md")))  # unchanged: local translation kept

        # a translates; b fails its check and keeps upstream English
        staged = os.path.join(self.tmp, "a-pt.md")
        self.write(staged, body("# A (pt)", "fim a novo pt"))
        common = ["--source", repo, "--record", record, "--language-code", "pt-BR"]
        self.run_py(SCRIPT, "apply", *common, "--language", "Portuguese", "--path", "docs/a.md", "--staged", staged,
                    "--dest", os.path.join(repo, "docs/a.md"))
        self.run_py(SCRIPT, "apply", *common, "--language", "Portuguese", "--path", "docs/b.md",
                    "--status", "english", "--reason", "check failed")
        files = translation.load_record(record)["files"]
        self.assertEqual(files["docs/a.md"]["source_sha256"], translation.text_sha256(a2))
        self.assertEqual(files["docs/a.md"]["status"], "translated")
        self.assertEqual(files["docs/b.md"]["status"], "english")
        self.assertEqual(files["docs/b.md"]["source_sha256"], translation.text_sha256(b2))
        self.assertEqual(self.read(os.path.join(repo, "docs/b.md")), b2)

    def test_l14_mode_b_requires_open_merge_fr06(self):
        repo = self.make_repo("adopter2", {"docs/a.md": "# A\n"})
        record = os.path.join(repo, "r.json")
        translation.save_record(record, {"files": {}})
        self.assertIn("error", translation.upgrade_plan_b(repo, record))
        self.assertIn("error", translation.take_upstream(repo, ["docs/a.md"]))


class SyncIndexFixes(TempCase):
    TPL = "| I need... | Read | Cost |\n|---|---|---|\n| Antigo. | `docs/a.md` | ~100 tok |\n| Ausente. | `docs/z.md` | ~100 tok |\n"

    def test_l12_sync_index_reports_missing_docs_fr11(self):
        md = os.path.join(self.tmp, "CLAUDE.md")
        self.write(md, self.TPL)
        self.write(os.path.join(self.tmp, "docs/a.md"), "---\nsummary: Novo.\n---\n# A\n")
        report = translation.sync_index(md, self.tmp)
        self.assertEqual(report["updated"], ["docs/a.md"])
        self.assertEqual(report["missing"], ["docs/z.md"])
        self.assertIn("Ausente.", self.read(md))

    def test_l12_sync_index_reads_routing_keys_from_project_config_fr11(self):
        project = os.path.join(self.tmp, "proj")
        os.makedirs(os.path.join(project, ".claude"))
        self.write(os.path.join(project, ".claude", "project-config.json"), json.dumps({"routing_keys": {"summary": "sinopse"}}))
        keys = translation.project_summary_keys(project)
        self.assertEqual(keys[0], "sinopse")
        self.assertIn("resumo", keys)
        md = os.path.join(project, "CLAUDE.md")
        self.write(md, self.TPL)
        self.write(os.path.join(project, "docs/a.md"), "---\nsinopse: Via config.\nresumo: Ignorado.\n---\n# A\n")
        self.run_py(SCRIPT, "sync-index", "--claude-md", md, "--root", project, "--project", project)
        self.assertIn("Via config.", self.read(md))
