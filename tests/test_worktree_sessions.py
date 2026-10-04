"""The linked-worktree resolver in `_project_paths.py` (framework spec 0004
task 1, framework ADR 0022 section 1): a session inside a worktree resolves
to the repo's main checkout through git's own link files, with no git
subprocess and no exception on an unexpected layout.
"""
import json
import os
import shutil
import subprocess
import sys
import unittest

from helpers import HOOKS, TempCase, posix


class WorktreeCase(TempCase):
    def setUp(self):
        super().setUp()
        # A copy of the hooks, so the registry and `framework.local.json`
        # beside them are this test's own.
        self.claude = os.path.join(self.tmp, "fw", ".claude")
        os.makedirs(os.path.join(self.claude, "hooks"))
        shutil.copy(os.path.join(HOOKS, "_project_paths.py"), os.path.join(self.claude, "hooks"))
        self.script = os.path.join(self.claude, "hooks", "_project_paths.py")
        self.repo = self.make_repo("my-app")
        self.subtree = os.path.join(self.tmp, "fw", "docs", "my-app")
        os.makedirs(self.subtree)

    def register(self, **entries):
        self.write(os.path.join(self.claude, "projects.local.json"), json.dumps(entries))

    def add_worktree(self, path, branch):
        self.git(self.repo, "worktree", "add", "-q", path, "-b", branch)
        return path

    def rewrite_dot_git(self, wt, text):
        # Windows marks a worktree's `.git` file hidden, which `open(..., "w")` refuses.
        path = os.path.join(wt, ".git")
        os.remove(path)
        self.write(path, text)

    def describe(self, project_dir):
        return json.loads(self.run_py(self.script, "describe", project_dir).stdout)

    def call(self, expr, project_dir):
        code = (f"import sys; sys.path.insert(0, {os.path.dirname(self.script)!r}); import _project_paths as p; "
                f"print({expr})")
        return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8",
                              env=self.env(project_dir), timeout=60, check=True).stdout.strip()


class TestWorktreeResolution(WorktreeCase):
    def test_t02_describe_in_a_worktree_reports_the_main_checkouts_subtree(self):
        # AC-01, FR-04
        self.register(**{posix(self.repo): posix(self.subtree)})
        wt = self.add_worktree(os.path.join(self.tmp, "wt", "leave-flow"), "task/leave-flow")
        described = self.describe(wt)
        self.assertTrue(described["registered"])
        self.assertEqual(described["subtree"], posix(self.subtree))
        self.assertEqual(described["worktree"]["admin"], "leave-flow")
        self.assertEqual(described["worktree"]["main"], posix(self.repo))
        self.assertEqual(described["worktree"]["branch"], "task/leave-flow")
        self.assertEqual(described["worktree"]["subpath"], "")

    def test_t03_worktree_is_reported_even_when_the_main_checkout_is_unregistered(self):
        # FR-04
        wt = self.add_worktree(os.path.join(self.tmp, "wt", "x"), "task/x")
        described = self.describe(wt)
        self.assertFalse(described["registered"])
        self.assertIsNone(described["subtree"])
        self.assertEqual(described["worktree"]["main"], posix(self.repo))
        self.assertEqual(described["worktree"]["branch"], "task/x")

    def test_t04_a_worktree_outside_any_worktrees_root_resolves_the_same_way(self):
        # AC-02, FR-01
        self.register(**{posix(self.repo): posix(self.subtree)})
        for where in (os.path.join(self.tmp, "sibling-wt"), os.path.join(self.tmp, "deep", "er", "wt")):
            wt = self.add_worktree(where, "task/" + os.path.basename(where))
            self.assertEqual(self.describe(wt)["subtree"], posix(self.subtree))

    def test_t05_a_monorepo_subfolder_session_routes_to_the_main_subfolders_entry(self):
        # AC-02, FR-02
        repo = self.make_repo("mono", {"packages/x/a.txt": "a\n", "packages/y/b.txt": "b\n"})
        sub_x = os.path.join(self.tmp, "fw", "docs", "mono-x")
        os.makedirs(sub_x)
        self.register(**{posix(os.path.join(repo, "packages", "x")): posix(sub_x)})
        wt = os.path.join(self.tmp, "mono-wt")
        self.git(repo, "worktree", "add", "-q", wt, "-b", "task/m")
        described = self.describe(os.path.join(wt, "packages", "x"))
        self.assertEqual(described["subtree"], posix(sub_x))
        self.assertEqual(described["worktree"]["subpath"], "packages/x")
        self.assertFalse(self.describe(os.path.join(wt, "packages", "y"))["registered"])
        self.assertFalse(self.describe(wt)["registered"])

    def test_t06_an_explicit_entry_for_the_worktree_overrides_the_fallback(self):
        # AC-02, FR-03
        other = os.path.join(self.tmp, "fw", "docs", "wt-own")
        os.makedirs(other)
        wt = self.add_worktree(os.path.join(self.tmp, "wt", "own"), "task/own")
        self.register(**{posix(self.repo): posix(self.subtree), posix(wt): posix(other)})
        self.assertEqual(self.describe(wt)["subtree"], posix(other))
        self.assertEqual(self.describe(self.repo)["subtree"], posix(self.subtree))

    def test_t07_unexpected_git_layouts_degrade_to_todays_behaviour(self):
        # AC-06, NFR-02
        self.register(**{posix(self.repo): posix(self.subtree)})

        corrupt = self.add_worktree(os.path.join(self.tmp, "wt", "corrupt"), "task/corrupt")
        self.rewrite_dot_git(corrupt, "\x00 not a gitdir line")

        no_common = self.add_worktree(os.path.join(self.tmp, "wt", "nocommon"), "task/nocommon")
        os.remove(os.path.join(self.repo, ".git", "worktrees", "nocommon", "commondir"))

        renamed = self.add_worktree(os.path.join(self.tmp, "wt", "renamed"), "task/renamed")
        not_git = os.path.join(self.tmp, "notgit")
        os.makedirs(not_git)
        self.write(os.path.join(self.repo, ".git", "worktrees", "renamed", "commondir"), not_git)

        for wt in (corrupt, no_common, renamed):
            described = self.describe(wt)
            self.assertFalse(described["registered"], wt)
            self.assertIsNone(described["worktree"], wt)
            self.assertEqual(self.call("p.resolve_project_root(%r)" % posix(wt), wt), posix(wt))

    def test_relative_gitdir_and_detached_head_are_understood(self):
        wt = self.add_worktree(os.path.join(self.tmp, "wt", "rel"), "task/rel")
        admin = os.path.join(self.repo, ".git", "worktrees", "rel")
        self.rewrite_dot_git(wt, "gitdir: " + posix(os.path.relpath(admin, wt)) + "\n")
        self.write(os.path.join(admin, "HEAD"), "0123456789abcdef0123456789abcdef01234567\n")
        described = self.describe(wt)
        self.assertEqual(described["worktree"]["main"], posix(self.repo))
        self.assertIsNone(described["worktree"]["branch"])


