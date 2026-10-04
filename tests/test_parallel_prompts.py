"""Spec 0007 task 6: agent prompt rules and the Reconciliation: literal."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".claude" / "scripts"))
import translation  # noqa: E402


def agent(name):
    return (ROOT / ".claude" / "agents" / f"{name}.md").read_text(encoding="utf-8")


class ParallelPrompts(unittest.TestCase):
    def test_p18_reconciliation_literal_registered(self):  # NFR-07
        self.assertIn("Reconciliation:", translation.LITERALS)
        rx = translation.LITERALS["Reconciliation:"]
        self.assertTrue(rx.search("under a `Reconciliation:` heading"))
        self.assertFalse(rx.search("## Reconciliation\n"))

    def test_read_only_git_rule_in_three_agents(self):
        for name in ("coder", "quickfix", "reviewer"):
            self.assertRegex(agent(name), r"(?i)git is read-only", name)

    def test_editing_rule_in_coder_and_quickfix(self):
        for name in ("coder", "quickfix"):
            self.assertRegex(agent(name), r"heredoc", name)

    def test_git_allowlist_matches_fr10(self):
        for name in ("coder", "quickfix", "reviewer"):
            flat = " ".join(agent(name).split())
            for sub in ("rev-parse", "check-ignore", "grep", "cat-file", "describe",
                        "worktree list", "stash list", "stash show"):
                self.assertIn(sub, flat, f"{name}: {sub}")

    def test_reviewer_per_task_returns_reconciliation(self):
        text = agent("reviewer")
        self.assertIn("`Reconciliation:` heading", text)
        self.assertNotIn("append exactly one line", text)
        # single-writer paths (sweep, final-only review) keep Edit (FR-15)
        tools = re.search(r"^tools:(.*)$", text, re.M).group(1)
        self.assertIn("Edit", tools)
        self.assertIn("Append one new `### Sweep", text)


if __name__ == "__main__":
    unittest.main()
