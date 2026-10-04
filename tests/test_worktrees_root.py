"""The per-machine worktrees root `/setup-framework` offers (Domain 7, or
Domain 6 in mode C) and `/worktree` resolves through
`_project_paths.py worktree-path`.
"""
import json
import os
import shutil
import subprocess
import sys
import unittest

from helpers import HOOKS, REPO, TempCase, posix

INSTALLER = os.path.join(REPO, ".claude", "scripts", "install_user_level.py")


class TestWorktreePathModesAB(TempCase):
    def setUp(self):
        super().setUp()
        # A copy of the hooks, so `framework.local.json` beside them is this
        # test's own and never the checkout's.
        self.claude = os.path.join(self.tmp, "fw", ".claude")
        os.makedirs(os.path.join(self.claude, "hooks"))
        shutil.copy(os.path.join(HOOKS, "_project_paths.py"), os.path.join(self.claude, "hooks"))
        self.repo = self.make_repo("my-app")

    def path_for(self, short_name, project_dir=None):
        script = os.path.join(self.claude, "hooks", "_project_paths.py")
        return self.run_py(script, "worktree-path", short_name, project_dir or self.repo).stdout.strip()

    def set_root(self, root, **extra):
        self.write(os.path.join(self.claude, "framework.local.json"), json.dumps({"worktrees_root": root, **extra}))

    def test_unset_keeps_the_sibling_layout(self):
        self.assertEqual(self.path_for("leave-flow"), posix(os.path.join(self.tmp, "leave-flow")))

    def test_configured_root_groups_by_repo_name(self):
        root = os.path.join(self.tmp, "elsewhere", "worktrees")
        self.set_root(root, other_key="kept")
        self.assertEqual(self.path_for("leave-flow"), posix(os.path.join(root, "my-app", "leave-flow")))

    def test_from_inside_a_worktree_still_uses_the_main_repo_name(self):
        root = os.path.join(self.tmp, "wt")
        self.set_root(root)
        first = self.path_for("first")
        self.git(self.repo, "worktree", "add", "-q", first, "-b", "task/first")
        self.assertEqual(self.path_for("second", project_dir=first), posix(os.path.join(root, "my-app", "second")))

    def test_non_ascii_path_survives_a_pipe_without_utf8_env(self):
        repo = self.make_repo("Área-app")
        env = self.env()
        env.pop("PYTHONIOENCODING", None)
        result = subprocess.run([sys.executable, os.path.join(self.claude, "hooks", "_project_paths.py"),
                                 "worktree-path", "x", repo], capture_output=True, env=env, timeout=60)
        self.assertEqual(result.stdout.decode("utf-8").strip(), posix(os.path.join(self.tmp, "x")))
        self.set_root(os.path.join(self.tmp, "wt"))
        result = subprocess.run([sys.executable, os.path.join(self.claude, "hooks", "_project_paths.py"),
                                 "worktree-path", "x", repo], capture_output=True, env=env, timeout=60)
        self.assertEqual(result.stdout.decode("utf-8").strip(), posix(os.path.join(self.tmp, "wt", "Área-app", "x")))

    def test_describe_reports_it_and_bad_json_fails_open(self):
        script = os.path.join(self.claude, "hooks", "_project_paths.py")
        self.set_root(os.path.join(self.tmp, "wt"))
        described = json.loads(self.run_py(script, "describe", self.repo).stdout)
        self.assertEqual(described["worktrees_root"], posix(os.path.join(self.tmp, "wt")))
        self.write(os.path.join(self.claude, "framework.local.json"), "{not json")
        self.assertEqual(self.path_for("x"), posix(os.path.join(self.tmp, "x")))


class TestWorktreesRootModeC(TempCase):
    def setUp(self):
        super().setUp()
        self.config = os.path.join(self.home, ".claude")
        self.ns = os.path.join(self.config, "cfw")

    def install(self, *extra):
        return self.run_py(INSTALLER, "--config-dir", self.config, "--today", "2026-10-03", *extra, "--apply")

    def root(self):
        with open(os.path.join(self.ns, "framework.json"), encoding="utf-8") as f:
            return json.load(f).get("worktrees_root")

    def test_recorded_kept_on_upgrade_and_cleared(self):
        wanted = os.path.join(self.tmp, "wt")
        self.install("--worktrees-root", wanted)
        self.assertEqual(self.root(), posix(wanted))

        self.install()
        self.assertEqual(self.root(), posix(wanted), "an upgrade without the flag keeps the choice")

        repo = self.make_repo("svc")
        hook = os.path.join(self.ns, "hooks", "_project_paths.py")
        out = self.run_py(hook, "worktree-path", "spec-a", repo).stdout.strip()
        self.assertEqual(out, posix(os.path.join(wanted, "svc", "spec-a")))

        self.install("--worktrees-root", "")
        self.assertIsNone(self.root())


if __name__ == "__main__":
    unittest.main()
