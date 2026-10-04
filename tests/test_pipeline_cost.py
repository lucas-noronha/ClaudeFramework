"""Spec 0003 — proportional pipeline cost (gate filter, metrics), plus the
mode A behaviour of the hooks spec 0002 touched (routing frontmatter).
"""
import json
import os
import time
import unittest

from helpers import HOOKS, REPO, TempCase

METRICS = os.path.join(REPO, ".claude", "scripts", "metrics.py")


class GateCase(TempCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo("app", {"src/a.py": "x = 1\n"})
        self.marker = os.path.join(self.tmp, "gate-ran")
        command = f'python -c "open(r\'{self.marker}\', \'a\').write(\'x\')"'
        self.write(os.path.join(self.repo, ".claude", "project-config.json"), json.dumps({"build_test_cmd": command}))

    def gate(self, payload):
        if os.path.exists(self.marker):
            os.remove(self.marker)
        result = self.hook(HOOKS, "run_build_test.py", payload, self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        return os.path.exists(self.marker)

    def transcript(self, *edits):
        path = os.path.join(self.tmp, "agent.jsonl")
        lines = [json.dumps({"message": {"content": [{"type": "text", "text": "hi"}]}})]
        for tool, file_path in edits:
            lines.append(json.dumps({"message": {"content": [
                {"type": "tool_use", "name": tool, "input": {"file_path": file_path}}]}}))
        self.write(path, "\n".join(lines) + "\n")
        return path


class TestGateFilter(GateCase):
    def test_ac02_read_only_subagents_never_run_the_gate(self):
        for agent in ("Explore", "triage", "researcher", "Plan"):
            self.write(os.path.join(self.repo, ".claude", "agents", "triage.md"), "---\nname: triage\ntools: Read, Grep, Glob\n---\n")
            self.write(os.path.join(self.repo, ".claude", "agents", "researcher.md"), "---\nname: researcher\ntools: WebSearch, Read\n---\n")
            self.assertFalse(self.gate({"agent_type": agent}), agent)

    def test_code_writers_always_run_it(self):
        self.assertTrue(self.gate({"agent_type": "coder"}))
        self.assertTrue(self.gate({"agent_type": "quickfix"}))

    def test_transcript_decides_for_other_agents(self):
        code = os.path.join(self.repo, "src", "a.py")
        doc = os.path.join(self.repo, "docs", "decisions", "0001-x.md")
        self.assertTrue(self.gate({"agent_type": "general-purpose", "agent_transcript_path": self.transcript(("Edit", code))}))
        self.assertFalse(self.gate({"agent_type": "architect", "agent_transcript_path": self.transcript(("Write", doc))}))
        self.assertFalse(self.gate({"agent_type": "general-purpose", "agent_transcript_path": self.transcript()}))

    def test_unknown_agent_without_transcript_runs_it(self):
        self.assertTrue(self.gate({}))

    def test_gate_run_is_logged(self):
        self.gate({"agent_type": "coder"})
        log = os.path.join(self.repo, ".claude", "pipeline-metrics.jsonl")
        events = [json.loads(line) for line in open(log, encoding="utf-8")]
        self.assertEqual(events[-1]["event"], "gate_run")
        self.assertEqual(events[-1]["exit_code"], 0)


class TestRealHookInput(TempCase):
    """Hook input exactly as Claude Code sent it on 2026-10-03 (Windows):
    raw UTF-8 on stdin, non-ASCII project path, these SubagentStop keys.
    """

    def setUp(self):
        super().setUp()
        self.repo = os.path.join(self.tmp, "Área de Trabalho", "app")
        os.makedirs(self.repo)
        self.git(self.repo, "init", "-q")

    def test_non_ascii_paths_reach_directory_scoped_hooks(self):
        spec = os.path.join(self.repo, "docs", "product", "specs", "0001-pedido.md")
        self.write(spec, "---\ndoc_type: spec\nid: 0001\nstatus: draft\narea: vendas\n---\n# Pedido de reposição\n")
        self.hook(HOOKS, "spec_index.py", {"tool_name": "Write", "tool_input": {"file_path": spec}}, self.repo)
        self.assertIn("Pedido de reposição", self.read(os.path.join(self.repo, "docs", "product", "specs", "README.md")))

    def test_subagent_stop_payload_as_captured(self):
        marker = os.path.join(self.tmp, "ran")
        self.write(os.path.join(self.repo, ".claude", "project-config.json"),
                   json.dumps({"build_test_cmd": f'python -c "open(r\'{marker}\', \'a\').write(\'x\')"'}))
        transcript = os.path.join(self.tmp, "agent-a1.jsonl")
        self.write(transcript, json.dumps({"message": {"content": [{"type": "tool_use", "name": "Write",
                   "input": {"file_path": os.path.join(self.repo, "src", "ação.py")}}]}}) + "\n")
        payload = {
            "session_id": "s", "transcript_path": os.path.join(self.tmp, "main.jsonl"), "cwd": self.repo,
            "prompt_id": "p", "permission_mode": "auto", "agent_id": "a1", "agent_type": "general-purpose",
            "hook_event_name": "SubagentStop", "stop_hook_active": False,
            "agent_transcript_path": transcript, "background_tasks": [], "session_crons": [],
        }
        self.assertEqual(self.hook(HOOKS, "run_build_test.py", payload, self.repo).returncode, 0)
        self.assertTrue(os.path.exists(marker))
        os.remove(marker)
        self.hook(HOOKS, "run_build_test.py", dict(payload, agent_type="Explore", agent_transcript_path=os.path.join(self.tmp, "none.jsonl")), self.repo)
        self.assertFalse(os.path.exists(marker))


class TestSettingsTemplates(unittest.TestCase):
    """What Claude Code 2.1.252 actually honours (verified 2026-10-03 in
    fresh headless sessions): `if` only on a handler, never on the group;
    in `if` the tool name is literal; permission file rules only via
    `Edit(...)`.
    """

    def load(self, name):
        with open(os.path.join(REPO, ".claude", name), encoding="utf-8") as f:
            return json.load(f)

    def test_if_is_on_handlers_and_names_the_matched_tool(self):
        for name in ("settings.example.json", "settings.multi-project.json.example"):
            for event, groups in self.load(name)["hooks"].items():
                for group in groups:
                    self.assertNotIn("if", group, f"{name} {event}: a group-level `if` is ignored")
                    for handler in group["hooks"]:
                        if "if" in handler:
                            tool = handler["if"].split("(", 1)[0]
                            self.assertEqual(tool, group.get("matcher"), f"{name} {event}: {handler['if']}")

    def test_file_permission_rules_use_edit(self):
        for name in ("settings.example.json", "settings.multi-project.json.example"):
            permissions = self.load(name).get("permissions", {})
            for rule in permissions.get("allow", []) + permissions.get("deny", []):
                self.assertFalse(rule.startswith("Write("), f"{name}: {rule} — Write(path) rules never match")


class TestMetrics(TempCase):
    def test_ac05_lanes_side_by_side(self):
        repo = self.make_repo("app")
        log = os.path.join(repo, ".claude", "pipeline-metrics.jsonl")
        events = [
            {"ts": 1, "event": "feature_started", "feature": "0007", "lane": "full", "tier": "standard"},
            {"ts": 2, "event": "subagent_dispatched", "subagent_type": "triage"},
            {"ts": 3, "event": "subagent_dispatched", "subagent_type": "coder"},
            {"ts": 4, "event": "gate_run", "exit_code": 1},
            {"ts": 5, "event": "gate_run", "exit_code": 0},
            {"ts": 6, "event": "subagent_dispatched", "subagent_type": "reviewer"},
            {"ts": 7, "event": "reviewer_verdict", "verdict": "Returned"},
            {"ts": 8, "event": "reviewer_verdict", "verdict": "Approved"},
            {"ts": 9, "event": "feature_finished", "feature": "0007"},
            {"ts": 10, "event": "gate_run", "exit_code": 0},
        ]
        self.write(log, "\n".join(json.dumps(e) for e in events) + "\n")
        self.run_py(METRICS, "--project-dir", repo, "start", "--feature", "quick-1", "--lane", "fast", "--tier", "trivial")
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "event": "subagent_dispatched", "subagent_type": "quickfix"}) + "\n")
            f.write(json.dumps({"ts": time.time(), "event": "gate_run", "exit_code": 0}) + "\n")
        self.run_py(METRICS, "--project-dir", repo, "finish", "--feature", "quick-1")
        report = json.loads(self.run_py(METRICS, "--project-dir", repo, "report", "--json").stdout)
        full = next(f for f in report["features"] if f["feature"] == "0007")
        self.assertEqual((full["subagents"], full["gate_runs"], full["gate_failures"], full["returned"], full["rework"]), (3, 2, 1, 1, 2))
        self.assertEqual(report["lanes"]["fast"]["avg_subagents"], 1)
        self.assertEqual(report["lanes"]["full"]["avg_gate_runs"], 2)
        table = self.run_py(METRICS, "--project-dir", repo, "report").stdout
        self.assertIn("| fast | 1 |", table)


