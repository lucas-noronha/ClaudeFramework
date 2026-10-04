"""Install (or upgrade) this framework user-level — mode C, framework ADR 0014 as
amended by framework ADR 0017. Run it from a checkout of the framework repository:

    python .claude/scripts/install_user_level.py                # dry run
    python .claude/scripts/install_user_level.py --apply        # install

What it does (framework spec 0001 FR-01..FR-10, NFR-03):

- **Namespace prefix** (`--prefix`, default `cfw`). Agents, commands and
  skills land as `<config>/agents/<prefix>-coder.md`,
  `<config>/commands/<prefix>-spec.md` and
  `<config>/skills/<prefix>-project-registration/`, so they never collide
  with a user's own `spec`/`plan` commands. Hooks, scripts, the registry,
  templates and the shared `docs/` root live in `<config>/<prefix>/`.
  The framework's own specs and ADRs (`evolution/`) are development
  history of this repository and are never installed. Every
  cross-reference in the
  installed text is rewritten consistently: `/spec` → `/cfw-spec`,
  `` `coder` `` → `` `cfw-coder` ``, `.claude/hooks/` → the absolute hooks
  path, `docs/workflow/...` → the absolute shared root.
- **One config source** (FR-09): `<config>/<prefix>/framework.json`
  records the registry, shared root, projects root, template locations
  and prefix. Hooks read it; the installed `project-registration` skill
  gets the same values in a generated "Install binding" block.
- **Manifest + uninstall** (FR-02): every file written and every
  `settings.json` entry added is recorded in
  `<config>/<prefix>/manifest.json`. `scripts/uninstall.py` removes
  exactly that, dry-run by default.
- **Worktrees root** (`--worktrees-root`, optional): the per-machine
  folder `/worktree` creates spec worktrees under, recorded in
  `framework.json` and kept across upgrades until changed (`""` clears it).
- **Language** (`--language NAME --language-code CODE`, optional; framework
  spec 0005, ADR 0023): recorded in `framework.json` and kept across
  upgrades. With a non-English language each translatable source is read
  from the cache `<namespace>/translations/<path>` (index:
  `translations/record.json`, built by `scripts/translation.py`) instead of
  the English source, then rewritten and hashed as usual. A translatable
  source with no fresh cache entry aborts the run before any write.
  English (no flag, `en`, `en-*`) reads no cache.
- **Absolute hook paths** (FR-04), and permissions generated against the
  absolute projects root (FR-08).
- **No per-project placeholder survives** (FR-06, AC-04): per-project
  `{{…}}` tokens in shared files become runtime tokens (`<canonical_lang>`,
  `<main_integration_branch>`, ...) that the registration skill defines,
  dates are stamped, and the install aborts if anything else is left.
- **Per-project hooks stay out** (FR-07): `*.py.example` files are never
  installed; `project_tools.py` runs whatever a project's own config
  declares instead.
- **Constitution layers** (FR-10, framework ADR 0018): `constitution-baseline.md`
  is replaced on every upgrade; `constitution.md` (organization layer)
  and `glossary.md` are created once and never overwritten.
- **Idempotent, refuses on collision** (NFR-03). Re-running with no
  source change changes nothing. A destination file this install
  doesn't own aborts the whole run before anything is written. An
  installed file someone edited by hand also aborts it: per NFR-01 a fix
  belongs in this repository first, never only in an installed copy.

Stdlib only. Never fetches, never touches any code repository.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(SCRIPTS_DIR))
SRC_CLAUDE = os.path.join(REPO, ".claude")
SRC_DOCS = os.path.join(REPO, "docs")

sys.path.insert(0, os.path.join(SRC_CLAUDE, "hooks"))
import skill_index  # noqa: E402

sys.path.insert(0, SCRIPTS_DIR)
import translation  # noqa: E402

MANIFEST_VERSION = 1
# Run from the framework checkout; installing them would only confuse.
EXCLUDED_COMMANDS = {"setup-framework"}
EXCLUDED_SCRIPTS = {"install_user_level.py"}
EXCLUDED_AGENTS = {"translator"}  # setup-time only; never installed (ADR 0023)
RESERVED_PREFIXES = {"", "docs", "hooks", "scripts", "agents", "commands", "skills"}

# Per-project placeholders → the runtime tokens the installed
# `project-registration` skill defines (framework spec 0001 FR-06).
RUNTIME_TOKENS = {
    "LANGUAGE": "<language>",
    "BUILD_TEST_CMD": "<build_test_cmd>",
    "MAIN_INTEGRATION_BRANCH": "<main_integration_branch>",
    "PROJECT_NAME": "<project name>",
    "BACKEND_DIR": "<backend dir>",
    "FRONTEND_DIR": "<frontend dir>",
}
# Placeholders allowed to stay literal, per file (Domain 1 step 1's
# permanent list): copy-paste examples, not values awaiting a fill.
PERMANENT_PLACEHOLDERS = {
    "docs/workflow/plugin-integrations.md": {"AZURE_DEVOPS_ORG", "AZURE_DEVOPS_PAT_ENV_VAR"},
}
# File kinds whose `{{…}}` are permanent: template sources a
# registration resolves per project.
PERMANENT_KINDS = {"template", "adr-template"}
PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")


def posix(path: str) -> str:
    return path.replace("\\", "/").rstrip("/")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def permission_path(path: str) -> str:
    """Absolute path in Claude Code's permission-rule form: `//` + a
    POSIX path, with a Windows drive as `//c/...`.
    """
    path = posix(path)
    drive = re.match(r"^([A-Za-z]):/(.*)$", path)
    if drive:
        return f"//{drive.group(1).lower()}/{drive.group(2)}"
    return "/" + path if path.startswith("/") else path


def read_text(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def git_commit() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True, timeout=10)
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    value = sha.stdout.strip() or "unknown"
    return value + ("-dirty" if dirty.stdout.strip() else "")


# ---------------------------------------------------------------- inventory


def stems(folder: str, suffix: str):
    return sorted(name[: -len(suffix)] for name in os.listdir(folder) if name.endswith(suffix))


def inventory():
    agents = [a for a in stems(os.path.join(SRC_CLAUDE, "agents"), ".md") if a not in EXCLUDED_AGENTS]
    commands = [c for c in stems(os.path.join(SRC_CLAUDE, "commands"), ".md") if c not in EXCLUDED_COMMANDS]
    skills_root = os.path.join(SRC_CLAUDE, "skills")
    skills = sorted(d for d in os.listdir(skills_root) if os.path.isfile(os.path.join(skills_root, d, "SKILL.md")))
    adrs = sorted(n for n in os.listdir(os.path.join(SRC_DOCS, "decisions")) if re.match(r"^\d{4}-.+\.md$", n))
    return agents, commands, skills, adrs


# ---------------------------------------------------------------- rewriting


class Rewriter:
    """Every cross-reference transform, in one place (framework spec 0001 FR-01)."""

    def __init__(self, prefix, agents, commands, skills, adrs, config_dir, namespace, shared, today):
        self.p = prefix
        self.agents, self.commands, self.skills, self.adrs = agents, commands, skills, adrs
        self.config_dir, self.ns, self.shared, self.today = posix(config_dir), posix(namespace), posix(shared), today

    def references(self, text: str) -> str:
        p = self.p
        # 1. Slash commands, on the original relative text (before any
        #    absolute path is spliced in, so a path segment can't match).
        names = "|".join(sorted(map(re.escape, self.commands), key=len, reverse=True))
        text = re.sub(rf"(?<![\w./-])/({names})(?![\w-])", lambda m: f"/{p}-{m.group(1)}", text)
        # 2. Backticked agent and skill names.
        roles = "|".join(sorted(map(re.escape, self.agents + self.skills), key=len, reverse=True))
        text = re.sub(rf"`({roles})`", lambda m: f"`{p}-{m.group(1)}`", text)
        # 3. Specific machinery files.
        text = re.sub(rf"\.claude/agents/({'|'.join(map(re.escape, self.agents))})\.md",
                      lambda m: f"{self.config_dir}/agents/{p}-{m.group(1)}.md", text)
        text = re.sub(rf"\.claude/commands/({'|'.join(map(re.escape, self.commands))})\.md",
                      lambda m: f"{self.config_dir}/commands/{p}-{m.group(1)}.md", text)
        text = re.sub(r"\.claude/skills/README\.md", f"{self.ns}/skills-index.md", text)
        skill_names = "|".join(map(re.escape, self.skills))
        text = re.sub(rf"(?<![\w/.-])(?:(?:\.claude/)?skills/)?({skill_names})/SKILL\.md",
                      lambda m: f"{self.config_dir}/skills/{p}-{m.group(1)}/SKILL.md", text)
        text = re.sub(r"(?:\$\{CLAUDE_PROJECT_DIR:-\.\}/|(?:\.\./)+)?\.claude/(hooks|scripts)/",
                      lambda m: f"{self.ns}/{m.group(1)}/", text)
        # 4. Shared docs material → the absolute shared root. Project
        #    content (`docs/product/specs/`, `docs/architecture/*.md`,
        #    project ADRs) is left for the registration skill to rebind.
        adr_names = "|".join(map(re.escape, self.adrs))
        shared = (r"workflow/[\w.-]+\.md|workflow/|glossary\.md|constitution-baseline\.md|constitution\.md|"
                  r"product/requirements-template\.md|"
                  rf"architecture/[\w-]+\.md\.template|decisions/(?:{adr_names})")
        text = re.sub(rf"(?<![\w/.-])(?:\.\./)*docs/({shared})", lambda m: f"{self.shared}/{m.group(1)}", text)
        return text

    def frontmatter(self, text: str, kind: str) -> str:
        fm = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        if not fm:
            return text
        body = fm.group(1)
        if kind in ("agent", "skill"):
            body = re.sub(r"^name:\s*(\S+)", lambda m: f"name: {self.p}-{m.group(1)}", body, count=1, flags=re.MULTILINE)
        roles = set(self.agents)
        body = re.sub(
            r"^applies_to:\s*\[(.*?)\]",
            lambda m: "applies_to: [" + ", ".join(
                f"{self.p}-{r.strip()}" if r.strip() in roles else r.strip() for r in m.group(1).split(",") if r.strip()
            ) + "]",
            body, flags=re.MULTILINE,
        )
        if kind not in ("template", "adr-template"):
            body = body.replace("{{DATE}}", self.today)  # template sources keep theirs for registration
        return text[: fm.start(1)] + body + text[fm.end(1):]

    def runtime_tokens(self, text: str) -> str:
        text = text.replace("{{DATE}}", "<today's date, YYYY-MM-DD>")
        return PLACEHOLDER.sub(lambda m: RUNTIME_TOKENS.get(m.group(1), m.group(0)), text)


def binding_block(cfg: dict) -> str:
    return (
        "> **Install binding — generated by the user-level installer, do not edit (framework ADR 0017).**\n"
        f"> Framework config: `{cfg['namespace_dir']}/framework.json`. Registry: `{cfg['registry']}`.\n"
        f"> Shared `docs/` root: `{cfg['shared_docs_root']}`. Projects root: `{cfg['projects_root']}`.\n"
        f"> `CLAUDE.md` template: `{cfg['claude_md_template']}`. Scripts: `{cfg['scripts_dir']}`.\n"
        f"> Probe: `{cfg['python']} \"{cfg['hooks_dir']}/_project_paths.py\" describe`.\n"
        "> These values win over anything this skill would otherwise infer from folder shape.\n\n"
    )


def insert_after_frontmatter(text: str, block: str) -> str:
    fm = re.match(r"^---\n.*?\n---\n", text, re.DOTALL)
    if not fm:
        return block + text
    return text[: fm.end()] + "\n" + block + text[fm.end():].lstrip("\n")


# ---------------------------------------------------------------- planning


class Plan:
    def __init__(self):
        # dest(posix) -> {"data": bytes, "policy": str, "kind": str, "source": str,
        #                 "source_sha256": str|None, "translation": translated|english|none}
        self.files = {}
        self.missing = []  # translatable sources with no fresh cache entry (FR-06)

    def add(self, dest, data, policy, kind, source, source_sha256=None, translated="none"):
        if isinstance(data, str):
            data = data.encode("utf-8")
        self.files[posix(dest)] = {"data": data, "policy": policy, "kind": kind, "source": source,
                                   "source_sha256": source_sha256, "translation": translated}


def build_plan(args, cfg, rw, agents, commands, skills, adrs, today):
    plan = Plan()
    ns, conf = cfg["namespace_dir"], cfg["config_dir"]
    cache = f"{ns}/translations"
    translating = not translation.is_english(cfg.get("language_code"))
    record = translation.load_record(f"{cache}/record.json") if translating else {"files": {}}
    stale_language = translating and record.get("language_code") != cfg.get("language_code")

    def chosen_text(src_rel, dest, policy):
        """(text, source_sha256, translation) — the cached translation when fresh, else the source."""
        source = os.path.join(REPO, src_rel)
        text = read_text(source)
        sha = translation.file_sha256(source)
        if not translating or not translation.is_translatable(src_rel):
            return text, sha, "none"
        entry = record["files"].get(src_rel)
        if entry and entry.get("source_sha256") == sha and not stale_language:
            if entry.get("status") == "english":
                return text, sha, "english"
            cached = os.path.join(cache, src_rel)
            if entry.get("status") in ("translated", "existing") and os.path.isfile(cached):
                with open(cached, encoding="utf-8-sig") as f:
                    return f.read(), sha, "translated"
        if policy == "keep" and os.path.isfile(dest):
            return text, sha, "english"  # never rewritten, so nothing to translate
        plan.missing.append(src_rel)
        return text, sha, "none"

    def text_file(src_rel, dest, kind, policy="replace", rewrite=True, tokens=True, transform=None):
        text, source_hash, translated = chosen_text(src_rel, posix(dest), policy)
        text = rw.frontmatter(text, kind)
        if rewrite:
            text = rw.references(text)
        if tokens and kind not in PERMANENT_KINDS:
            text = rw.runtime_tokens(text)
        if transform:
            text = transform(text)
        plan.add(dest, text, policy, kind, src_rel, source_hash, translated)

    for a in agents:
        text_file(f".claude/agents/{a}.md", f"{conf}/agents/{args.prefix}-{a}.md", "agent")
    for c in commands:
        text_file(f".claude/commands/{c}.md", f"{conf}/commands/{args.prefix}-{c}.md", "command")
    for s in skills:
        root = os.path.join(SRC_CLAUDE, "skills", s)
        for dirpath, _, filenames in os.walk(root):
            for name in sorted(filenames):
                rel = posix(os.path.relpath(os.path.join(dirpath, name), REPO))
                inner = posix(os.path.relpath(os.path.join(dirpath, name), root))
                dest = f"{conf}/skills/{args.prefix}-{s}/{inner}"
                if name.endswith(".md"):
                    transform = (lambda t: insert_after_frontmatter(t, binding_block(cfg))) if s == "project-registration" and name == "SKILL.md" else None
                    text_file(rel, dest, "skill", transform=transform)
                else:
                    with open(os.path.join(dirpath, name), "rb") as f:
                        data = f.read()
                    plan.add(dest, data, "replace", "skill", rel, sha256(data))

    for name in sorted(os.listdir(os.path.join(SRC_CLAUDE, "hooks"))):
        if name.endswith(".py"):
            with open(os.path.join(SRC_CLAUDE, "hooks", name), "rb") as f:
                data = f.read()
            plan.add(f"{ns}/hooks/{name}", data, "replace", "hook", f".claude/hooks/{name}", sha256(data))
    for dirpath, dirnames, filenames in os.walk(SCRIPTS_DIR):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in sorted(filenames):
            if not name.endswith(".py") or name in EXCLUDED_SCRIPTS:
                continue
            rel = posix(os.path.relpath(os.path.join(dirpath, name), SCRIPTS_DIR))
            with open(os.path.join(dirpath, name), "rb") as f:
                data = f.read()
            plan.add(f"{ns}/scripts/{rel}", data, "replace", "script", f".claude/scripts/{rel}", sha256(data))

    docs = f"{ns}/docs"
    text_file("docs/constitution-baseline.md", f"{docs}/constitution-baseline.md", "doc")
    text_file("docs/constitution.md", f"{docs}/constitution.md", "doc", policy="keep")
    text_file("docs/glossary.md.template", f"{docs}/glossary.md", "doc", policy="keep",
              transform=lambda t: "\n".join(line for line in t.split("\n") if "{{TERM}}" not in line))
    for name in sorted(os.listdir(os.path.join(SRC_DOCS, "workflow"))):
        if name.endswith(".md"):
            text_file(f"docs/workflow/{name}", f"{docs}/workflow/{name}", "doc")
    text_file("docs/product/requirements-template.md", f"{docs}/product/requirements-template.md", "doc")
    for name in sorted(os.listdir(os.path.join(SRC_DOCS, "architecture"))):
        if name.endswith(".md.template"):
            text_file(f"docs/architecture/{name}", f"{docs}/architecture/{name}", "template")
    # Only the ADR *template* ships: `docs/decisions/` holds nothing else
    # since the framework's own ADRs moved to `evolution/` (never installed).
    for name in adrs:
        text_file(f"docs/decisions/{name}", f"{docs}/decisions/{name}", "adr-template",
                  rewrite=False, tokens=False)
    text_file("CLAUDE.md.template", cfg["claude_md_template"], "template")

    plan.add(f"{ns}/framework.json", json.dumps(cfg, indent=2) + "\n", "replace", "generated", "(generated)")
    plan.add(f"{ns}/README.md", namespace_readme(cfg), "replace", "generated", "(generated)")
    return plan


def namespace_readme(cfg: dict) -> str:
    return f"""# Claude framework — user-level install (`{cfg['prefix']}`)

