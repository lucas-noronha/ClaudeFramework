"""Metrics per checkout (framework spec 0004 task 3, framework ADR 0022
section 3): one shared log, a `checkout` stamp from linked worktrees,
features told apart per checkout, appends that don't interleave.
"""
import json
import os
import subprocess
import sys
import unittest

from helpers import HOOKS, SCRIPTS, TempCase

sys.path.insert(0, SCRIPTS)
import metrics  # noqa: E402

METRICS = os.path.join(SCRIPTS, "metrics.py")


class TestWorktreeMetrics(TempCase):
    def worktree(self, repo, name):
        wt = os.path.join(self.tmp, "wt", name)
        self.git(repo, "worktree", "add", "-q", wt, "-b", "task/" + name)
        return wt

    def lines(self, path):
        return [json.loads(line) for line in self.read(path).splitlines()]

    def test_t10_mode_a_worktree_events_land_in_main_log(self):
        # AC-04, FR-06
        repo = self.make_repo("app")
        os.makedirs(os.path.join(repo, ".claude"))
        wt = self.worktree(repo, "a")
        self.run_py(METRICS, "start", "--feature", "0001", "--lane", "full", project_dir=wt)
        self.run_py(METRICS, "start", "--feature", "0002", "--lane", "fast", project_dir=repo)
        log = os.path.join(repo, ".claude", "pipeline-metrics.jsonl")
        self.assertFalse(os.path.exists(os.path.join(wt, ".claude", "pipeline-metrics.jsonl")))
        events = self.lines(log)
        self.assertEqual(events[0]["checkout"], "a")
        self.assertNotIn("checkout", events[1])

    def test_t11_features_in_two_checkouts_are_attributed_apart(self):
        # AC-04, FR-06, NFR-01
        ev = [
            {"ts": 1, "event": "feature_started", "feature": "A", "lane": "full"},
            {"ts": 2, "event": "feature_started", "feature": "B", "lane": "full", "checkout": "wt"},
            {"ts": 3, "event": "subagent_dispatched", "checkout": "wt"},
            {"ts": 4, "event": "subagent_dispatched"},
            {"ts": 5, "event": "subagent_dispatched"},
            {"ts": 6, "event": "feature_finished", "feature": "B", "checkout": "wt"},
        ]
        rows, _ = metrics.summarize(ev)
        by = {r["feature"]: r for r in rows}
        self.assertEqual((by["A"]["subagents"], by["B"]["subagents"]), (2, 1))
        self.assertTrue(by["B"]["finished"])
        self.assertFalse(by["A"]["finished"])
        self.assertFalse(by["A"]["overlapped"] or by["B"]["overlapped"])

    def test_t12_parallel_appends_yield_valid_lines(self):
        # FR-06
        repo = self.make_repo("app")
        os.makedirs(os.path.join(repo, ".claude"))
        n = 12
        code = ("import sys; sys.path.insert(0, sys.argv[1]); from _pipeline_metrics import log_event; "
                "[log_event(sys.argv[2], 'gate_run', exit_code=0, pad='x' * 500) for _ in range(20)]")
        procs = [subprocess.Popen([sys.executable, "-c", code, HOOKS, repo], env=self.env(repo)) for _ in range(n)]
        for p in procs:
            self.assertEqual(p.wait(timeout=120), 0)
        events = self.lines(os.path.join(repo, ".claude", "pipeline-metrics.jsonl"))
        self.assertEqual(len(events), n * 20)


if __name__ == "__main__":
    unittest.main()
