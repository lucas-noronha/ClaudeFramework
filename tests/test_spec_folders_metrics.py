"""Metrics and session brief read spec folders (spec 0006 FR-13, S09)."""
import json
import os
import unittest

from helpers import HOOKS, TempCase

RECON = (
    "## Reconciliation\n\n"
    "- [task 1] src/a.py: matches spec\n"
    "- [task 2] src/b.py: diverged from FR-02\n"
    "- [task 3] out of scope\n"
)


class SpecFoldersMetricsTests(TempCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("proj")
        self.specs = os.path.join(self.repo, "docs", "product", "specs")
        os.makedirs(os.path.join(self.repo, ".claude"))
        self.log = os.path.join(self.repo, ".claude", "pipeline-metrics.jsonl")

    def events(self):
        if not os.path.exists(self.log):
            return []
        return [json.loads(line) for line in self.read(self.log).splitlines() if line.strip()]

    def edit(self, path):
        result = self.hook(HOOKS, "pipeline_metrics.py",
                           {"tool_name": "Edit", "tool_input": {"file_path": path}}, self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)

    def snapshots(self):
        return [e for e in self.events() if e.get("event") == "reconciliation_snapshot"]

    def verdict_for(self, prompt):
        transcript = os.path.join(self.tmp, "reviewer.jsonl")
        records = [{"type": "user", "message": {"content": prompt}},
                   {"type": "assistant", "message": {"id": "m1", "content": [{"type": "text", "text": "Approved - fine"}]}}]
        self.write(transcript, "\n".join(json.dumps(r) for r in records) + "\n")
        payload = {"hook_event_name": "SubagentStop", "agent_type": "reviewer", "agent_id": "r1",
                   "agent_transcript_path": transcript}
        self.hook(HOOKS, "pipeline_metrics.py", payload, self.repo)
        return [e for e in self.events() if e.get("event") == "reviewer_verdict"][-1]

    def test_s09_snapshot_from_folder_reconciliation_file(self):  # FR-13
        self.write(os.path.join(self.specs, "0010-feat", "spec.md"), "---\nid: 0010\nstatus: approved\n---\n# S\n")
        recon = os.path.join(self.specs, "0010-feat", "reconciliation.md")
        self.write(recon, "# Reconciliation\n\n" + RECON.split("\n\n", 1)[1])
        self.edit(recon)
        snaps = self.snapshots()
        self.assertEqual(len(snaps), 1, self.events())
        self.assertEqual((snaps[0]["spec_id"], snaps[0]["matches"], snaps[0]["diverged"], snaps[0]["out_of_scope"]),
                         ("0010", 1, 1, 1))

    def test_s09_snapshot_from_single_file_section_legacy_and_lite(self):  # FR-13
        legacy = os.path.join(self.specs, "0011-old.md")
        self.write(legacy, "---\nid: 0011\nstatus: approved\n---\n# S\n\n" + RECON)
        lite = os.path.join(self.specs, "0012-quick-x", "spec.md")
        self.write(lite, "---\nid: 0012\nlite: true\nstatus: approved\n---\n# S\n\n" + RECON)
        self.edit(legacy)
        self.edit(lite)
        self.assertEqual([(s["spec_id"], s["matches"]) for s in self.snapshots()], [("0011", 1), ("0012", 1)])

    def test_s09_folder_plan_or_spec_edit_yields_no_snapshot(self):  # FR-13
        spec = os.path.join(self.specs, "0010-feat", "spec.md")
        self.write(spec, "---\nid: 0010\nstatus: approved\n---\n\n" + RECON)
        plan = os.path.join(self.specs, "0010-feat", "plan.md")
        self.write(plan, "# Plan\n")
        self.edit(spec)
        self.edit(plan)
        self.assertEqual(self.snapshots(), [])

    def test_s09_verdict_spec_id_matches_both_path_shapes(self):  # FR-13
        self.assertEqual(self.verdict_for("review docs/product/specs/0013-old.md")["spec_id"], "0013")
        self.assertEqual(self.verdict_for("review docs/product/specs/0014-feat/")["spec_id"], "0014")
        self.assertEqual(self.verdict_for("review docs/product/specs/0015-feat/spec.md")["spec_id"], "0015")

    def test_s09_session_brief_lists_folders_and_legacy_files(self):  # FR-13
        self.write(os.path.join(self.specs, "0010-feat", "spec.md"), "---\nid: 0010\nstatus: approved\n---\n")
        self.write(os.path.join(self.specs, "0011-done", "spec.md"), "---\nid: 0011\nstatus: implemented\n---\n")
        self.write(os.path.join(self.specs, "0012-old.md"), "---\nid: 0012\nstatus: draft\n---\n")
        result = self.hook(HOOKS, "session_brief.py", {}, self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        text = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("0010-feat: approved", text)
        self.assertIn("0012-old.md: draft", text)
        self.assertNotIn("0011-done", text)


if __name__ == "__main__":
    unittest.main()
