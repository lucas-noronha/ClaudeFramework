"""Shared helper for every hook that needs to know *which project* the
current session is about — see docs/decisions/0013-multi-project-ai-repo.md,
docs/decisions/0014-setup-framework-adoption-modes.md and
docs/decisions/0015-unified-docs-tree-and-layered-constitution.md. Not a
hook entry point itself, not wired in settings.json directly — imported
by the hooks that are, the same pattern _pipeline_metrics.py already
establishes for shared non-hook code.

One shared `.claude/` can back several target repos, so a hook can no
longer assume CLAUDE_PROJECT_DIR is where its project's documentation,
CLAUDE.md and per-project state live. A two-step lookup supplies that:

  1. `projects.local.json` (per-machine, gitignored) maps this machine's
     absolute CLAUDE_PROJECT_DIR -> that project's subtree.
  2. `<subtree>/project-config.json` (committed) holds that project's
     shared values (build/test command, language split).

Since ADR 0015 that subtree is `<ai-repo>/docs/<project-name>/` (or
`~/.claude/docs/<project-name>/` in mode C) — a folder *inside* the one
shared `docs/` tree, which also holds the cross-project material at its
root (`constitution.md`, `workflow/`, `glossary.md`, the product
templates). No path segment is hardcoded here, so that move changed only
the *values* in the registry, not this module: `PROJECTS_ROOT_KEY` is a
JSON key name, never a folder name, and `resolve_project_root()` returns
whatever absolute path the registry hands it.

Resolved: several *callers* used to hardcode a `docs/` level inside that
returned root (e.g. `os.path.join(resolve_project_root(p), "docs",
"product", "specs")`, and `project_relative_path()` results matched
against a `docs/...` prefix). That was right for ADR 0013's
`projects/<name>/docs/` subtree; under ADR 0015 a project's own folders
sit directly in the subtree (`<subtree>/product/specs/`,
`<subtree>/decisions/`) with no second `docs/` level — except in mode A,
where `resolve_project_root()` returns `CLAUDE_PROJECT_DIR` unchanged and
that real project repo's own `docs/` folder genuinely does sit at its
root, so the extra `docs/` level is still correct there.

Those two shapes can't be told apart by pattern-matching the returned
root's value (it's opaque, per above) — the only reliable signal is
whether it changed at all, i.e. `resolve_project_root(p) == p` means
unrouted (mode A, keep the `docs/` level) and anything else means routed
(mode B/C, drop it). `state_file_path()` below already used exactly that
comparison internally; `resolve_docs_root()` now exposes the same
comparison as a small helper so every other caller building a path to a
project's own `product/`, `architecture/` or `decisions/` folder doesn't
have to re-derive it by hand. Callers fixed to use it: `adr_backlink.py`,
`claude_md_index_check.py`, `context_budget_check.py`,
`decision_index.py`, `frontmatter_check.py`, `session_brief.py`,
`spec_index.py`, `spec_number_guard.py`. Callers that matched
`project_relative_path()`'s result against a hardcoded `docs/...` prefix
(`adr_backlink.py`, `adr_immutability_guard.py`, `decision_index.py`,
`pipeline_metrics.py`, `spec_index.py`, `spec_number_guard.py`,
`spec_status_sync.py`) were changed to compare the tool-reported path's
own directory directly against `resolve_docs_root()`-derived
`specs_dir`/`decisions_dir` instead — sidestepping the prefix ambiguity
entirely rather than trying to compute which prefix shape applies.

Every read here fails open: no registry file, no entry for this project,
or an unparseable one all degrade to today's single-repo behaviour
rather than raising inside a hook. That fallback is what keeps classic
(mode A) setups working with zero behaviour change — with no registry on
disk at all, `resolve_project_root` hands back exactly what it was
given.

**One exception, user-level installs (ADR 0017).** Under mode C the
fallback above is exactly the bug: a hook loaded from `~/.claude` for a
repo nobody registered would treat it as mode A and write
`<repo>/.claude/...` or `docs/*/README.md` into it. A user-level install
is recognized by the `framework.json` the installer writes beside the
hooks folder (`install_mode: user-level`), and `hook_should_run()` then
answers False for any unregistered `CLAUDE_PROJECT_DIR`. Every hook asks
it first, so in a user-level install an unregistered repo gets zero
footprint, and mode A/B behaviour is untouched (no `framework.json`,
gate always open).

`framework.json` is also the single config source ADR 0017 asks for: the
registry, the shared `docs/` root, the projects root and the template
locations are all recorded there at install time, and nothing below
infers them from folder shape when it exists.

Run as a script (`python _project_paths.py describe`), this module
prints that whole resolution as JSON. The `project-registration` skill
calls it, so a command and a hook can never disagree about which project
a session belongs to.
"""
import json
import os
import subprocess
import sys

