"""Session brief in a linked worktree (spec 0004 FR-11, AC-08)."""
import json
import os
import unittest

from helpers import HOOKS, TempCase


class WorktreeBriefTests(TempCase):
    def brief(self, project):
        result = self.hook(HOOKS, "session_brief.py", {}, project)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]

    def test_t19_brief_in_worktree_names_repo_and_branch(self):  # AC-08, FR-11
        repo = self.make_repo("myrepo")
        wt = os.path.join(self.tmp, "wt-feature")
        self.git(repo, "worktree", "add", "-q", "-b", "spec/0004", wt)
        first = self.brief(wt).splitlines()[0]
        self.assertIn("myrepo", first)
        self.assertIn("spec/0004", first)

    def test_t19_detached_worktree_says_so(self):  # FR-11
        repo = self.make_repo("myrepo")
        wt = os.path.join(self.tmp, "wt-detached")
        self.git(repo, "worktree", "add", "-q", "--detach", wt)
        self.assertIn("detached", self.brief(wt).splitlines()[0])

    def test_t19_main_checkout_brief_unchanged(self):  # NFR-01
        repo = self.make_repo("myrepo")
        text = self.brief(repo)
        self.assertTrue(text.startswith("Git status:"), text)
        self.assertNotIn("Worktree", text)


if __name__ == "__main__":
    unittest.main()
