"""Spec 0007 task 1: subagent lifecycle events and the shared _subagents helper."""
import json
import os
import sys

from helpers import HOOKS, TempCase, posix

sys.path.insert(0, HOOKS)
import _subagents  # noqa: E402


class LifecycleEvents(TempCase):
    def setUp(self):
        super().setUp()
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(self.repo, ".claude"))

    def events(self):
        path = os.path.join(self.repo, ".claude", "pipeline-metrics.jsonl")
        if not os.path.exists(path):
            return []
        return [json.loads(l) for l in self.read(path).splitlines() if l.strip()]

    def test_p01_started_and_stopped_logged(self):  # FR-05, AC-04
        for name, event in (("SubagentStart", "subagent_started"), ("SubagentStop", "subagent_stopped")):
            r = self.hook(HOOKS, "pipeline_metrics.py",
                          {"hook_event_name": name, "agent_id": "a1", "agent_type": "coder"}, self.repo)
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout, "")
        evs = self.events()
        self.assertEqual([e["event"] for e in evs], ["subagent_started", "subagent_stopped"])
        for e in evs:
            self.assertEqual((e["agent_id"], e["agent_type"], e["role"]), ("a1", "coder", "coder"))

    def test_p01_checkout_stamped_in_linked_worktree(self):  # AC-04
        main = self.make_repo("app")
        os.makedirs(os.path.join(main, ".claude"))
        wt = os.path.join(self.tmp, "wt")
        self.git(main, "worktree", "add", "-q", wt, "-b", "feat")
        self.hook(HOOKS, "pipeline_metrics.py",
                  {"hook_event_name": "SubagentStart", "agent_id": "a2", "agent_type": "reviewer"}, wt)
        lines = [json.loads(l) for l in self.read(os.path.join(main, ".claude", "pipeline-metrics.jsonl")).splitlines()]
        self.assertEqual(lines[0]["event"], "subagent_started")
        self.assertTrue(lines[0].get("checkout"))

    def test_fields_only_when_present(self):
        self.hook(HOOKS, "pipeline_metrics.py", {"hook_event_name": "SubagentStop"}, self.repo)
        e = self.events()[0]
        self.assertEqual(e["event"], "subagent_stopped")
        for k in ("agent_id", "agent_type", "role"):
            self.assertNotIn(k, e)

    def test_dispatch_still_logged_by_posttooluse(self):
        self.hook(HOOKS, "pipeline_metrics.py",
                  {"tool_name": "Agent", "tool_input": {"subagent_type": "coder"}, "tool_response": "x"}, self.repo)
        self.assertEqual([e["event"] for e in self.events()], ["subagent_dispatched"])


class Readers(TempCase):
    def rec(self, typ, content, mid=None):
        m = {"content": content}
        if mid:
            m["id"] = mid
        return {"type": typ, "message": m}

    def test_read_jsonl_skips_bad_lines_and_missing(self):
        p = os.path.join(self.tmp, "t.jsonl")
        self.write(p, '{"a": 1}\nnot json\n[1]\n{"b": 2}\n')
        self.assertEqual(_subagents.read_jsonl(p), [{"a": 1}, {"b": 2}])
        self.assertEqual(_subagents.read_jsonl(os.path.join(self.tmp, "nope")), [])

    def test_read_jsonl_tail_drops_partial_line(self):
        p = os.path.join(self.tmp, "t.jsonl")
        self.write(p, "".join(json.dumps({"n": i}) + "\n" for i in range(50)))
        got = _subagents.read_jsonl(p, tail_bytes=60)
        self.assertTrue(got and got[-1] == {"n": 49})
        self.assertNotIn({"n": 0}, got)

    def test_last_assistant_text_joins_shared_message_id(self):
        recs = [
            self.rec("assistant", [{"type": "text", "text": "early"}], "m1"),
            self.rec("assistant", [{"type": "text", "text": "Approved"}], "m2"),
            self.rec("assistant", [{"type": "tool_use", "name": "X"}], "m2"),
            self.rec("assistant", [{"type": "text", "text": "details"}], "m2"),
            self.rec("assistant", [{"type": "tool_use", "name": "Y"}], "m3"),
        ]
        self.assertEqual(_subagents.last_assistant_text(recs), "Approved\ndetails")

    def test_last_assistant_text_string_content_and_empty(self):
        self.assertEqual(_subagents.last_assistant_text([self.rec("assistant", "hi")]), "hi")
        self.assertEqual(_subagents.last_assistant_text([]), "")

    def test_first_user_text(self):
        recs = [self.rec("user", [{"type": "tool_result"}]), self.rec("user", "review 0007-x/spec.md"),
                self.rec("user", "later")]
        self.assertEqual(_subagents.first_user_text(recs), "review 0007-x/spec.md")
        self.assertEqual(_subagents.first_user_text([]), "")

    def test_is_read_only(self):
        self.assertTrue(_subagents.is_read_only(self.tmp, "Explore"))
        self.write(os.path.join(self.tmp, ".claude", "agents", "ro.md"), "---\ntools: Read, Grep\n---\n")
        self.write(os.path.join(self.tmp, ".claude", "agents", "rw.md"), "---\ntools: Read, Edit\n---\n")
        self.assertTrue(_subagents.is_read_only(self.tmp, "ro"))
        self.assertFalse(_subagents.is_read_only(self.tmp, "rw"))
        self.assertFalse(_subagents.is_read_only(self.tmp, ""))
