"""Spec 0001 — mode C hardening. Acceptance criteria exercised against a
throwaway config directory and throwaway repos.
"""
import json
import os
import re
import shutil
import unittest

from helpers import REPO, TempCase, posix

INSTALLER = os.path.join(REPO, ".claude", "scripts", "install_user_level.py")


class InstallCase(TempCase):
    def setUp(self):
        super().setUp()
        self.config = os.path.join(self.home, ".claude")
        os.makedirs(os.path.join(self.config, "commands"))
        # A machine that already has personal commands and settings (D6).
        self.write(os.path.join(self.config, "commands", "spec.md"), "my own spec command\n")
        self.write(os.path.join(self.config, "commands", "plan.md"), "my own plan command\n")
        self.original_settings = '{\n  "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo hi"}]}]},\n  "model": "x"\n}\n'
        self.write(os.path.join(self.config, "settings.json"), self.original_settings)
        self.ns = os.path.join(self.config, "cfw")

    def install(self, *extra, installer=INSTALLER, check=True):
        return self.run_py(installer, "--config-dir", self.config, "--today", "2026-10-03", *extra, check=check)

    def uninstall(self, *extra):
        return self.run_py(os.path.join(self.ns, "scripts", "uninstall.py"), *extra)

    def framework(self):
        with open(os.path.join(self.ns, "framework.json"), encoding="utf-8") as f:
            return json.load(f)