class TestMainCheckoutUnchanged(WorktreeCase):
    def test_t08_main_checkout_describe_and_state_paths_are_unchanged(self):
        # AC-05, NFR-01
        unrouted = self.describe(self.repo)
        self.assertIsNone(unrouted["worktree"])
        self.assertFalse(unrouted["registered"])
        self.assertEqual(
            self.call("p.state_file_path(%r, 'session-handoff.md')" % self.repo, self.repo),
            os.path.join(self.repo, ".claude", "session-handoff.md"),
        )

        self.register(**{posix(self.repo): posix(self.subtree)})
        routed = self.describe(self.repo)
        self.assertIsNone(routed["worktree"])
        self.assertEqual(routed["subtree"], posix(self.subtree))
        self.assertEqual(
            self.call("p.state_file_path(%r, 'session-handoff.md')" % self.repo, self.repo),
            os.path.join(posix(self.subtree), "session-handoff.md"),
        )

    def test_a_non_git_folder_has_no_worktree(self):
        plain = os.path.join(self.tmp, "plain")
        os.makedirs(plain)
        self.assertIsNone(self.describe(plain)["worktree"])


class TestWorktreeLocalConfig(TempCase):
    def test_t17_worktree_path_honours_the_main_checkouts_local_config(self):
        # AC-07, FR-09 — mode A: `.claude/` is committed, so the worktree has
        # its own copy of the hooks but never the gitignored config.
        repo = self.make_repo("my-app")
        hooks = os.path.join(repo, ".claude", "hooks")
        os.makedirs(hooks)
        shutil.copy(os.path.join(HOOKS, "_project_paths.py"), hooks)
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-q", "-m", "hooks")
        root = os.path.join(self.tmp, "elsewhere", "worktrees")
        self.write(os.path.join(repo, ".claude", "framework.local.json"), json.dumps({"worktrees_root": root}))
        wt = os.path.join(self.tmp, "wt-a")
        self.git(repo, "worktree", "add", "-q", wt, "-b", "task/a")
        self.assertFalse(os.path.exists(os.path.join(wt, ".claude", "framework.local.json")))

        script = os.path.join(wt, ".claude", "hooks", "_project_paths.py")
        out = self.run_py(script, "worktree-path", "second", wt).stdout.strip()
        self.assertEqual(out, posix(os.path.join(root, "my-app", "second")))
        described = json.loads(self.run_py(script, "describe", wt).stdout)
        self.assertEqual(described["worktrees_root"], posix(root))

        # A worktree's own file still wins.
        own = os.path.join(self.tmp, "own-root")
        self.write(os.path.join(wt, ".claude", "framework.local.json"), json.dumps({"worktrees_root": own}))
        out = self.run_py(script, "worktree-path", "second", wt).stdout.strip()
        self.assertEqual(out, posix(os.path.join(own, "my-app", "second")))


if __name__ == "__main__":
    unittest.main()
