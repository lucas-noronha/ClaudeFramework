"""Spec 0007 task 3 — the concurrency-aware, blocking gate (P02, P03, P10, P11)."""
import json
import os
import sys
import time

from helpers import HOOKS, TempCase

sys.path.insert(0, HOOKS)
import run_build_test  # noqa: E402


class GateBase(TempCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("app", {"src/a.py": "x = 1\n"})
        self.log = os.path.join(self.repo, ".claude", "pipeline-metrics.jsonl")
        self.runs = os.path.join(self.tmp, "runs")
        self.write(os.path.join(self.repo, ".claude", "agents", "scout.md"), "---\nname: scout\ntools: Read, Grep\n---\n")

    def set_cmd(self, code, exit_code=0):
        script = os.path.join(self.tmp, "build.py")
        self.write(script, f"import sys\nopen(r'{self.runs}', 'a').write('x')\n{code}\nsys.exit({exit_code})\n")
        self.write(os.path.join(self.repo, ".claude", "project-config.json"),
                   json.dumps({"build_test_cmd": f'python "{script}"'}))

    def events(self, *events):
        with open(self.log, "a", encoding="utf-8", newline="\n") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")

    def started(self, agent_id, agent_type="coder", ts=None, **extra):
        return {"ts": ts if ts is not None else time.time() - 10, "event": "subagent_started",
                "agent_id": agent_id, "agent_type": agent_type, **extra}

    def gate_events(self):
        with open(self.log, encoding="utf-8") as f:
            return [e for e in map(json.loads, f) if e["event"] == "gate_run"]

    def run_gate(self, **payload):
        return self.hook(HOOKS, "run_build_test.py", dict({"agent_type": "coder", "agent_id": "me"}, **payload), self.repo)


class TestConcurrentCount(GateBase):
    def count(self, agent_id="me"):
        return run_build_test.concurrent_agents(self.repo, agent_id)

    def test_p02_excludes_self_and_read_only_agents(self):  # FR-06, AC-04
        self.events(self.started("me"), self.started("b"), self.started("c", "scout"), self.started("d", "Explore"))
        self.assertEqual(self.count(), 1)

    def test_p02_counts_per_checkout(self):  # FR-06
        self.events(self.started("me"), self.started("b", checkout="wt-1"), self.started("c"))
        self.assertEqual(self.count(), 1)

    def test_p02_window_open_feature_and_sixty_minutes(self):  # FR-06
        now = time.time()
        self.events(self.started("old", ts=now - 7200), self.started("pre", ts=now - 1000),
                    self.started("me", ts=now - 5), self.started("b", ts=now - 30))
        self.assertEqual(self.count(), 2)  # no open feature: pre and b; the 2 h old one is outside
        self.events({"ts": now - 100, "event": "feature_started", "feature": "0007"})
        self.assertEqual(self.count(), 1)  # open feature: only b started inside it
        self.events({"ts": now - 1, "event": "feature_finished", "feature": "0007"})
        self.assertEqual(self.count(), 2)  # closed: back to the 60 minute window

    def test_p02_stopped_before_own_start_does_not_overlap(self):  # FR-06
        now = time.time()
        self.events(self.started("b", ts=now - 60), {"ts": now - 40, "event": "subagent_stopped", "agent_id": "b"},
                    self.started("me", ts=now - 20))
        self.assertEqual(self.count(), 0)

    def test_p02_blocked_sibling_is_still_in_flight(self):  # FR-06
        now = time.time()
        self.events(self.started("b", ts=now - 60), {"ts": now - 40, "event": "subagent_stopped", "agent_id": "b"},
                    {"ts": now - 39, "event": "gate_run", "agent_id": "b", "blocked": True},
                    self.started("c", ts=now - 60), {"ts": now - 40, "event": "subagent_stopped", "agent_id": "c"},
                    {"ts": now - 39, "event": "gate_run", "agent_id": "c", "blocked": False},
                    self.started("me", ts=now - 20))
        self.assertEqual(self.count(), 1)  # b was sent back to work; c really finished

    def test_p02_survives_a_line_cut_at_the_tail_boundary(self):  # FR-06, NFR-01
        old_cap = run_build_test.LOG_TAIL_BYTES
        try:
            filler = [{"ts": time.time() - 30, "event": "gate_run", "pad": "y" * 200} for _ in range(40)]
            self.events(self.started("b"), *filler, self.started("me"), self.started("c"))
            run_build_test.LOG_TAIL_BYTES = 3000  # cuts mid-line inside the filler
            self.assertEqual(self.count(), 1)  # b fell out of the tail, c counted, no crash
        finally:
            run_build_test.LOG_TAIL_BYTES = old_cap

    def test_p03_omitted_without_a_start_event(self):  # FR-06, NFR-01
        self.events(self.started("b"))
        self.assertIsNone(self.count())
        self.assertIsNone(self.count(agent_id=None))
        self.set_cmd("")
        self.assertEqual(self.run_gate(agent_id="ghost").returncode, 0)
        self.assertNotIn("concurrent", self.gate_events()[-1])


class TestBlockingGate(GateBase):
    def test_p10_failure_blocks_with_bounded_tail(self):  # FR-19, AC-15
        self.set_cmd("print('\\n'.join(f'line {i} ' + 'z' * 300 for i in range(400)))", exit_code=3)
        result = self.run_gate(stop_hook_active=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("FAILED", result.stderr)
        self.assertIn("line 399", result.stderr)
        self.assertNotIn("line 0 ", result.stderr)
        self.assertLessEqual(len(result.stderr.encode("utf-8")), 8 * 1024 + 1024)
        self.assertTrue(self.gate_events()[-1]["blocked"])
        self.assertEqual(self.gate_events()[-1]["agent_id"], "me")

    def test_p10_failure_with_stop_hook_active_exits_1(self):  # FR-19
        self.set_cmd("print('boom')", exit_code=3)
        result = self.run_gate(stop_hook_active=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAILED", result.stderr)
        self.assertIn("boom", result.stderr)
        self.assertFalse(self.gate_events()[-1]["blocked"])
        self.assertEqual(self.gate_events()[-1]["exit_code"], 3)

    def test_p10_active_failure_stderr_is_bounded(self):  # FR-19
        self.set_cmd("print('\\n'.join(f'line {i} ' + 'z' * 300 for i in range(400)))", exit_code=3)
        result = self.run_gate(stop_hook_active=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("line 399", result.stderr)
        self.assertNotIn("line 0 ", result.stderr)
        self.assertLessEqual(len(result.stderr.encode("utf-8")), 8 * 1024 + 1024)

    def test_p10_pass_exits_0_and_echoes_output(self):  # FR-19
        self.set_cmd("print('all good')")
        result = self.run_gate(stop_hook_active=False)
        self.assertEqual(result.returncode, 0)
        self.assertIn("all good", result.stdout)
        self.assertFalse(self.gate_events()[-1]["blocked"])

    def test_p10_missing_command_does_not_block(self):  # FR-19
        result = self.run_gate(stop_hook_active=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("build_test_cmd", result.stderr)

    def test_p11_concurrent_failure_runs_once_and_warns(self):  # FR-06, FR-07, AC-05
        self.set_cmd("print('red')", exit_code=1)
        self.events(self.started("me"), self.started("sib"))
        result = self.run_gate(stop_hook_active=False)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.read(self.runs), "x")
        self.assertIn("sibling", result.stderr)
        self.assertEqual(self.gate_events()[-1]["concurrent"], 1)

    def test_p11_solo_failure_has_no_sibling_warning(self):  # FR-06
        self.set_cmd("print('red')", exit_code=1)
        self.events(self.started("me"))
        result = self.run_gate(stop_hook_active=False)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("sibling", result.stderr)
        self.assertEqual(self.gate_events()[-1]["concurrent"], 0)
