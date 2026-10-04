"""Context budget of a migrated spec folder (spec 0006 NFR-03, AC-13, S16).

Measures, on the framework's own migrated spec 0004, what a per-task coder
loads (spec.md plus one task's full text from tasks.md) against the whole
legacy single file reconstructed read-only from git. Heuristic: chars / 4.
"""
import os
import re
import subprocess
import unittest

from helpers import REPO

SPEC_DIR = os.path.join(REPO, "evolution", "product", "specs", "0004-worktree-sessions")
LEGACY_GIT_PATH = "evolution/product/specs/0004-worktree-sessions.md"
TARGET = 0.50


def _read(name):
    with open(os.path.join(SPEC_DIR, name), encoding="utf-8") as f:
        return f.read()


def _legacy():
    r = subprocess.run(
        ["git", "show", "HEAD:" + LEGACY_GIT_PATH],
        cwd=REPO, capture_output=True, check=False,
    )
    if r.returncode != 0:
        return None
    return r.stdout.decode("utf-8")


def _task_blocks(tasks_text):
    """A task's text: its `- [ ] N.` line plus indented continuation lines."""
    blocks, cur = [], None
    for line in tasks_text.splitlines():
        if re.match(r"^- \[[ xX]\] \d+\.", line):
            cur = [line]
            blocks.append(cur)
        elif cur is not None and (line.startswith(" ") or not line.strip()):
            cur.append(line)
        else:
            cur = None
    return ["\n".join(b).strip() for b in blocks]


class ContextBudgetTests(unittest.TestCase):
    def setUp(self):
        if not os.path.isdir(SPEC_DIR):
            self.skipTest("spec 0004 is not a folder in this checkout")
        self.legacy = _legacy()
        if self.legacy is None:
            self.skipTest("legacy spec 0004 not available from git HEAD")

    def test_s16_per_task_coder_context_vs_legacy_file(self):
        """S16 / NFR-03 / AC-13: spec.md + one task <= 50% of the legacy file."""
        spec = _read("spec.md")
        blocks = _task_blocks(_read("tasks.md"))
        self.assertTrue(blocks, "tasks.md has no task lines")
        legacy_tokens = len(self.legacy) / 4
        spec_tokens = len(spec) / 4
        ratios = [(spec_tokens + len(b) / 4) / legacy_tokens for b in blocks]
        worst, mean = max(ratios), sum(ratios) / len(ratios)
        print(
            "\n[S16] legacy=%d tokens, spec.md=%d tokens, tasks=%d; "
            "ratio worst=%.1f%% mean=%.1f%% (target <= %d%%)"
            % (legacy_tokens, spec_tokens, len(blocks),
               worst * 100, mean * 100, TARGET * 100)
        )
        self.assertLessEqual(worst, TARGET)

    def test_s16_file_size_vs_declared_budget_is_reported(self):
        """AC-13 second clause: no file exceeds 2x its context_budget."""
        for name in ("spec.md", "plan.md", "tasks.md", "reconciliation.md"):
            text = _read(name)
            m = re.search(r"^context_budget:\s*~?(\d+)", text, re.M)
            self.assertIsNotNone(m, name + " lacks context_budget")
            tokens, budget = len(text) / 4, int(m.group(1))
            print("[S16] %s: %d tokens vs budget %d (%.1fx; limit 2x)"
                  % (name, tokens, budget, tokens / budget))
            self.assertLessEqual(tokens, 2 * budget, name)


if __name__ == "__main__":
    unittest.main()
