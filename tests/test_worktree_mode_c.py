"""Spec 0004 — worktree sessions, mode C end to end (FR-04, NFR-04, AC-01).
An installed copy ships link_worktree.py, and the installed hooks treat a
worktree of a registered repo as that repo.
"""
import json
import os
import unittest

from helpers import posix
from test_user_level_install import InstallCase


class TestWorktreeModeC(InstallCase):
    def setUp(self):
        super().setUp()
        self.install("--apply")
        self.hooks = os.path.join(self.ns, "hooks")
        self.repo = self.make_repo("orders", {"Orders.sln": "", "README.md": "x\n"})
        self.run_py(os.path.join(self.ns, "scripts", "register_project.py"), "--repo", self.repo,
                    "--canonical-lang", "English", "--stakeholder-lang", "Portuguese",
                    "--stakeholder-lang-code", "pt", "--today", "2026-10-03", "--apply")
        self.subtree = os.path.join(self.ns, "docs", "orders")
        self.worktree = os.path.join(self.tmp, "orders-wt")
        self.git(self.repo, "worktree", "add", "-q", "-b", "feature", self.worktree)

    def test_t18_installer_ships_link_worktree_and_resolver_opens_gate_in_worktree(self):  # NFR-04
        self.assertTrue(os.path.isfile(os.path.join(self.ns, "scripts", "link_worktree.py")))
        describe = json.loads(self.run_py(os.path.join(self.hooks, "_project_paths.py"), "describe", self.worktree).stdout)
        self.assertEqual(describe["mode"], "C")
        self.assertEqual(describe["subtree"], posix(self.subtree))

    def test_t01_mode_c_worktree_is_not_gated_and_build_test_gate_fires(self):  # AC-01, FR-04
        marker = os.path.join(self.tmp, "gate-cwd")
        command = f'python -c "import os; open(r\'{marker}\', \'w\').write(os.getcwd())"'
        self.write(os.path.join(self.subtree, "project-config.json"), json.dumps({"build_test_cmd": command}))
        # Registration gate open: a spec write in the subtree is indexed from the worktree.
        spec = os.path.join(self.subtree, "product", "specs", "0001-orders.md")
        self.write(spec, "---\ndoc_type: spec\nid: 0001\nstatus: draft\narea: orders\n---\n# Orders\n")
        self.hook(self.hooks, "spec_index.py", {"tool_input": {"file_path": spec}}, self.worktree)
        self.assertIn("0001", self.read(os.path.join(self.subtree, "product", "specs", "README.md")))
        # Build/test gate fires, in the worktree.
        result = self.hook(self.hooks, "run_build_test.py", {"agent_type": "cfw-coder"}, self.worktree)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(os.path.exists(marker), "gate did not run in the worktree")
        self.assertEqual(os.path.realpath(self.read(marker)), os.path.realpath(self.worktree))


if __name__ == "__main__":
    unittest.main()