class TestRoutingFrontmatter(TempCase):
    def test_ac06_missing_summary_is_nudged_with_configurable_key(self):
        repo = self.make_repo("app")
        doc = os.path.join(repo, "docs", "architecture", "module-structure.md")
        self.write(doc, "---\r\ndoc_type: architecture\r\nstatus: active\r\ncontext_budget: ~100 tokens\r\n---\r\n# x\r\n")
        result = self.hook(HOOKS, "frontmatter_check.py", {"tool_input": {"file_path": doc}}, repo)
        self.assertIn("`summary`", result.stdout)
        self.write(os.path.join(repo, ".claude", "project-config.json"), json.dumps({"routing_keys": {"summary": "answers"}}))
        result = self.hook(HOOKS, "frontmatter_check.py", {"tool_input": {"file_path": doc}}, repo)
        self.assertIn("`answers`", result.stdout)
        self.write(doc, "---\ndoc_type: architecture\nstatus: active\ncontext_budget: ~100 tokens\nanswers: Where does code go?\n---\n")
        self.assertEqual(self.hook(HOOKS, "frontmatter_check.py", {"tool_input": {"file_path": doc}}, repo).stdout.strip(), "")

    def test_templates_carry_routing_keys(self):
        for rel in ("docs/architecture/module-structure.md.template", "docs/architecture/frontend.md.template",
                    "docs/architecture/overview.md.template", "docs/product/requirements-template.md"):
            text = self.read(os.path.join(REPO, rel))
            self.assertIn("\nsummary:", text, rel)
            self.assertIn("\nnotFor:", text, rel)
            self.assertNotIn("resumo:", text, rel)
            self.assertNotIn("naoResponde:", text, rel)

    def test_claude_md_row_must_copy_resumo(self):
        repo = self.make_repo("app")
        doc = os.path.join(repo, "docs", "architecture", "overview.md")
        self.write(doc, "---\ndoc_type: architecture\nstatus: active\ncontext_budget: ~400 tokens\nresumo: What is the system's shape?\n---\n")
        self.write(os.path.join(repo, "CLAUDE.md"), "| I need... | File | ~Cost |\n|---|---|---|\n| Architecture overview | `docs/architecture/overview.md` | ~400 tok |\n")
        result = self.hook(HOOKS, "claude_md_index_check.py", {"tool_input": {"file_path": doc}}, repo)
        self.assertIn("The doc wins", result.stdout)
        self.write(os.path.join(repo, "CLAUDE.md"), "| What is the system's shape? | `docs/architecture/overview.md` | ~400 tok |\n")
        self.assertEqual(self.hook(HOOKS, "claude_md_index_check.py", {"tool_input": {"file_path": doc}}, repo).stdout.strip(), "")


class TestModeAUnchanged(TempCase):
    def test_hooks_still_work_without_any_install(self):
        repo = self.make_repo("app")
        spec = os.path.join(repo, "docs", "product", "specs", "0001-x.md")
        self.write(spec, "---\ndoc_type: spec\nid: 0001\nstatus: draft\narea: core\n---\n# X\n")
        # The project's own ADR 0008 is unrelated to framework ADR 0008:
        # the index must name the framework one, never link the project's.
        self.write(os.path.join(repo, "docs", "decisions", "0008-our-own-thing.md"), "# ADR\n")
        self.write(os.path.join(repo, "docs", "product", "requirements-template.md"), "# T\n")
        self.hook(HOOKS, "spec_index.py", {"tool_input": {"file_path": "docs/product/specs/0001-x.md"}}, repo)
        index = self.read(os.path.join(repo, "docs", "product", "specs", "README.md"))
        self.assertIn("framework ADR 0008", index)
        self.assertNotIn("decisions/0008", index)
        self.assertIn("`../requirements-template.md`", index)
        describe = json.loads(self.run_py(os.path.join(HOOKS, "_project_paths.py"), "describe", repo).stdout)
        self.assertEqual(describe["mode"], "A")


if __name__ == "__main__":
    unittest.main()