REGISTRY_FILENAME = "projects.local.json"
CONFIG_FILENAME = "project-config.json"
FRAMEWORK_CONFIG_FILENAME = "framework.json"
PROJECTS_ROOT_KEY = "projects_root"
USER_LEVEL_MODE = "user-level"


def framework_home() -> str:
    """The folder holding `hooks/` — `<repo>/.claude` in modes A/B, the
    install namespace (e.g. `~/.claude/cfw`) in a user-level install.
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def framework_config() -> dict:
    """`framework.json` beside `hooks/`, written by the user-level
    installer (ADR 0017). `{}` in modes A/B, where nothing writes it.
    """
    try:
        with open(os.path.join(framework_home(), FRAMEWORK_CONFIG_FILENAME), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def is_user_level_install() -> bool:
    return framework_config().get("install_mode") == USER_LEVEL_MODE


def read_hook_input() -> dict:
    """The hook's stdin JSON, decoded as UTF-8 — what Claude Code sends.

    Not `json.load(sys.stdin)`: on Windows `sys.stdin` decodes with the
    ANSI code page (cp1252), so a non-ASCII path such as
    `C:\\Users\\x\\OneDrive\\Área de Trabalho\\...` arrives mangled, and
    every path comparison a hook makes silently fails (verified
    2026-10-03 against real hook input). `{}` on empty or invalid input,
    so a hook degrades to a no-op instead of crashing.
    """
    try:
        raw = sys.stdin.buffer.read()
    except (AttributeError, OSError):
        return {}
    try:
        data = json.loads(raw.decode("utf-8-sig") or "{}")
    except (UnicodeDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def normalize(path: str) -> str:
    """Forward slashes, no trailing slash — the comparison form every
    directory-scoped hook here already uses (see `.claude/README.md`,
    "Why a Write/Edit to the wrong directory doesn't silently misfire").
    Windows mixes `\\` and `/` freely, so raw string equality between two
    paths is never safe.
    """
    return path.replace("\\", "/").rstrip("/")


def _registry_candidates(project_dir: str):
    """Where `projects.local.json` can live, most specific first.

    Mode B (external AI-repo) reaches it through the target repo's own
    `.claude` link, so `<project_dir>/.claude/` finds it. Mode C has no
    links at all — the machinery sits in `~/.claude`, so the registry
    sits beside *this file's own* `.claude/`, which is also what the
    explicit `~/.claude` fallback covers. Mode A matches none of them and
    falls through to unrouted behaviour.
    """
    configured = framework_config().get("registry")
    if isinstance(configured, str) and configured:
        # A user-level install names its registry explicitly — nothing to
        # infer, and no other location may answer for it (ADR 0017).
        return [configured]

    candidates = [
        os.path.join(project_dir, ".claude", REGISTRY_FILENAME),
        os.path.join(framework_home(), REGISTRY_FILENAME),
        os.path.expanduser(os.path.join("~", ".claude", REGISTRY_FILENAME)),
    ]

    seen = set()
    unique = []
    for candidate in candidates:
        key = normalize(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _find_registry(project_dir: str):
    """`(path, data)` of the first registry that exists and parses, or
    `(None, {})`.
    """
    for path in _registry_candidates(project_dir):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue  # missing or malformed — try the next location
        if isinstance(data, dict):
            return path, data
    return None, {}


def _read_registry(project_dir: str) -> dict:
    return _find_registry(project_dir)[1]


def _registered_subtree(project_dir: str):
    """This project's subtree from the registry, or None when it has no
    entry (mode A, or an unregistered repo under a user-level install).
    """
    registry = _read_registry(project_dir)
    if not registry:
        return None

    routes = {
        normalize(key): value
        for key, value in registry.items()
        if key != PROJECTS_ROOT_KEY and isinstance(value, str) and value
    }

    # The raw value first (what every entry is keyed by), then its
    # absolute form, for a caller that was handed `.` or a relative path.
    wanted = [normalize(project_dir), normalize(os.path.abspath(project_dir or "."))]
    for candidate in wanted:
        if candidate in routes:
            return normalize(routes[candidate])

    # Windows paths are case-insensitive, so a registry entry written
    # with a differently-cased drive letter is still the same project.
    if os.name == "nt":
        lowered = {key.lower(): value for key, value in routes.items()}
        for candidate in wanted:
            if candidate.lower() in lowered:
                return normalize(lowered[candidate.lower()])
    return None


def is_registered(project_dir: str) -> bool:
    return _registered_subtree(project_dir) is not None


def hook_should_run(project_dir: str) -> bool:
    """The registration gate every hook calls first (ADR 0017, spec 0001
    FR-03). Always True outside a user-level install, so modes A and B
    behave exactly as before. Under a user-level install, True only for a
    registered `CLAUDE_PROJECT_DIR`: an unregistered repo must never see
    a mode-A fallback write, a blocked tool call or a build run.
    """
    if not is_user_level_install():
        return True
    return is_registered(project_dir)


def resolve_project_root(project_dir: str) -> str:
    """This session's project subtree — the folder holding its
    `CLAUDE.md`, `project-config.json`, its optional own
    `constitution.md` and its documentation folders (`product/`,
    `architecture/`, `decisions/`). Since ADR 0015 that folder is
    `docs/<project-name>/` under the AI-repo's shared `docs/` root, but
    nothing here depends on that: the value is opaque, whatever absolute
    path the registry recorded.

    Returns `project_dir` unchanged when there is no registry or no entry
    for it, which is exactly classic mode's behaviour today.
    """
    subtree = _registered_subtree(project_dir)
    return subtree if subtree is not None else project_dir


def resolve_docs_root(project_dir: str) -> str:
    """The folder that directly holds this project's own `product/`,
    `architecture/` and `decisions/` folders — i.e. what a caller should
    join `"product/specs"` or `"decisions"` onto, in every mode, with no
    extra `docs/` segment to reason about.

    Mode A (no registry entry — `resolve_project_root()` hands back
    `project_dir` unchanged): a real project repo's own `docs/` folder
    sits at its root, so this returns `<project_dir>/docs`.

    Mode B/C (routed): `resolve_project_root()` already returns
    `docs/<project-name>/` inside the shared tree (ADR 0015), and that
    folder's own `product/`, `architecture/`, `decisions/` sit directly
    inside it — no second `docs/` level — so this returns that root
    unchanged.
    """
    root = resolve_project_root(project_dir)
    if root == project_dir:
        return os.path.join(project_dir, "docs")
    return root


def _real(path: str) -> str:
    try:
        return os.path.realpath(path)
    except (OSError, ValueError):
        return path


def _dedup(paths):
    seen = set()
    unique = []
    for path in paths:
        key = normalize(path)
        if os.name == "nt":
            key = key.lower()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def _relative_within(root: str, target: str):
    """`target` expressed relative to `root`, or None if it isn't inside
    it. `os.path.relpath` (not string prefixing) so `..`, mixed separators
    and Windows' case-insensitivity are all handled by the stdlib.
    """
    try:
        rel = normalize(os.path.relpath(target, root))
    except ValueError:
        return None  # different drives on Windows — never inside
    if rel == ".." or rel.startswith("../") or os.path.isabs(rel):
        return None
    return rel


def project_relative_path(project_dir: str, path: str):
    """A tool's reported `file_path`, expressed relative to whichever root
    owns this session's documentation — e.g. `"docs/decisions/0001-x.md"`
    against `CLAUDE_PROJECT_DIR` in mode A — or None when it is under no
    such root. What that string looks like depends on which root matched,
    so a caller comparing it against a literal `docs/...` prefix should
    read the open item in this module's own docstring first.

    A hook can't assume which shape `file_path` arrives in. Mode A writes
    a relative `docs/...` path (resolved against `CLAUDE_PROJECT_DIR`);
    modes B and C name the project subtree's *absolute* path instead (see
    `.claude/skills/project-registration/SKILL.md`) — mode C because it
    has no link to redirect a relative path, and mode B because since ADR
    0015 its `docs` link points at the **shared** root, where a relative
    project-content path would land in shared material rather than in
    this project's subtree. Prefix-matching the raw string can only ever
    get one of those shapes right, which is how a directory-scoped hook
    goes silently dark.

    Two roots are tried, most specific first: the routed project subtree
    (mode B/C) and `CLAUDE_PROJECT_DIR` itself (mode A — and mode B again,
    for *shared* material read through the target repo's own `docs` link,
    which sits under `CLAUDE_PROJECT_DIR` while the tree that link points
    into is somewhere else entirely). Each root's `realpath` is tried too,
    covering the case where one side of such a link is already resolved
    and the other isn't.
    """
    if not path:
        return None

    abspath = path if os.path.isabs(path) else os.path.join(project_dir, path)
    targets = _dedup([abspath, _real(abspath)])

    roots = []
    for root in (resolve_project_root(project_dir), project_dir):
        roots.extend([root, _real(root)])

    for root in _dedup(roots):
        for target in targets:
            rel = _relative_within(root, target)
            if rel is not None:
                return rel
    return None


def read_project_config(project_root: str) -> dict:
    """The project's committed `project-config.json` (build/test command,
    language split). `{}` on a missing file or any parse error.
    """
    try:
        with open(os.path.join(project_root, CONFIG_FILENAME), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def get_projects_root(project_dir: str):
    """The machine-wide folder under which registered projects' subtrees
    are created (mode C, chosen once at setup). `None` when unset.

    The key is `projects_root` — a JSON key name, not a folder name. Its
    *value* defaults to the shared `docs/` root since ADR 0015
    (`<ai-repo>/docs` in mode B, `~/.claude/docs` in mode C), so a
    subtree lands at `docs/<project-name>/`; it stays overridable to any
    folder, for ADR 0014's unchanged reasons.

    A user-level install records it in `framework.json` (ADR 0017's one
    config source), which wins; the registry key is the pre-0017 home and
    stays readable so an older install keeps working.
    """
    configured = framework_config().get(PROJECTS_ROOT_KEY)
    if isinstance(configured, str) and configured:
        return normalize(configured)
    value = _read_registry(project_dir).get(PROJECTS_ROOT_KEY)
    return normalize(value) if isinstance(value, str) and value else None


def resolve_shared_docs_root(project_dir: str):
    """The shared `docs/` root — constitution layers, `workflow/`,
    `glossary.md`, the `product/` templates and the framework's own
    reference ADRs (ADR 0015).

    - A user-level install names it in `framework.json` (no inference).
    - Unrouted (mode A): the repo's own `docs/`, which is both shared and
      project material there.
    - Routed without `framework.json` (mode B, or a pre-0017 mode C):
      `docs/` beside the `.claude/` that holds the registry, else `docs/`
      inside it (old `~/.claude/docs`), else the subtree's parent.

    Returns None only when nothing on disk matches.
    """
    configured = framework_config().get("shared_docs_root")
    if isinstance(configured, str) and configured:
        return normalize(configured)

    subtree = _registered_subtree(project_dir)
    if subtree is None:
        return normalize(os.path.join(project_dir, "docs"))

    registry_path, _ = _find_registry(project_dir)
    candidates = []
    if registry_path:
        registry_dir = os.path.dirname(registry_path)
        candidates += [
            os.path.join(os.path.dirname(registry_dir), "docs"),
            os.path.join(registry_dir, "docs"),
        ]
    candidates.append(os.path.dirname(subtree))
    for candidate in candidates:
        if os.path.isfile(os.path.join(candidate, "constitution.md")) or os.path.isdir(os.path.join(candidate, "workflow")):
            return normalize(candidate)
    return None


def load_project_config(project_dir: str) -> dict:
    """This project's config in every mode: `<subtree>/project-config.json`
    when routed, else the optional mode A file
    `<repo>/.claude/project-config.json` (ADR 0020 — census, review
    policy, routing-key names and the build/test command need a
    machine-readable home in mode A too). `{}` when neither exists, which
    every caller treats as "framework defaults".
    """
    subtree = _registered_subtree(project_dir)
    if subtree is not None:
        return read_project_config(subtree)
    return read_project_config(os.path.join(project_dir, ".claude"))


def project_config_path(project_dir: str) -> str:
    subtree = _registered_subtree(project_dir)
    base = subtree if subtree is not None else os.path.join(project_dir, ".claude")
    return os.path.join(base, CONFIG_FILENAME)


def detect_main_branch(repo_dir: str):
    """`origin/HEAD`'s branch name, else the checked-out branch, else
    None. Read-only git; used at registration time and as the runtime
    fallback when `main_integration_branch` isn't configured (spec 0001
    FR-06).
    """
    for args in (
        ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
    ):
        try:
            result = subprocess.run(args, cwd=repo_dir, capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            return None
        value = result.stdout.strip()
        if result.returncode == 0 and value and value != "HEAD":
            return value.split("/", 1)[1] if value.startswith("origin/") else value
    return None


def main_integration_branch(project_dir: str):
    configured = load_project_config(project_dir).get("main_integration_branch")
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    return detect_main_branch(project_dir)


def state_file_path(project_dir: str, filename: str) -> str:
    """Where a per-project *state* file (session handoff, metrics log,
    dismiss list) belongs for this session.

    Routed (mode B/C): in the project's own subtree, beside its
    `CLAUDE.md` — i.e. `docs/<project-name>/session-handoff.md` under ADR
    0015's unified tree — so two target repos sharing one `.claude/` stop
    writing the same physical file (ADR 0013). That does put operational
    state inside a `docs/` tree, which ADR 0015 accepted explicitly; the
    `.gitignore` patterns for these files follow the same `docs/*/` shape.

    Unrouted (classic mode A, no registry at all): exactly where it lives
    today, under `<project>/.claude/`. Resolving to the repo root instead
    would drop per-machine operational state into the target repo's own
    root — a behaviour change, and a `.gitignore` break, that classic
    mode never asked for.
    """
    root = resolve_project_root(project_dir)
    if root == project_dir:
        return os.path.join(project_dir, ".claude", filename)
    return os.path.join(root, filename)


def describe(project_dir: str) -> dict:
    """Everything a pipeline command needs to rebind its paths, resolved
    the same way the hooks resolve it. Printed by `python
    _project_paths.py describe` — the `project-registration` skill's
    single probe.
    """
    config = framework_config()
    subtree = _registered_subtree(project_dir)
    registry_path, _ = _find_registry(project_dir)
    docs_reachable = os.path.isdir(os.path.join(project_dir, "docs"))

    if subtree is not None:
        mode = "C" if config.get("install_mode") == USER_LEVEL_MODE or not docs_reachable else "B"
    elif config.get("install_mode") == USER_LEVEL_MODE:
        mode = "C-unregistered"
    elif docs_reachable:
        mode = "A"
    elif registry_path:
        mode = "C-unregistered"
    else:
        mode = "unconfigured"

    template = config.get("claude_md_template")
    if not template:
        for candidate in (
            os.path.join(os.path.dirname(framework_home()), "CLAUDE.md.template"),
            os.path.join(framework_home(), "CLAUDE.md.template"),
        ):
            if os.path.isfile(candidate):
                template = normalize(candidate)
                break

    return {
        "mode": mode,
        "project_dir": normalize(project_dir),
        "registered": subtree is not None,
        "subtree": subtree,
        "docs_root": normalize(resolve_docs_root(project_dir)),
        "shared_docs_root": resolve_shared_docs_root(project_dir),
        "projects_root": get_projects_root(project_dir),
        "registry": normalize(registry_path) if registry_path else config.get("registry"),
        "claude_md_template": template,
        "framework_home": normalize(framework_home()),
        "hooks_dir": normalize(os.path.dirname(os.path.abspath(__file__))),
        "scripts_dir": normalize(os.path.join(framework_home(), "scripts")),
        "install": {key: config[key] for key in ("install_mode", "prefix") if key in config},
        "project_config": load_project_config(project_dir),
        "main_integration_branch": main_integration_branch(project_dir) if subtree is not None or mode == "A" else None,
    }


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "describe":
        target = sys.argv[2] if len(sys.argv) >= 3 else os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
        print(json.dumps(describe(target), indent=2))
        sys.exit(0)
    print("usage: python _project_paths.py describe [project_dir]", file=sys.stderr)
    sys.exit(2)
