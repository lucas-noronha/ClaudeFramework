"""State scopes in `_project_paths.state_file_path` (framework spec 0004
task 2, framework ADR 0022 section 2): the handoff is per checkout, the
project-scoped state is shared, a main checkout resolves as ever.
"""
import json
import os
import shutil
import subprocess
import sys
import unittest

from helpers import HOOKS, TempCase, posix


class TestStateScopes(TempCase):
    def setUp(self):
        super().setUp()
        self.claude = os.path.join(self.tmp, "fw", ".claude")
        os.makedirs(os.path.join(self.claude, "hooks"))
        for name in ("_project_paths.py", "session_handoff.py"):
            shutil.copy(os.path.join(HOOKS, name), os.path.join(self.claude, "hooks"))
        self.repo = self.make_repo("my-app")
        self.subtree = os.path.join(self.tmp, "fw", "docs", "my-app")
        os.makedirs(self.subtree)

    def register(self):
        self.write(os.path.join(self.claude, "projects.local.json"),
                   json.dumps({posix(self.repo): posix(self.subtree)}))

    def path(self, project_dir, scope):
        code = (f"import sys; sys.path.insert(0, {os.path.join(self.claude, 'hooks')!r}); "
                f"import _project_paths as p; print(p.state_file_path({project_dir!r}, 'f.md', {scope!r}))")
        return posix(subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8",
                                    env=self.env(project_dir), timeout=60, check=True).stdout.strip())

    def worktree(self, name):
        wt = os.path.join(self.tmp, "wt", name)
        self.git(self.repo, "worktree", "add", "-q", wt, "-b", "task/" + name)
        return wt

    def test_t09_three_checkouts_keep_three_handoff_files_in_modes_b_c(self):
        # AC-04, FR-05
        self.register()
        a, b = self.worktree("a"), self.worktree("b")
        sub = posix(self.subtree)
        self.assertEqual(self.path(self.repo, "checkout"), sub + "/f.md")
        self.assertEqual(self.path(a, "checkout"), sub + "/.worktree-state/a/f.md")
        self.assertEqual(self.path(b, "checkout"), sub + "/.worktree-state/b/f.md")
        for wt in (self.repo, a, b):
            self.assertEqual(self.path(wt, "project"), sub + "/f.md")
            self.assertEqual(self.path(wt, None), sub + "/f.md")

    def test_t09_mode_a_worktree_checkout_local_project_in_main(self):
        # AC-04, FR-05
        wt = self.worktree("a")
        self.assertEqual(self.path(self.repo, "checkout"), posix(self.repo) + "/.claude/f.md")
        self.assertEqual(self.path(self.repo, "project"), posix(self.repo) + "/.claude/f.md")
        self.assertEqual(self.path(wt, "checkout"), posix(wt) + "/.claude/f.md")
        self.assertEqual(self.path(wt, None), posix(wt) + "/.claude/f.md")
        self.assertEqual(self.path(wt, "project"), posix(self.repo) + "/.claude/f.md")

    def test_t09_handoff_hook_writes_per_worktree_and_creates_folders(self):
        # AC-04, FR-05
        self.register()
        a = self.worktree("a")
        result = self.hook(os.path.join(self.claude, "hooks"), "session_handoff.py",
                           {"last_assistant_message": "from a", "end_reason": "x"}, a)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("from a", self.read(os.path.join(self.subtree, ".worktree-state", "a", "session-handoff.md")))
        self.assertFalse(os.path.exists(os.path.join(self.subtree, "session-handoff.md")))


if __name__ == "__main__":
    unittest.main()
