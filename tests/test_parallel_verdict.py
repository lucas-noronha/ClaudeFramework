"""Spec 0007 task 2: the reviewer verdict is read from the transcript on SubagentStop."""
import json
import os
import sys

from helpers import HOOKS, TempCase

sys.path.insert(0, HOOKS)
import _subagents  # noqa: E402


def text(t):
    return [{"type": "text", "text": t}]


class VerdictOnStop(TempCase):
    def setUp(self):
        super().setUp()
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(self.repo, ".claude"))

    def events(self, name=None):
        path = os.path.join(self.repo, ".claude", "pipeline-metrics.jsonl")
        if not os.path.exists(path):
            return []
        evs = [json.loads(l) for l in self.read(path).splitlines() if l.strip()]
        return [e for e in evs if name is None or e["event"] == name]

    def stop(self, records, agent_type="reviewer", transcript=True):
        path = os.path.join(self.tmp, "agent.jsonl")
        self.write(path, "\n".join(json.dumps(r) for r in records) + "\n")
        payload = {"hook_event_name": "SubagentStop", "agent_id": "a1", "agent_type": agent_type}
        if transcript:
            payload["agent_transcript_path"] = path
        r = self.hook(HOOKS, "pipeline_metrics.py", payload, self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)

    def user(self, prompt="review docs/product/specs/0007-x/spec.md"):
        return {"type": "user", "message": {"content": prompt}}

    def asst(self, mid, content):
        return {"type": "assistant", "message": {"id": mid, "content": content}}

    def test_p04_approved_and_returned_read_from_transcript(self):  # FR-01, AC-01
        for reply, verdict in (("Approved\n\nall good", "Approved"), ("Returned\n\n- finding", "Returned")):
            self.stop([self.user(), self.asst("m1", text(reply))])
            self.assertEqual(self.events("reviewer_verdict")[-1]["verdict"], verdict)
            self.assertEqual(self.events("reviewer_verdict")[-1]["agent_id"], "a1")

    def test_verdict_omits_agent_id_when_input_has_none(self):
        path = os.path.join(self.tmp, "agent.jsonl")
        self.write(path, "\n".join(json.dumps(r) for r in [self.user(), self.asst("m1", text("Approved"))]) + "\n")
        self.hook(HOOKS, "pipeline_metrics.py",
                  {"hook_event_name": "SubagentStop", "agent_type": "reviewer", "agent_transcript_path": path}, self.repo)
        self.assertNotIn("agent_id", self.events("reviewer_verdict")[-1])

    def test_p04_bold_markdown_stripped(self):  # FR-01
        self.stop([self.user(), self.asst("m1", text("**Approved**\n\nok"))])
        self.assertEqual(self.events("reviewer_verdict")[-1]["verdict"], "Approved")
        self.stop([self.user(), self.asst("m1", text("## **Returned**"))])
        self.assertEqual(self.events("reviewer_verdict")[-1]["verdict"], "Returned")

    def test_p04_split_records_joined_by_message_id(self):  # FR-01, AC-01
        self.stop([
            self.user(),
            self.asst("m1", text("working on it")),
            self.asst("m2", [{"type": "thinking", "thinking": "hm"}]),
            self.asst("m2", text("Returned")),
            self.asst("m2", [{"type": "tool_use", "name": "Read"}]),
            self.asst("m2", text("details")),
        ])
        evs = self.events("reviewer_verdict")
        self.assertEqual([e["verdict"] for e in evs], ["Returned"])

    def test_p04_verdict_read_from_subagent_handback_call(self):  # FR-01, AC-01
        # Shape captured in a real session (spec 0007 task 9): the reviewer ends
        # with a SubagentHandback tool call and no final text message.
        handback = {"type": "tool_use", "name": "SubagentHandback",
                    "input": {"message": "**Approved**\nProbe only."}}
        self.stop([self.user(), self.asst("m1", text("checking")), self.asst("m2", [handback])])
        self.assertEqual(self.events("reviewer_verdict")[-1]["verdict"], "Approved")
        other_tool = {"type": "tool_use", "name": "Read", "input": {"message": "Returned"}}
        self.stop([self.user(), self.asst("m1", text("Approved")), self.asst("m2", [other_tool])])
        self.assertEqual(self.events("reviewer_verdict")[-1]["verdict"], "Approved")

    def test_p04_non_reviewer_and_unrecognized_reply_log_nothing(self):  # FR-01
        self.stop([self.user(), self.asst("m1", text("Approved"))], agent_type="coder")
        self.stop([self.user(), self.asst("m1", text("I looked at it, seems fine"))])
        self.stop([self.user(), self.asst("m1", text("Approved"))], transcript=False)
        self.assertEqual(self.events("reviewer_verdict"), [])

    def test_p05_spec_id_from_both_path_shapes_and_slashes(self):  # FR-02, AC-02
        cases = {
            "review docs/product/specs/0013-old.md": "0013",
            "review docs/product/specs/0014-feat/": "0014",
            "review docs/product/specs/0015-feat/spec.md": "0015",
            "review docs\\product\\specs\\0016-feat\\spec.md": "0016",
            "review docs\\product\\specs\\0017-feat\\": "0017",
            "review docs/product/specs/0018-two-words.md": "0018",
        }
        for prompt, spec_id in cases.items():
            self.stop([self.user(prompt), self.asst("m1", text("Approved"))])
            self.assertEqual(self.events("reviewer_verdict")[-1]["spec_id"], spec_id, prompt)

    def test_p05_no_spec_reference_gives_null_spec_id(self):  # FR-02
        self.stop([self.user("review the thing"), self.asst("m1", text("Approved"))])
        self.assertIsNone(self.events("reviewer_verdict")[-1]["spec_id"])

    def test_p06_posttooluse_logs_no_verdict(self):  # FR-03, AC-01
        for response in ("Approved - fine", {"content": "**Returned**"}):
            r = self.hook(HOOKS, "pipeline_metrics.py",
                          {"tool_name": "Agent",
                           "tool_input": {"subagent_type": "reviewer", "prompt": "review 0007-x/spec.md"},
                           "tool_response": response}, self.repo)
            self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.events("reviewer_verdict"), [])
        self.assertEqual(len(self.events("subagent_dispatched")), 2)

    def test_p06_foreground_reviewer_counted_exactly_once(self):  # FR-03, AC-01
        self.hook(HOOKS, "pipeline_metrics.py",
                  {"tool_name": "Agent", "tool_input": {"subagent_type": "reviewer", "prompt": "review 0007-x/"},
                   "tool_response": "Approved"}, self.repo)
        self.stop([self.user("review 0007-x/"), self.asst("m1", text("Approved"))])
        self.assertEqual(len(self.events("reviewer_verdict")), 1)


class SplitLines(TempCase):
    def test_unicode_line_separators_do_not_split_a_record(self):
        p = os.path.join(self.tmp, "t.jsonl")
        record = {"type": "assistant", "message": {"content": "a b\x0bc\x0cd\x85e f"}}
        with open(p, "wb") as f:
            f.write((json.dumps(record, ensure_ascii=False) + "\r\n" + json.dumps({"n": 1}) + "\n").encode("utf-8"))
        self.assertEqual(_subagents.read_jsonl(p), [record, {"n": 1}])
