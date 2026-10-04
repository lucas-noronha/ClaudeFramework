"""`link_worktree.py` (framework spec 0004 task 4, framework ADR 0022
section 4): mode B's three framework links follow the code into a git
worktree, idempotently, and never into the AI-repo itself.
"""
import json
import os
import shutil
import subprocess
import unittest

from helpers import HOOKS, SCRIPTS, TempCase, posix


def make_dir_link(target, dest):
    """What Domain 5 does for `.claude` / `docs`: symlink, else junction."""
    try:
        os.symlink(target, dest, target_is_directory=True)
    except OSError:
        subprocess.run(["cmd", "/c", "mklink", "/J", dest, target], check=True, capture_output=True)


def drop_dir_link(path):
    if os.path.islink(path):
        os.unlink(path)
    else:
        os.rmdir(path)  # a junction


class LinkCase(TempCase):
    def setUp(self):
        super().setUp()
        # A copy of the scripts and hooks, so the registry beside them is this test's own.
        self.fw = os.path.join(self.tmp, "fw", ".claude")
        os.makedirs(os.path.join(self.fw, "hooks"))
        os.makedirs(os.path.join(self.fw, "scripts"))
        shutil.copy(os.path.join(HOOKS, "_project_paths.py"), os.path.join(self.fw, "hooks"))
        shutil.copy(os.path.join(SCRIPTS, "link_worktree.py"), os.path.join(self.fw, "scripts"))
        self.script = os.path.join(self.fw, "scripts", "link_worktree.py")
        self.repo = self.make_repo("my-app")

    def make_ai_repo(self):
        self.ai = os.path.join(self.tmp, "ai")
        self.subtree = os.path.join(self.ai, "docs", "my-app")
        self.write(os.path.join(self.subtree, "CLAUDE.md"), "# my-app\n")
        self.write(os.path.join(self.ai, "docs", "constitution.md"), "# c\n")
        self.write(os.path.join(self.ai, ".claude", "projects.local.json"),
                   json.dumps({posix(self.repo): posix(self.subtree)}))

    def link_main_checkout(self):
        """Mode B's three links in the main checkout."""
        self.make_ai_repo()
        make_dir_link(os.path.join(self.ai, ".claude"), os.path.join(self.repo, ".claude"))
        make_dir_link(os.path.join(self.ai, "docs"), os.path.join(self.repo, "docs"))
        os.link(os.path.join(self.subtree, "CLAUDE.md"), os.path.join(self.repo, "CLAUDE.md"))

    def add_worktree(self, path, branch="task/x"):
        self.git(self.repo, "worktree", "add", "-q", path, "-b", branch)
        return path

    def link(self, wt, *args, check=True):
        return self.run_py(self.script, wt, *args, project_dir=self.repo, check=check)

    def assert_linked(self, wt):
        self.assertTrue(os.path.isfile(os.path.join(wt, ".claude", "projects.local.json")))
        self.assertTrue(os.path.isfile(os.path.join(wt, "docs", "constitution.md")))
        self.assertTrue(os.path.samefile(os.path.join(wt, "CLAUDE.md"), os.path.join(self.subtree, "CLAUDE.md")))

    def exclude_lines(self):
        path = os.path.join(self.repo, ".git", "info", "exclude")
        return [line for line in self.read(path).splitlines() if line.startswith("/")]


class TestLinkWorktree(LinkCase):
    def test_t13_mode_b_creates_working_links_with_anchored_idempotent_excludes(self):
        # AC-03, FR-07
        self.link_main_checkout()
        wt = self.add_worktree(os.path.join(self.tmp, "wt", "x"))
        report = json.loads(self.link(wt).stdout)["worktrees"][0]
        self.assertFalse(report["errors"])
        self.assert_linked(wt)
        self.assertEqual(self.git(wt, "status", "--porcelain"), "")
        self.assertEqual(sorted(self.exclude_lines()), ["/.claude", "/CLAUDE.md", "/docs"])

        before = self.read(os.path.join(self.repo, ".git", "info", "exclude"))
        again = json.loads(self.link(wt).stdout)["worktrees"][0]
        self.assertEqual({r["status"] for r in again["links"]}, {"already linked"})
        self.assertEqual(again["excludes"], [])
        self.assertEqual(self.read(os.path.join(self.repo, ".git", "info", "exclude")), before)

    def test_t14_repair_recreates_a_deleted_link(self):
        # AC-03, FR-07
        self.link_main_checkout()
        wt = self.add_worktree(os.path.join(self.tmp, "wt", "x"))
        self.link(wt)
        drop_dir_link(os.path.join(wt, "docs"))
        os.remove(os.path.join(wt, "CLAUDE.md"))
        self.assertFalse(os.path.exists(os.path.join(wt, "docs")))
        self.run_py(self.script, "--repair", project_dir=self.repo)
        self.assert_linked(wt)
        self.assertEqual(self.git(wt, "status", "--porcelain"), "")

    def test_t15_no_op_in_modes_a_and_c(self):
        # AC-03, FR-07
        wt = self.add_worktree(os.path.join(self.tmp, "wt", "a"), "task/a")
        before = sorted(os.listdir(wt))
        mode_a = json.loads(self.link(wt).stdout)["worktrees"][0]
        self.assertTrue(mode_a["noop"])
        self.assertEqual(sorted(os.listdir(wt)), before)

        # Mode C: the repo is registered, but its checkout holds no links.
        self.write(os.path.join(self.fw, "projects.local.json"),
                   json.dumps({posix(self.repo): posix(os.path.join(self.tmp, "fw", "docs", "my-app"))}))
        mode_c = json.loads(self.link(wt).stdout)["worktrees"][0]
        self.assertTrue(mode_c["noop"])
        self.assertEqual(sorted(os.listdir(wt)), before)
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".git", "info", "exclude")) and self.exclude_lines())

    def test_t16_refuses_a_worktree_inside_the_ai_repo(self):
        # FR-07, NFR-03
        self.link_main_checkout()
        wt = self.add_worktree(os.path.join(self.ai, ".claude", "worktrees", "x"))
        result = self.link(wt, check=False)
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)["worktrees"][0]
        self.assertTrue(report["refused"])
        self.assertFalse(os.path.lexists(os.path.join(wt, "docs")))
        self.assertFalse(os.path.lexists(os.path.join(wt, "CLAUDE.md")))
        self.assertEqual(self.exclude_lines(), [])


if __name__ == "__main__":
    unittest.main()
