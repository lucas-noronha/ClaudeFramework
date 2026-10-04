"""Shared helpers for the framework's own tests. Everything runs in temp
folders with HOME/USERPROFILE redirected, so no test can read or write
the real `~/.claude`.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(REPO, ".claude", "hooks")
SCRIPTS = os.path.join(REPO, ".claude", "scripts")


def posix(path: str) -> str:
    return path.replace("\\", "/").rstrip("/")


class TempCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cfw-test-")
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def env(self, project_dir=None, **extra):
        env = dict(os.environ, HOME=self.home, USERPROFILE=self.home, PYTHONIOENCODING="utf-8")
        env.pop("CLAUDE_CONFIG_DIR", None)
        if project_dir is not None:
            env["CLAUDE_PROJECT_DIR"] = project_dir
        env.update(extra)
        return env

    def run_py(self, script, *args, project_dir=None, stdin=None, check=True):
        result = subprocess.run(
            [sys.executable, script, *args], input=stdin, capture_output=True, text=True,
            encoding="utf-8", env=self.env(project_dir), timeout=120,
        )
        if check and result.returncode != 0:
            self.fail(f"{os.path.basename(script)} {args} exited {result.returncode}\n{result.stdout}\n{result.stderr}")
        return result

    def hook(self, hooks_dir, name, payload, project_dir):
        return self.run_py(os.path.join(hooks_dir, name), stdin=json.dumps(payload), project_dir=project_dir, check=False)

    def write(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def read(self, path):
        with open(path, encoding="utf-8") as f:
            return f.read()

    def git(self, cwd, *args):
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True,
                              env=self.env()).stdout.strip()

    def make_repo(self, name, files=None, branch="main"):
        repo = os.path.join(self.tmp, name)
        os.makedirs(repo)
        self.git(repo, "init", "-q", "-b", branch)
        self.git(repo, "config", "user.email", "t@example.com")
        self.git(repo, "config", "user.name", "t")
        self.git(repo, "config", "core.autocrlf", "false")
        for rel, text in (files or {"README.md": "x\n"}).items():
            self.write(os.path.join(repo, rel), text)
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-q", "-m", "initial")
        return repo

    def snapshot(self, root):
        """`{relpath: bytes}` of a whole tree, for "nothing changed" checks."""
        state = {}
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d != ".git"]
            for name in filenames:
                full = os.path.join(dirpath, name)
                with open(full, "rb") as f:
                    state[posix(os.path.relpath(full, root))] = f.read()
        return state
