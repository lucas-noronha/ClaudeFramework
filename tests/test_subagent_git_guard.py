"""Spec 0007 task 5: the subagent git guard (P13-P16)."""
import json
import os
import shutil
import subprocess
import sys
import unittest

from helpers import HOOKS, TempCase

GUARD = "subagent_git_guard.py"
SUB = {"agent_id": "a1", "agent_type": "coder"}


def payload(command, tool="Bash", **extra):
    return dict({"tool_name": tool, "tool_input": {"command": command}}, **extra)


class GuardCase(TempCase):
    def decision(self, command, tool="Bash", hooks=HOOKS, project_dir=None, subagent=True, raw=None):
        data = payload(command, tool, **(SUB if subagent else {}))
        proc = subprocess.run(
            [sys.executable, os.path.join(hooks, GUARD)],
            input=raw if raw is not None else json.dumps(data), capture_output=True, text=True,
            encoding="utf-8", env=self.env(project_dir or self.tmp), timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        if not proc.stdout.strip():
            return "allow"
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        return out["permissionDecision"]


class TestGuard(GuardCase):
    def test_p13_main_session_is_never_blocked(self):  # FR-12, AC-08
        for cmd in ("git commit -m x", "git reset --hard", "git checkout -- .", "git stash"):
            self.assertEqual(self.decision(cmd, subagent=False), "allow", cmd)

    def test_p13_either_field_marks_a_subagent(self):  # FR-12
        for extra in ({"agent_id": "x"}, {"agent_type": "coder"}):
            proc = self.run_py(os.path.join(HOOKS, GUARD), stdin=json.dumps(payload("git commit -m x", **extra)),
                               project_dir=self.tmp)
            self.assertIn("deny", proc.stdout)

    def test_p14_denies_mutating_git(self):  # FR-10, FR-12, AC-08
        denied = [
            ("git commit -m x", "Bash"),
            ("git add . && git commit -m x", "Bash"),
            ("git status; git reset --hard", "Bash"),
            ("git log | git apply", "Bash"),
            ("echo hi || git checkout main", "Bash"),
            ("git status\ngit stash", "Bash"),
            ("git -C /tmp/repo checkout x", "Bash"),
            ("git -c user.name=x commit -m y", "Bash"),
            ("git --git-dir=/tmp/x/.git reset --hard", "Bash"),
            ("git --git-dir /tmp/x/.git --work-tree /tmp/x checkout .", "Bash"),
            ("git --no-pager restore file", "Bash"),
            ("FOO=1 git push", "Bash"),
            ("env GIT_X=1 git merge a", "Bash"),
            ("/usr/bin/git rebase main", "Bash"),
            ("bash -c 'git add . && git commit -m x'", "Bash"),
            ('sh -c "git clean -fd"', "Bash"),
            ("git stash", "Bash"),
            ("git stash pop", "Bash"),
            ("git worktree add ../x", "Bash"),
            ("git branch newname", "Bash"),
            ("git branch -D old", "Bash"),
            ("git branch -m a b", "Bash"),
            ("git branch --delete old", "Bash"),
            ("git branch --set-upstream-to=origin/x", "Bash"),
            ("git tag v1", "Bash"),
            ("git tag -d v1", "Bash"),
            ("git tag -a v1 -m x", "Bash"),
            ("git tag -s v1", "Bash"),
            ("git config user.name x", "Bash"),
            ("git co main", "Bash"),
            ("git checkout main", "PowerShell"),
            ("git add .; git commit -m x", "PowerShell"),
            ("& git commit -m x", "PowerShell"),
            ("git.exe reset --hard", "PowerShell"),
            ("& git.exe checkout .", "PowerShell"),
            (r"& 'C:\Program Files\Git\cmd\git.exe' checkout .", "PowerShell"),
            (r"C:\Git\bin\git.exe reset --hard", "PowerShell"),
            ('powershell -Command "git commit -m x"', "PowerShell"),
            ("pwsh -c 'git stash'", "PowerShell"),
            ("cmd /c git reset --hard", "Bash"),
            ("git status | Out-Null; git push", "PowerShell"),
        ]
        for cmd, tool in denied:
            with self.subTest(cmd=cmd, tool=tool):
                self.assertEqual(self.decision(cmd, tool), "deny")

    def test_p14_deny_reason_names_the_rule(self):  # FR-10
        proc = self.run_py(os.path.join(HOOKS, GUARD), stdin=json.dumps(payload("git commit -m x", **SUB)),
                           project_dir=self.tmp)
        reason = json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("FR-10", reason)
        self.assertIn("git commit", reason)

    def test_p15_allows_read_only_git_and_non_git(self):  # NFR-02, NFR-04, AC-09
        allowed = [
            "git", "git --version", "git status", "git status --short", "git diff -- a.py",
            "git log --oneline -5", "git show HEAD:a.py", "git rev-parse HEAD", "git ls-files",
            "git check-ignore -v x", "git blame a.py", "git grep foo", "git cat-file -p HEAD",
            "git describe --tags", "git -C /tmp/r status", "git -c core.x=y log",
            "git --no-pager log", "git --git-dir=/x/.git diff", "git worktree list",
            "git stash list", "git stash show -p", "git branch", "git branch -v", "git branch --list",
            "git branch -l 'feat/*'", "git branch --contains abc", "git branch --merged main",
            "git branch -r", "git branch -a", "git branch -vv", "git branch -avv", "git branch -vva", "git tag", "git tag -l", "git tag --list 'v*'", "git tag -n",
            "git status && git diff | head", "git log 2>&1 | head", "git status > out.txt 2>&1",
            "echo git commit", "ls -la", "python -m unittest", "npm run build", "github-cli commit",
            "cat .gitignore", "bash -c 'ls'", "git log --format='%h; %s'", 'git log --grep="a && b"',
            "bash -c 'git status && git diff'", "FOO=1 git status", "/usr/bin/git log",
        ]
        for cmd in allowed:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.decision(cmd), "allow")
        self.assertEqual(self.decision("git status", "PowerShell"), "allow")
        self.assertEqual(self.decision("& git.exe diff", "PowerShell"), "allow")

    def test_p15_allows_unparseable_input(self):  # NFR-02
        for raw in ("", "not json", "[]", "{", json.dumps({"agent_id": "a"}),
                    json.dumps({"agent_id": "a", "tool_input": "git commit"}),
                    json.dumps({"agent_id": "a", "tool_input": {"command": 5}}),
                    json.dumps({"agent_id": "a", "tool_input": {}})):
            with self.subTest(raw=raw):
                self.assertEqual(self.decision("", raw=raw), "allow")
        self.assertEqual(self.decision("git commit -m 'unbalanced"), "allow")
        self.assertEqual(self.decision('git commit -m "unbalanced'), "allow")

    def test_p15_fast_path_reads_no_project_file(self):  # NFR-04
        # A project dir that doesn't exist and a hooks copy without the helper:
        # the fast path must still allow, because nothing is imported or read.
        lone = os.path.join(self.tmp, "lone")
        os.makedirs(lone)
        shutil.copy(os.path.join(HOOKS, GUARD), lone)
        for cmd, subagent in (("ls", True), ("git status", True), ("git commit -m x", False)):
            self.assertEqual(self.decision(cmd, hooks=lone, subagent=subagent), "allow", cmd)

    def test_p16_unregistered_mode_c_repo_is_never_blocked(self):  # NFR-05
        home = os.path.join(self.tmp, "cfw")
        shutil.copytree(HOOKS, os.path.join(home, "hooks"), ignore=shutil.ignore_patterns("__pycache__"))
        self.write(os.path.join(home, "framework.json"), json.dumps(
            {"install_mode": "user-level", "registry": os.path.join(home, "projects.local.json")}))
        repo = os.path.join(self.tmp, "unregistered")
        os.makedirs(repo)
        self.assertEqual(self.decision("git commit -m x", hooks=os.path.join(home, "hooks"), project_dir=repo), "allow")

        # Once registered, the same call is denied.
        subtree = os.path.join(self.tmp, "docs", "proj")
        os.makedirs(subtree)
        self.write(os.path.join(home, "projects.local.json"), json.dumps({repo.replace("\\", "/"): subtree.replace("\\", "/")}))
        self.assertEqual(self.decision("git commit -m x", hooks=os.path.join(home, "hooks"), project_dir=repo), "deny")

    def test_modes_a_b_deny_without_registration(self):  # NFR-05 (gate open outside user-level installs)
        self.assertEqual(self.decision("git reset --hard", project_dir=self.tmp), "deny")


if __name__ == "__main__":
    unittest.main()