class TestInstall(InstallCase):
    def test_ac01_install_with_colliding_personal_commands(self):
        self.install("--apply")
        self.assertEqual(self.read(os.path.join(self.config, "commands", "spec.md")), "my own spec command\n")
        for name in ("cfw-spec.md", "cfw-plan.md", "cfw-implement.md", "cfw-quick.md", "cfw-update-docs.md", "cfw-metrics.md"):
            self.assertTrue(os.path.isfile(os.path.join(self.config, "commands", name)), name)
        self.assertTrue(os.path.isfile(os.path.join(self.config, "agents", "cfw-coder.md")))
        self.assertTrue(os.path.isfile(os.path.join(self.config, "skills", "cfw-project-registration", "SKILL.md")))
        coder = self.read(os.path.join(self.config, "agents", "cfw-coder.md"))
        self.assertIn("name: cfw-coder", coder)
        implement = self.read(os.path.join(self.config, "commands", "cfw-implement.md"))
        self.assertIn("`cfw-reviewer`", implement)
        self.assertNotRegex(implement, r"(?<![\w./-])/(spec|plan|tasks|review|quick)(?![\w-])")

    def test_ac04_no_per_project_placeholder_survives(self):
        self.install("--apply")
        permanent = {"AZURE_DEVOPS_ORG", "AZURE_DEVOPS_PAT_ENV_VAR"}
        for root in (os.path.join(self.config, d) for d in ("agents", "commands", "skills")):
            for dirpath, _, files in os.walk(root):
                for name in files:
                    if name.startswith("cfw") or "cfw-" in dirpath:
                        text = self.read(os.path.join(dirpath, name))
                        self.assertEqual(re.findall(r"\{\{([A-Z_]+)\}\}", text), [], os.path.join(dirpath, name))
        docs = os.path.join(self.ns, "docs")
        for rel in ("constitution.md", "constitution-baseline.md", "glossary.md", "product/requirements-template.md"):
            self.assertEqual(re.findall(r"\{\{([A-Z_]+)\}\}", self.read(os.path.join(docs, rel))), [], rel)
        for name in os.listdir(os.path.join(docs, "workflow")):
            left = set(re.findall(r"\{\{([A-Z_]+)\}\}", self.read(os.path.join(docs, "workflow", name))))
            self.assertLessEqual(left, permanent, name)

    def test_hook_commands_are_absolute_and_unquoted_tilde_free(self):
        self.install("--apply")
        settings = json.loads(self.read(os.path.join(self.config, "settings.json")))
        commands = [h["command"] for groups in settings["hooks"].values() for g in groups for h in g["hooks"]]
        ours = [c for c in commands if "/cfw/hooks/" in c]
        self.assertTrue(ours)
        for command in ours:
            self.assertNotIn("~", command)
            self.assertIn(posix(self.ns), command)
        self.assertIn("echo hi", commands)
        rule = settings["permissions"]["allow"][0]
        self.assertTrue(rule.startswith("Edit(//"), rule)
        self.assertTrue(rule.endswith("/*/product/specs/*)"), rule)

    def test_nfr03_idempotent(self):
        self.install("--apply")
        before = self.snapshot(self.config)
        out = self.install("--apply").stdout
        self.assertIn("settings.json: no change", out)
        self.assertEqual(before, self.snapshot(self.config))

    def test_nfr03_refuses_collision(self):
        self.write(os.path.join(self.config, "agents", "cfw-coder.md"), "someone else's\n")
        result = self.install("--apply", check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Refusing to install", result.stderr)
        self.assertFalse(os.path.exists(self.ns))

    def test_nfr01_refuses_to_overwrite_hand_edited_installed_file(self):
        self.install("--apply")
        hook = os.path.join(self.ns, "hooks", "spec_index.py")
        self.write(hook, self.read(hook) + "\n# local hotfix\n")
        result = self.install("--apply", check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("edited by hand", result.stderr)

    def test_ac03_uninstall_restores_settings_byte_for_byte(self):
        self.install("--apply")
        self.uninstall("--apply")
        with open(os.path.join(self.config, "settings.json"), "rb") as f:
            self.assertEqual(f.read(), self.original_settings.encode())
        leftovers = [os.path.join(d, n) for d, _, files in os.walk(self.config) for n in files + [os.path.basename(d)] if "cfw" in n]
        self.assertEqual(leftovers, [])
        self.assertEqual(self.read(os.path.join(self.config, "commands", "spec.md")), "my own spec command\n")

    def test_ac03_uninstall_keeps_project_subtrees(self):
        self.install("--apply")
        repo = self.make_repo("orders", {"Orders.sln": ""})
        self.register(repo, "orders")
        subtree = os.path.join(self.ns, "docs", "orders")
        self.write(os.path.join(subtree, "product", "specs", "0001-x.md"), "---\nstatus: draft\n---\n# x\n")
        self.uninstall("--apply")
        self.assertTrue(os.path.isfile(os.path.join(subtree, "product", "specs", "0001-x.md")))
        self.assertTrue(os.path.isfile(os.path.join(self.ns, "projects.local.json")))
        self.assertFalse(os.path.isfile(os.path.join(self.ns, "hooks", "spec_index.py")))

    def test_retire_and_restore(self):
        self.write(os.path.join(self.config, "skills", "quickfix", "SKILL.md"), "---\nname: quickfix\n---\nmine\n")
        self.install("--apply", "--retire", "skills/quickfix")
        self.assertFalse(os.path.exists(os.path.join(self.config, "skills", "quickfix")))
        out = self.uninstall().stdout
        self.assertIn("retired at install", out)
        self.uninstall("--apply", "--restore-retired")
        self.assertEqual(self.read(os.path.join(self.config, "skills", "quickfix", "SKILL.md")), "---\nname: quickfix\n---\nmine\n")

    def test_ac06_upgrade_replaces_baseline_keeps_organization_layer(self):
        checkout = os.path.join(self.tmp, "framework")
        for item in (".claude", "docs", "CLAUDE.md.template"):
            src = os.path.join(REPO, item)
            (shutil.copytree if os.path.isdir(src) else shutil.copyfile)(src, os.path.join(checkout, item))
        installer = os.path.join(checkout, ".claude", "scripts", "install_user_level.py")
        self.install("--apply", installer=installer)
        org = os.path.join(self.ns, "docs", "constitution.md")
        self.write(org, self.read(org).replace("**VI. — add", "**VI. Tenant data never crosses tenants.** (old: add"))
        with open(org, "rb") as f:
            org_bytes = f.read()
        baseline_src = os.path.join(checkout, "docs", "constitution-baseline.md")
        self.write(baseline_src, self.read(baseline_src).replace("version: 1.0.0", "version: 1.1.0"))
        self.install("--apply", installer=installer)
        self.assertIn("version: 1.1.0", self.read(os.path.join(self.ns, "docs", "constitution-baseline.md")))
        with open(org, "rb") as f:
            self.assertEqual(f.read(), org_bytes)

    def register(self, repo, name, *extra):
        return self.run_py(os.path.join(self.ns, "scripts", "register_project.py"), "--repo", repo, "--name", name,
                           "--canonical-lang", "English", "--stakeholder-lang", "Portuguese",
                           "--stakeholder-lang-code", "pt", "--today", "2026-10-03", *extra, "--apply")


class TestGateAndRegistration(InstallCase):
    def setUp(self):
        super().setUp()
        self.install("--apply")
        self.hooks = os.path.join(self.ns, "hooks")

    def test_ac02_unregistered_repo_gets_zero_footprint(self):
        repo = self.make_repo("unrelated", {"src/a.cs": "class A {}\n", "docs/product/specs/0001-x.md": "---\nstatus: approved\n---\n"})
        before_repo, before_config = self.snapshot(repo), self.outside_namespace()
        before_ns = {k: v for k, v in self.snapshot(self.ns).items() if "__pycache__" not in k}
        spec = os.path.join(repo, "docs", "product", "specs", "0001-x.md")
        edit = {"tool_name": "Edit", "tool_input": {"file_path": spec, "new_string": "AKIA" + "A" * 16}}
        for name in ("spec_index.py", "decision_index.py", "pipeline_metrics.py", "frontmatter_check.py",
                     "secret_leak_guard.py", "validation_sync_check.py", "project_tools.py", "spec_status_sync.py"):
            result = self.hook(self.hooks, name, edit, repo)
            self.assertEqual((result.returncode, result.stdout.strip()), (0, ""), name)
        self.hook(self.hooks, "session_handoff.py", {"last_assistant_message": "bye"}, repo)
        self.hook(self.hooks, "session_brief.py", {}, repo)
        result = self.hook(self.hooks, "run_build_test.py", {"agent_type": "cfw-coder"}, repo)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.git(repo, "status", "--porcelain"), "")
        self.assertEqual(before_repo, self.snapshot(repo))
        self.assertEqual(before_config, self.outside_namespace())
        self.assertEqual(before_ns, {k: v for k, v in self.snapshot(self.ns).items() if "__pycache__" not in k})

    def outside_namespace(self):
        return {k: v for k, v in self.snapshot(self.config).items() if not k.startswith("cfw/")}

    def test_registration_creates_subtree_and_opens_gate(self):
        repo = self.make_repo("orders", {"Orders.sln": "", "README.md": "x\n"})
        report = json.loads(self.register_repo(repo).stdout)
        self.assertEqual(report["errors"], [])
        subtree = os.path.join(self.ns, "docs", "orders")
        config = json.loads(self.read(os.path.join(subtree, "project-config.json")))
        self.assertEqual(config["build_test_cmd"], "dotnet test")
        self.assertEqual(config["main_integration_branch"], "main")
        self.assertFalse(os.path.exists(os.path.join(subtree, "constitution.md")))
        self.assertTrue(os.path.isfile(os.path.join(subtree, "decisions", "0000-adr-template.md")))
        claude_md = self.read(os.path.join(subtree, "CLAUDE.md"))
        self.assertNotIn("{{PROJECT_NAME}}", claude_md)
        self.assertIn("{{DATABASE}}", report["projects"][0]["claude_md_placeholders_left"] and claude_md)
        describe = json.loads(self.run_py(os.path.join(self.hooks, "_project_paths.py"), "describe", repo).stdout)
        self.assertEqual(describe["mode"], "C")
        self.assertEqual(describe["subtree"], posix(subtree))
        # Gate open: a spec write in the subtree now gets indexed.
        spec = os.path.join(subtree, "product", "specs", "0001-orders.md")
        self.write(spec, "---\ndoc_type: spec\nid: 0001\nstatus: draft\narea: orders\n---\n# Orders\n")
        self.hook(self.hooks, "spec_index.py", {"tool_input": {"file_path": spec}}, repo)
        index = self.read(os.path.join(subtree, "product", "specs", "README.md"))
        self.assertIn("0001", index)
        # D4: header links resolve from where the index sits.
        for target in re.findall(r"`(\.\./[^`]+)`", index):
            self.assertTrue(os.path.isfile(os.path.normpath(os.path.join(subtree, "product", "specs", target))), target)

    def test_ac05_validation_sync_fires_in_mode_c_subtree_only_when_needed(self):
        repo = self.make_repo("orders", {"Orders.sln": ""})
        self.register_repo(repo)
        spec = os.path.join(self.ns, "docs", "orders", "product", "specs", "0001-orders.md")
        body = "## Business context\nwhy\n\n## Functional requirements\n- FR-01: x\n\n## Reconciliation\n"
        self.write(spec, "---\nstatus: approved\n---\n" + body)
        result = self.hook(self.hooks, "validation_sync_check.py", {"tool_name": "Edit", "tool_input": {"file_path": spec}}, repo)
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn(".validation-pt.md", context)
        source_hash = re.search(r"source_hash: (\w+)", context).group(1)
        self.write(spec[:-3] + ".validation-pt.md", f"---\nsource_hash: {source_hash}\n---\nresumo\n")
        self.write(spec, "---\nstatus: approved\n---\n" + body + "- [task 1] FR-01: matches spec\n")
        result = self.hook(self.hooks, "validation_sync_check.py", {"tool_name": "Edit", "tool_input": {"file_path": spec}}, repo)
        self.assertEqual(result.stdout.strip(), "")  # only Reconciliation changed
        self.write(spec, "---\nstatus: draft\n---\n" + body.replace("x", "y"))
        result = self.hook(self.hooks, "validation_sync_check.py", {"tool_name": "Edit", "tool_input": {"file_path": spec}}, repo)
        self.assertEqual(result.stdout.strip(), "")  # not approved

    def test_skill_index_stays_inside_namespace(self):
        personal = os.path.join(self.config, "skills", "mine", "SKILL.md")
        self.write(personal, "---\nname: mine\ndescription: personal\n---\n")
        repo = self.make_repo("orders", {"Orders.sln": ""})
        self.register_repo(repo)
        skill = os.path.join(self.config, "skills", "cfw-adr-writing", "SKILL.md")
        self.hook(self.hooks, "skill_index.py", {"tool_input": {"file_path": skill}}, repo)
        index = self.read(os.path.join(self.ns, "skills-index.md"))
        self.assertIn("cfw-adr-writing", index)
        self.assertNotIn("personal", index)
        self.assertFalse(os.path.exists(os.path.join(self.config, "skills", "README.md")))
        self.hook(self.hooks, "skill_index.py", {"tool_input": {"file_path": personal}}, repo)
        self.assertNotIn("personal", self.read(os.path.join(self.ns, "skills-index.md")))

    def test_bulk_registration_reuses_shared_answers(self):
        a = self.make_repo("orders", {"Orders.sln": ""})
        b = self.make_repo("billing", {"package.json": '{"scripts": {"test": "jest"}}'})
        plan = os.path.join(self.tmp, "plan.json")
        self.write(plan, json.dumps({"shared": {"canonical_lang": "English", "stakeholder_lang": "English",
                                                "stakeholder_lang_code": "en"},
                                     "projects": [{"repo": a}, {"repo": b, "name": "billing-api"}]}))
        script = os.path.join(self.ns, "scripts", "register_project.py")
        dry = json.loads(self.run_py(script, "--plan", plan).stdout)
        self.assertFalse(dry["applied"])
        self.assertFalse(os.path.exists(os.path.join(self.ns, "docs", "orders")))
        report = json.loads(self.run_py(script, "--plan", plan, "--apply").stdout)
        self.assertEqual([p["build_test_cmd"] for p in report["projects"]], ["dotnet test", "npm test"])
        registry = json.loads(self.read(os.path.join(self.ns, "projects.local.json")))
        self.assertEqual(len(registry), 2)

    def test_registration_refuses_reserved_name(self):
        repo = self.make_repo("workflow", {"Orders.sln": ""})
        result = self.run_py(os.path.join(self.ns, "scripts", "register_project.py"), "--repo", repo, "--apply", check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("collides", result.stdout)

    def register_repo(self, repo):
        return self.run_py(os.path.join(self.ns, "scripts", "register_project.py"), "--repo", repo,
                           "--canonical-lang", "English", "--stakeholder-lang", "Portuguese",
                           "--stakeholder-lang-code", "pt", "--today", "2026-10-03", "--apply")


class TestMigration(TempCase):
    def test_ac07_migrate_existing_context(self):
        src = os.path.join(self.tmp, "context")
        self.write(os.path.join(src, "README.md"), "See [orders](arquitetura/orders.md) and [ADR 3](adr/ADR-003-bus.md#why).\n")
        self.write(os.path.join(src, "arquitetura", "orders.md"),
                   "---\ntitulo: Orders\n---\n# Orders\nDecided in [this ADR](../adr/ADR-003-bus.md).\n"
                   "![diagram](img/flow.png)\n\n```\n[not a link](../nowhere.md)\n```\n")
        self.write(os.path.join(src, "arquitetura", "img", "flow.png"), "png")
        self.write(os.path.join(src, "adr", "ADR-003-bus.md"), "# Bus\nSee [specs](../specs/checkout.md).\n")
        self.write(os.path.join(src, "adr", "outro.md"), "# Other\n")
        self.write(os.path.join(src, "specs", "checkout.md"), "# Checkout\n[ref]: ../arquitetura/orders.md\n")
        before = self.snapshot(src)
        dest = os.path.join(self.tmp, "subtree")
        result = self.run_py(os.path.join(REPO, ".claude", "scripts", "migrate_context.py"), "--source", src,
                             "--dest", dest, "--rename-key", "titulo=title", "--apply")
        report = json.loads(result.stdout)
        self.assertEqual(report["broken_links_introduced"], [])
        self.assertEqual(report["docs_missing_required_keys"], [])
        self.assertTrue(report["source_unchanged"])
        self.assertEqual(before, self.snapshot(src))
        self.assertTrue(os.path.isfile(os.path.join(dest, "decisions", "0003-bus.md")))
        self.assertTrue(os.path.isfile(os.path.join(dest, "decisions", "0004-outro.md")))
        self.assertTrue(os.path.isfile(os.path.join(dest, "product", "specs", "0001-checkout.md")))
        orders = self.read(os.path.join(dest, "architecture", "orders.md"))
        self.assertIn("title: Orders", orders)
        self.assertIn("(../decisions/0003-bus.md)", orders)
        self.assertIn("[not a link](../nowhere.md)", orders)
        self.assertIn("(adr/", self.read(os.path.join(src, "README.md")))
        self.assertIn("(decisions/0003-bus.md#why)", self.read(os.path.join(dest, "README.md")))

    def test_refuses_non_empty_dest(self):
        src = os.path.join(self.tmp, "context")
        self.write(os.path.join(src, "a.md"), "# a\n")
        dest = os.path.join(self.tmp, "subtree")
        self.write(os.path.join(dest, "keep.md"), "mine\n")
        result = self.run_py(os.path.join(REPO, ".claude", "scripts", "migrate_context.py"), "--source", src,
                             "--dest", dest, "--apply", check=False)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