Installed {cfg['installed_at']} from `{cfg['source_repo']}` at
`{cfg['framework_commit']}` by `install_user_level.py` (framework ADR 0017).

- Commands are `/{cfg['prefix']}-spec`, `/{cfg['prefix']}-plan`, `/{cfg['prefix']}-quick`, ... ;
  agents and skills carry the same `{cfg['prefix']}-` prefix.
- Hooks do nothing in a repo that isn't registered. Registration happens
  lazily, the first time a `/{cfg['prefix']}-*` pipeline command runs there.
- `docs/` here is the shared root (constitution layers, workflow docs,
  templates). The framework's own specs and ADRs stay in its repository
  (`evolution/`) and are never installed. Project subtrees are
  created under the projects root: `{cfg['projects_root']}`.

**Don't fix anything in this folder by hand.** Every installed file is
hashed in `manifest.json`; the next upgrade refuses to overwrite a file
that changed, so a local fix can't be silently lost — or silently kept
diverging. Fix it in the framework repository, then re-run the
installer from there (framework spec 0001 NFR-01).

Uninstall (dry run first, then `--apply`):

    {cfg['python']} "{cfg['scripts_dir']}/uninstall.py"
"""


# ---------------------------------------------------------------- settings


def resolve_settings_template(cfg: dict) -> dict:
    text = read_text(os.path.join(SRC_CLAUDE, "settings.multi-project.json.example"))
    text = text.replace("{{HOOKS_DIR}}", cfg["hooks_dir"]).replace("{{PYTHON}}", cfg["python"])
    text = text.replace("{{PROJECTS_ROOT_PERMISSION_PATH}}", permission_path(cfg["projects_root"]))
    leftover = PLACEHOLDER.findall(text)
    if leftover:
        raise SystemExit(f"settings template still has placeholders: {sorted(set(leftover))}")
    return json.loads(text)


def unmerge(settings: dict, record: dict) -> list:
    """Remove a previous install's additions in place. Returns what could
    not be found (the user changed or removed it since).
    """
    missing = []
    hooks = settings.get("hooks") if isinstance(settings.get("hooks"), dict) else {}
    for item in record.get("added_groups", []):
        groups = hooks.get(item["event"], [])
        for index in range(len(groups) - 1, -1, -1):
            if groups[index] == item["group"]:
                del groups[index]
                break
        else:
            missing.append(f"hooks.{item['event']} group {json.dumps(item['group'])[:80]}")
    allow = (settings.get("permissions") or {}).get("allow")
    for rule in record.get("added_permissions", []):
        if isinstance(allow, list) and rule in allow:
            allow.remove(rule)
        else:
            missing.append(f"permissions.allow {rule}")
    # Scalar keys: removed only while they still hold the value we set; a
    # value we overwrote (--set-language-setting) goes back to what it was.
    previous = record.get("previous_scalars", {})
    for key, value in record.get("added_scalars", {}).items():
        if settings.get(key) != value:
            missing.append(f"{key} (changed since install, left alone)")
        elif key in previous:
            settings[key] = previous[key]
        else:
            del settings[key]
    # Containers this install created, deepest first — only if now empty.
    for key in reversed(record.get("created_keys", [])):
        parts = key.split(".")
        parent = settings
        for part in parts[:-1]:
            parent = parent.get(part, {}) if isinstance(parent, dict) else {}
        if isinstance(parent, dict) and parts[-1] in parent and parent[parts[-1]] in ([], {}):
            del parent[parts[-1]]
    return missing


def merge(settings: dict, template: dict, scalars: dict = None, overwrite: bool = False) -> dict:
    """Append this install's hook groups and permissions, never touching
    an existing entry. A group whose every hook command already exists in
    that event is skipped (idempotency). `scalars` (Claude Code's `language`)
    are set when absent and recorded; an equal value is not ours (not
    recorded); a different one is reported in `kept_scalars` and left alone
    unless `overwrite`, which records the value it replaced.
    """
    record = {"added_groups": [], "added_permissions": [], "created_keys": [],
              "added_scalars": {}, "previous_scalars": {}, "kept_scalars": {}}
    for key, value in (scalars or {}).items():
        if key not in settings:
            settings[key] = value
            record["added_scalars"][key] = value
        elif settings[key] != value:
            if overwrite:
                record["previous_scalars"][key] = settings[key]
                settings[key] = value
                record["added_scalars"][key] = value
            else:
                record["kept_scalars"][key] = settings[key]

    def ensure(container, key, default, path):
        if key not in container:
            container[key] = default
            record["created_keys"].append(path)
        return container[key]

    hooks = ensure(settings, "hooks", {}, "hooks")
    for event, groups in template.get("hooks", {}).items():
        existing = ensure(hooks, event, [], f"hooks.{event}")
        present = {h.get("command") for g in existing for h in g.get("hooks", []) if isinstance(h, dict)}
        for group in groups:
            new_hooks = [h for h in group.get("hooks", []) if h.get("command") not in present]
            if not new_hooks:
                continue
            added = dict(group, hooks=new_hooks)
            existing.append(added)
            record["added_groups"].append({"event": event, "group": added})
    allow_rules = template.get("permissions", {}).get("allow", [])
    if allow_rules:
        permissions = ensure(settings, "permissions", {}, "permissions")
        allow = ensure(permissions, "allow", [], "permissions.allow")
        for rule in allow_rules:
            if rule not in allow:
                allow.append(rule)
                record["added_permissions"].append(rule)
    return record


# ---------------------------------------------------------------- main


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def default_python() -> str:
    return "python" if shutil.which("python") else "python3"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Install or upgrade the framework user-level (mode C).")
    parser.add_argument("--prefix", default="cfw", help="namespace prefix for agents/commands/skills (default: cfw)")
    parser.add_argument("--config-dir", help="Claude Code user config dir (default: ~/.claude; required if CLAUDE_CONFIG_DIR is set)")
    parser.add_argument("--projects-root", help="where project subtrees are created (default: <namespace>/docs)")
    parser.add_argument("--worktrees-root", help="per-machine folder /worktree creates spec worktrees under (default: kept from the last install, else none = sibling of the repo; \"\" clears it)")
    parser.add_argument("--language", help="project language name, e.g. Portuguese (default: kept from the last install, else English)")
    parser.add_argument("--language-code", help="its BCP 47 code, e.g. pt-BR; en / en-* means English (needs --language)")
    parser.add_argument("--set-language-setting", action="store_true", help="overwrite a different `language` already in settings.json (uninstall restores it); without it that value is left alone")
    parser.add_argument("--python", default=None, help="interpreter command used in hook commands (default: python, else python3)")
    parser.add_argument("--retire", action="append", default=[], help="move one of your own files/folders under the config dir aside (restorable by uninstall)")
    parser.add_argument("--today", help=argparse.SUPPRESS)
    parser.add_argument("--apply", action="store_true", help="write; without it this is a dry run")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    if not re.match(r"^[a-z][a-z0-9]{1,15}$", args.prefix) or args.prefix in RESERVED_PREFIXES:
        print(f"Invalid prefix {args.prefix!r}: lowercase letters/digits, 2-16 chars, starting with a letter.", file=sys.stderr)
        return 2

    if args.config_dir:
        config_dir = os.path.abspath(os.path.expanduser(args.config_dir))
    elif os.environ.get("CLAUDE_CONFIG_DIR"):
        print("CLAUDE_CONFIG_DIR is set, so Claude Code doesn't read ~/.claude. Re-run with "
              "--config-dir pointing at the directory it does read (framework ADR 0014).", file=sys.stderr)
        return 2
    else:
        config_dir = os.path.expanduser(os.path.join("~", ".claude"))
    config_dir = posix(config_dir)
    namespace = f"{config_dir}/{args.prefix}"
    manifest_path = f"{namespace}/manifest.json"
    today = args.today or datetime.date.today().isoformat()

    old_manifest = {}
    if os.path.isfile(manifest_path):
        try:
            old_manifest = load_json(manifest_path)
        except ValueError:
            print(f"{manifest_path} doesn't parse — refusing to guess what this install owns.", file=sys.stderr)
            return 2
    old_files = old_manifest.get("files", {})
    old_cfg = {}
    if os.path.isfile(f"{namespace}/framework.json"):
        try:
            old_cfg = load_json(f"{namespace}/framework.json")
        except ValueError:
            old_cfg = {}

    projects_root = posix(os.path.abspath(os.path.expanduser(args.projects_root))) if args.projects_root else old_cfg.get("projects_root") or f"{namespace}/docs"
    if args.worktrees_root is None:
        worktrees_root = old_cfg.get("worktrees_root")
    else:
        worktrees_root = posix(os.path.abspath(os.path.expanduser(args.worktrees_root))) if args.worktrees_root.strip() else None
    language = args.language if args.language is not None else old_cfg.get("language")
    language_code = args.language_code if args.language_code is not None else old_cfg.get("language_code")
    language, language_code = (language or "").strip() or None, (language_code or "").strip() or None
    if bool(language) != bool(language_code):
        print("--language and --language-code go together (e.g. --language Portuguese --language-code pt-BR).", file=sys.stderr)
        return 2
    cfg = {
        "install_mode": "user-level",
        "prefix": args.prefix,
        "framework_commit": git_commit(),
        "installed_at": today,
        "source_repo": posix(REPO),
        "config_dir": config_dir,
        "namespace_dir": namespace,
        "hooks_dir": f"{namespace}/hooks",
        "scripts_dir": f"{namespace}/scripts",
        "skills_dir": f"{config_dir}/skills",
        "skills_index": f"{namespace}/skills-index.md",
        "registry": f"{namespace}/projects.local.json",
        "shared_docs_root": f"{namespace}/docs",
        "projects_root": projects_root,
        "worktrees_root": worktrees_root,
        "claude_md_template": f"{namespace}/CLAUDE.md.template",
        "python": args.python or old_cfg.get("python") or default_python(),
    }
    if language:
        cfg["language"], cfg["language_code"] = language, language_code

    agents, commands, skills, adrs = inventory()
    rw = Rewriter(args.prefix, agents, commands, skills, adrs, config_dir, namespace, cfg["shared_docs_root"], today)
    plan = build_plan(args, cfg, rw, agents, commands, skills, adrs, today)

    # ---- every translatable source needs a fresh cache entry (ADR 0023 section 2, FR-06)
    if plan.missing:
        print("Install aborted — no fresh translation for these sources (nothing was written):", file=sys.stderr)
        for rel in sorted(plan.missing):
            print(f"  - {rel}", file=sys.stderr)
        print(f"Run the setup's translation step for {cfg['language_code']} first "
              f"(cache: {namespace}/translations/), then re-run.", file=sys.stderr)
        return 1

    # ---- verification before anything is written (AC-04 + FR-01)
    problems = []
    for dest, item in plan.files.items():
        if item["kind"] in PERMANENT_KINDS or item["kind"] in ("hook", "script") or not dest.endswith((".md", ".json")):
            continue
        text = item["data"].decode("utf-8")
        allowed = PERMANENT_PLACEHOLDERS.get(item["source"], set())
        left = sorted({name for name in PLACEHOLDER.findall(text) if name not in allowed})
        if left:
            problems.append(f"unresolved placeholder(s) {left} in {dest}")
        if item["kind"] in ("agent", "command", "skill"):
            names = "|".join(commands)
            stray = re.findall(rf"(?<![\w./-])/({names})(?![\w-])", text)
            if stray:
                problems.append(f"unprefixed command reference(s) {sorted(set(stray))} in {dest}")
    if problems:
        print("Install aborted — the rewrite left something behind (a bug in this installer, not in your setup):", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    # ---- collision / divergence checks (NFR-03, NFR-01)
    collisions, modified, actions = [], [], []
    for dest, item in sorted(plan.files.items()):
        exists = os.path.isfile(dest)
        current = None
        if exists:
            with open(dest, "rb") as f:
                current = f.read()
        owned = dest in old_files
        if not exists:
            actions.append(("create", dest))
        elif item["policy"] == "keep":
            actions.append(("keep", dest))  # user-amendable layer: never overwritten
        elif not owned:
            collisions.append(dest)
        elif sha256(current) != old_files[dest]["sha256"] and item["kind"] != "generated":
            modified.append(dest)
        elif current == item["data"]:
            actions.append(("unchanged", dest))
        else:
            actions.append(("update", dest))

    stale = []
    for dest, meta in old_files.items():
        if dest in plan.files or dest == posix(cfg["skills_index"]) or not os.path.isfile(dest):
            continue
        with open(dest, "rb") as f:
            current_hash = sha256(f.read())
        if current_hash == meta["sha256"] or meta.get("kind") == "generated":
            stale.append(dest)
        elif meta.get("policy") != "keep":
            modified.append(dest)

    retire = []
    for target in args.retire:
        path = posix(os.path.abspath(os.path.expanduser(target if os.path.isabs(target) else os.path.join(config_dir, target))))
        if not path.startswith(config_dir + "/") or path.startswith(namespace + "/") or not os.path.exists(path):
            print(f"--retire {target}: must be an existing path under {config_dir}, outside {namespace}.", file=sys.stderr)
            return 2
        backup = f"{namespace}/backups/retired/{path[len(config_dir) + 1:]}"
        if os.path.exists(backup):
            print(f"--retire {target}: a backup already exists at {backup}.", file=sys.stderr)
            return 2
        retire.append({"original": path, "backup": backup})
    retired_paths = {r["original"] for r in retire}
    collisions = [c for c in collisions if c not in retired_paths and not any(c.startswith(r + "/") for r in retired_paths)]

    if collisions or modified:
        if collisions:
            print("Refusing to install — these destinations exist and this install doesn't own them:", file=sys.stderr)
            for c in collisions:
                print(f"  - {c}", file=sys.stderr)
            print("Move them aside (or pass --retire <path> so uninstall can restore them), or pick another --prefix.", file=sys.stderr)
        if modified:
            print("Refusing to upgrade — these installed files were edited by hand since the last install:", file=sys.stderr)
            for m in modified:
                print(f"  - {m}", file=sys.stderr)
            print("Port the fix into the framework repository first (framework spec 0001 NFR-01), then restore the "
                  "installed copy (or remove it) and re-run.", file=sys.stderr)
        return 1

    # ---- settings.json
    settings_path = f"{config_dir}/settings.json"
    settings_preexisted = old_manifest.get("settings", {}).get("preexisted") if old_manifest else os.path.isfile(settings_path)
    if os.path.isfile(settings_path):
        try:
            settings = load_json(settings_path)
        except ValueError:
            print(f"{settings_path} doesn't parse — fix it first; refusing to guess.", file=sys.stderr)
            return 2
    else:
        settings = {}
    original_settings = json.loads(json.dumps(settings))
    # An earlier --set-language-setting overwrite sticks on upgrade only while the
    # value is still the one it wrote; one the user changed since is left alone.
    old_scalars = old_manifest.get("settings", {})
    sticky = ("language" in old_scalars.get("previous_scalars", {})
              and settings.get("language") == old_scalars.get("added_scalars", {}).get("language"))
    if old_manifest.get("settings"):
        lost = unmerge(settings, old_manifest["settings"])
        if lost:
            print("Note: some previously installed settings entries were already changed or removed by hand:")
            for item in lost:
                print(f"  - {item}")
    # Claude Code's `language` follows the install's language; English writes nothing.
    scalars = {"language": language} if language and not translation.is_english(language_code) else {}
    record = merge(settings, resolve_settings_template(cfg), scalars, args.set_language_setting or sticky)
    kept_scalars = record.pop("kept_scalars")
    for key in ("added_scalars", "previous_scalars"):
        if not record[key]:
            del record[key]  # manifests stay as before unless a scalar was set
    previous_keys = set(old_manifest.get("settings", {}).get("created_keys", []))
    record["created_keys"] = sorted(set(record["created_keys"]) | previous_keys, key=lambda k: (k.count("."), k))
    settings_changed = settings != original_settings

    registry_path = cfg["registry"]
    registry_created = old_manifest.get("registry", {}).get("created", False) if old_manifest else not os.path.isfile(registry_path)
    legacy = [p for p in (f"{config_dir}/projects.local.json", f"{config_dir}/docs/constitution.md") if os.path.isfile(p)]

    # ---- report
    counts = {}
    for action, _ in actions:
        counts[action] = counts.get(action, 0) + 1
    print(f"{'Installing' if args.apply else 'Dry run'}: prefix `{args.prefix}` into {config_dir}")
    print(f"  namespace: {namespace}   projects root: {projects_root}")
    if language:
        print(f"  language: {language} ({language_code})")
    print(f"  worktrees root: {worktrees_root or '(none — each spec worktree sits beside its repo)'}")
    print("  files: " + ", ".join(f"{n} {a}" for a, n in sorted(counts.items())) + (f", {len(stale)} removed (dropped upstream)" if stale else ""))
    for action, dest in actions:
        if action in ("create", "update", "keep"):
            print(f"    {action:9} {dest}")
    for dest in stale:
        print(f"    {'remove':9} {dest}")
    print(f"  settings.json: {'+' + str(len(record['added_groups'])) + ' hook group(s), +' + str(len(record['added_permissions'])) + ' permission(s)' if settings_changed else 'no change'}")
    for key in record.get("added_scalars", {}):
        replaced = record.get("previous_scalars", {}).get(key)
        print(f"  settings.json: {key} = {record['added_scalars'][key]!r}" + (f" (replaces {replaced!r}; uninstall restores it)" if replaced is not None else ""))
    for key, value in kept_scalars.items():
        print(f"  settings.json: {key} is {value!r}, left alone (--set-language-setting overwrites it)")
    for r in retire:
        print(f"  retire: {r['original']} -> {r['backup']}")
    if legacy:
        print("  Note: a pre-namespace mode C install seems to exist (" + ", ".join(legacy) + "). It is left untouched; "
              "its projects are not routed by this install until registered again.")
    if not args.apply:
        print("Nothing written. Re-run with --apply to install.")
        return 0

    # ---- apply
    created_dirs = set(old_manifest.get("dirs_created", []))

    def makedirs(path):
        missing = []
        while path and not os.path.isdir(path):
            missing.append(path)
            path = posix(os.path.dirname(path))
        for d in reversed(missing):
            os.mkdir(d)
            created_dirs.add(d)

    for r in retire:
        makedirs(posix(os.path.dirname(r["backup"])))
        shutil.move(r["original"], r["backup"])

    makedirs(namespace)
    backup_path = f"{namespace}/backups/settings.json.pre-install"
    if settings_preexisted and not os.path.isfile(backup_path) and os.path.isfile(settings_path):
        makedirs(posix(os.path.dirname(backup_path)))
        shutil.copyfile(settings_path, backup_path)

    files_record = {}
    for dest, item in plan.files.items():
        if item["policy"] == "keep" and os.path.isfile(dest):
            if dest in old_files:
                files_record[dest] = old_files[dest]
            continue  # never overwritten; adopted only if this install created it
        makedirs(posix(os.path.dirname(dest)))
        with open(dest, "wb") as f:
            f.write(item["data"])
        files_record[dest] = {"sha256": sha256(item["data"]), "policy": item["policy"], "kind": item["kind"],
                              "source_sha256": item["source_sha256"], "translation": item["translation"]}
    for dest in stale:
        os.remove(dest)

    if not os.path.isfile(registry_path):
        with open(registry_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("{}\n")

    index_path = cfg["skills_index"]
    skill_index.write_index(cfg["skills_dir"], f"{args.prefix}-*", index_path)
    with open(index_path, "rb") as f:
        files_record[posix(index_path)] = {"sha256": sha256(f.read()), "policy": "replace", "kind": "generated"}

    if settings_changed or not os.path.isfile(settings_path):
        makedirs(config_dir)
        with open(settings_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(settings, indent=2) + "\n")

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "prefix": args.prefix,
        "installed_at": today,
        "framework_commit": cfg["framework_commit"],
        "config_dir": config_dir,
        "namespace_dir": namespace,
        "files": dict(sorted(files_record.items())),
        "dirs_created": sorted(created_dirs, key=lambda d: (-d.count("/"), d)),
        "settings": dict(record, path=settings_path, preexisted=bool(settings_preexisted),
                         backup=backup_path if settings_preexisted else None),
        "registry": {"path": registry_path, "created": bool(registry_created)},
        "retired": old_manifest.get("retired", []) + retire,
    }
    with open(manifest_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(manifest, indent=2) + "\n")

    print(f"Installed. Commands: /{args.prefix}-spec, /{args.prefix}-quick, ... — "
          f"uninstall with: {cfg['python']} \"{cfg['scripts_dir']}/uninstall.py\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
