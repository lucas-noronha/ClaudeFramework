"""Spec 0007 task 4 — `/metrics` for parallel waves (P07, P08, P09, P12)."""
import json
import os
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "hooks"))

from helpers import HOOKS, REPO, SCRIPTS, TempCase  # noqa: E402
from _pipeline_metrics import LOG_FILENAME  # noqa: E402
from _project_paths import state_file_path  # noqa: E402

METRICS = os.path.join(SCRIPTS, "metrics.py")


class MetricsCase(TempCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("app")
        self.ts = 1000.0

    def log(self, event, **fields):
        self.ts += 1
        record = {"ts": self.ts, "event": event, **fields}
        path = state_file_path(self.repo, LOG_FILENAME, "project")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def report(self):
        out = self.run_py(METRICS, "--project-dir", self.repo, "report", "--json", project_dir=self.repo).stdout
        return json.loads(out)

    def text(self):
        return self.run_py(METRICS, "--project-dir", self.repo, "report", project_dir=self.repo).stdout


class TestMissingVerdicts(MetricsCase):
    def test_p07_flag_when_reviewer_dispatches_outnumber_verdicts(self):  # FR-04, AC-03
        self.log("feature_started", feature="0009", lane="full", tier="standard")
        for _ in range(3):
            self.log("subagent_dispatched", subagent_type="reviewer", role="reviewer")
        self.log("subagent_dispatched", subagent_type="cfw-coder", role="coder")
        self.log("reviewer_verdict", verdict="Approved", agent_id="a1")
        self.log("reviewer_verdict", verdict="Returned", agent_id="a2")
        self.log("feature_finished", feature="0009")
        row = self.report()["features"][0]
        self.assertEqual(row["reviewer_dispatches"], 3)
        self.assertEqual(row["missing_verdicts"], 1)
        self.assertIn("⚠ missing verdicts: 1", self.text())

    def test_p07_no_flag_when_every_dispatch_has_a_verdict_and_duplicates_collapse(self):
        self.log("feature_started", feature="0009", lane="full")
        self.log("subagent_dispatched", subagent_type="reviewer", role="reviewer")
        self.log("reviewer_verdict", verdict="Returned", agent_id="a1")
        self.log("reviewer_verdict", verdict="Approved", agent_id="a1")  # repeated stop: last wins
        row = self.report()["features"][0]
        self.assertEqual((row["approved"], row["returned"], row["missing_verdicts"]), (1, 0, 0))
        self.assertNotIn("missing verdicts", self.text())

    def test_p07_role_falls_back_to_subagent_type(self):
        self.log("feature_started", feature="0009", lane="full")
        self.log("subagent_dispatched", subagent_type="reviewer")
        self.assertEqual(self.report()["features"][0]["missing_verdicts"], 1)


class TestSoloConcurrent(MetricsCase):
    def test_p08_splits_failures_and_rework_counts_solo_plus_returned(self):  # FR-09, AC-06
        self.log("feature_started", feature="0009", lane="full")
        self.log("gate_run", exit_code=1, concurrent=2)
        self.log("gate_run", exit_code=1, concurrent=0)
        self.log("gate_run", exit_code=1)  # field absent = solo
        self.log("gate_run", exit_code=0, concurrent=1)
        self.log("reviewer_verdict", verdict="Returned")
        row = self.report()["features"][0]
        self.assertEqual(row["gate_runs"], 4)
        self.assertEqual(row["gate_failures"], 3)
        self.assertEqual(row["gate_failures_solo"], 2)
        self.assertEqual(row["gate_failures_concurrent"], 1)
        self.assertEqual(row["rework"], 3)  # 2 solo + 1 Returned
        self.assertIn("| 2/1 |", self.text())


class TestRealLog(MetricsCase):
    def test_p09_real_log_same_numbers_plus_the_flag(self):  # NFR-01, AC-13
        real = state_file_path(REPO, LOG_FILENAME, "project")
        if not os.path.exists(real):
            self.skipTest("no real metrics log on this machine")
        old = subprocess.run(["git", "show", "HEAD:.claude/scripts/metrics.py"], cwd=REPO,
                             capture_output=True, text=True, encoding="utf-8")
        if old.returncode != 0:
            self.skipTest("no HEAD baseline")
        root = os.path.join(self.tmp, "baseline", ".claude")
        shutil.copytree(HOOKS, os.path.join(root, "hooks"))
        self.write(os.path.join(root, "scripts", "metrics.py"), old.stdout)
        run = lambda script: json.loads(subprocess.run(
            [sys.executable, script, "--project-dir", REPO, "report", "--json"], capture_output=True, text=True,
            encoding="utf-8", env=self.env(REPO), timeout=120, check=True).stdout)
        before, after = run(os.path.join(root, "scripts", "metrics.py")), run(METRICS)
        self.assertEqual(len(before["features"]), len(after["features"]))
        for b, a in zip(before["features"], after["features"]):
            for key in b:
                if key == "rework":
                    # A log written since spec 0007 can hold concurrent failures,
                    # which the old script counted as rework and FR-09 doesn't.
                    self.assertEqual(b[key] - a["gate_failures_concurrent"], a[key], key)
                    continue
                self.assertEqual(b[key], a[key], key)
            self.assertIn("missing_verdicts", a)
            self.assertEqual(a["gate_failures_solo"] + a["gate_failures_concurrent"], a["gate_failures"])


class TestWaveGates(MetricsCase):
    def cli(self, *args):
        return self.run_py(METRICS, "--project-dir", self.repo, *args, project_dir=self.repo)

    def test_p12_wave_start_and_gates(self):  # FR-08, AC-07
        self.log("gate_run", agent_id="old", exit_code=1)  # before the wave
        self.cli("wave-start", "--feature", "0009")
        events = [json.loads(l) for l in self.read(state_file_path(self.repo, LOG_FILENAME, "project")).splitlines()]
        self.assertEqual(events[-1]["event"], "wave_started")
        self.assertEqual(events[-1]["feature"], "0009")
        self.ts = events[-1]["ts"] + 1
        self.log("gate_run", agent_id="a1", exit_code=1, concurrent=1, blocked=True)
        self.log("gate_run", agent_id="a1", exit_code=0, concurrent=0)
        self.log("gate_run", agent_id="a2", exit_code=1, concurrent=2)
        self.log("gate_run", agent_id="a3", exit_code=1, checkout="wt-other")  # other checkout
        gates = json.loads(self.cli("gates").stdout)
        by_agent = {g["agent_id"]: g for g in gates}
        self.assertEqual(set(by_agent), {"a1", "a2"})
        self.assertEqual(by_agent["a1"]["exit_code"], 0)  # latest per agent
        self.assertEqual(by_agent["a2"]["concurrent"], 2)

    def test_gates_with_no_log_is_an_empty_list(self):
        self.assertEqual(json.loads(self.cli("gates").stdout), [])

    def test_pending_lists_stops_whose_gate_has_not_landed(self):
        def life(agent_id, agent_type, *events, **extra):
            for event in events:
                self.log(event, agent_id=agent_id, agent_type=agent_type, **extra)
        life("old", "coder", "subagent_started", "subagent_stopped")  # before the wave
        self.cli("wave-start", "--feature", "0009")
        self.ts = 10 ** 10
        life("waiting", "coder", "subagent_started", "subagent_stopped")
        life("gated", "coder", "subagent_started", "subagent_stopped")
        self.log("gate_run", agent_id="gated", exit_code=0)
        life("resumed", "coder", "subagent_started", "subagent_stopped")
        self.log("gate_run", agent_id="resumed", exit_code=1, blocked=True)
        life("resumed", "coder", "subagent_started")  # returned to, running again
        life("reader", "reviewer", "subagent_started", "subagent_stopped")  # not a gated role
        life("fixer", "quickfix", "subagent_started", "subagent_stopped")
        life("elsewhere", "coder", "subagent_started", "subagent_stopped", checkout="wt-other")
        pending = json.loads(self.cli("pending").stdout)
        self.assertEqual([p["agent_id"] for p in pending], ["waiting", "fixer"])
        self.assertEqual(pending[0]["agent_type"], "coder")
        self.assertIsInstance(pending[0]["waiting_s"], int)


if __name__ == "__main__":
    unittest.main()
