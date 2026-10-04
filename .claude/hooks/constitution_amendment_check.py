"""PostToolUse: nudge (never block) when a constitution changes without
its `version`/`last_amended` frontmatter moving in the same change.
Mirrors context_budget_check.py/frontmatter_check.py's posture (warn,
don't gate) rather than adr_immutability_guard.py's hard block — a
constitution is meant to be amended over the project's life (see its
own Governance section), so blocking edits would fight legitimate ones;
only silent, unversioned drift is worth flagging.

Since framework ADR 0015 there are two layers, and this hook watches both
*independently* — one nudge about whichever file was actually touched:

    <root>/docs/constitution.md                  supreme, cross-project
    <root>/docs/<project-name>/constitution.md   that project's additions

`<root>` is the same place for both (the AI-repo root in mode B, or
`~/.claude` in mode C, which typically isn't a git repo at all — that
case fails open below): project constitutions do not live in a git repo
of their own. Mode A has only the supreme file, at
`<repo>/docs/constitution.md`, and behaves here exactly as it did before
framework ADR 0015.

framework ADR 0018 adds a framework-owned baseline layer above both,
`<root>/docs/constitution-baseline.md` (Principles I-V). It is replaced
on every framework upgrade, so any edit to it gets a "you're editing the
framework's layer" nudge instead of the version check.

Whether a project principle actually *weakens* a supreme one stays a
semantic judgment `/spec`, `/plan`, `coder`/`quickfix` and `reviewer`
make while reading both files (framework ADR 0015 deliberately did not strengthen
enforcement here). This hook attempts no contradiction detection — it
only watches for unversioned drift, exactly as framework ADR 0007 specified.
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _project_paths import hook_should_run, normalize, read_hook_input  # noqa: E402

CONSTITUTION_FILENAME = "constitution.md"
# framework ADR 0018: the framework's own Principles I-V, a third layer above the
# two framework ADR 0015 introduced. Framework-owned: replaced on every upgrade.
BASELINE_FILENAME = "constitution-baseline.md"
DOCS_DIRNAME = "docs"

# Shared material sits at the `docs/` root beside the project folders
# (framework ADR 0015), so these names can never be a project name — registration
# reserves them. `docs/decisions/constitution.md` is therefore some other
# file that happens to be named that, not a project's constitution.
RESERVED_DOCS_NAMES = {"workflow", "product", "architecture", "decisions", "glossary"}


def read_version(text: str):
    fm_match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    frontmatter = fm_match.group(1) if fm_match else ""
    match = re.search(r"^version:\s*(\S+)", frontmatter, re.MULTILINE)
    return match.group(1) if match else None


def constitution_target(abspath: str):
    """`(owner_dir, path_relative_to_owner)` for a touched constitution,
    or `None` when this path is not one.

    `owner_dir` is the directory that *holds* the `docs/` tree — the repo
    root in mode A, the AI-repo/`~/.claude` root in modes B/C — and the
    relative path is that constitution's committed path inside it, which
    is what `git show HEAD:<path>` needs. Deriving both from the touched
    path's own shape (rather than blindly taking its grandparent) is what
    makes the two layers land on their own committed copy instead of on
    each other's.

    Nothing here routes through `resolve_project_root()`: this check has
    to work for the *shared* file too, which sits one level **above** any
    project subtree, so a subtree-relative lookup
    (`project_relative_path()`, what the per-project state-file hooks
    use) would report `None` for it. The trailing components are exact
    enough, and identical in every mode.
    """
    parts = normalize(abspath).split("/")
    if len(parts) < 3 or parts[-1] not in (CONSTITUTION_FILENAME, BASELINE_FILENAME):
        return None

    if parts[-1] == BASELINE_FILENAME:
        # Only ever at a docs root — a project subtree has no baseline.
        if parts[-2] != DOCS_DIRNAME:
            return None
        depth = 2
    elif parts[-2] == DOCS_DIRNAME:
        depth = 2  # supreme: .../docs/constitution.md
    elif len(parts) >= 4 and parts[-3] == DOCS_DIRNAME and parts[-2] not in RESERVED_DOCS_NAMES:
        depth = 3  # project: .../docs/<project-name>/constitution.md
    else:
        return None

    owner = abspath
    for _ in range(depth):
        owner = os.path.dirname(owner)
    return owner, "/".join(parts[-depth:])


def _committed_copy(abspath: str):
    """The `HEAD` copy of this constitution, or `None` when there's
    nothing to compare against (no git, not committed, no repo).

    The path is tried as reported *and* as `realpath` resolves it: in
    mode B the constitution is reached through the target repo's own
    `docs` link, so the reported path's owner is that repo — which has no
    such file committed — while the resolved one is the AI-repo that
    does. Same two-candidate discipline `_project_paths.py` already
    applies for link-crossed paths. When the two are the same string
    (mode A, always) only one candidate is tried and the behaviour is
    byte-for-byte what it was before.
    """
    candidates = [abspath]
    try:
        resolved = os.path.realpath(abspath)
    except (OSError, ValueError):
        resolved = abspath
    if normalize(resolved) != normalize(abspath):
        candidates.append(resolved)

    for candidate in candidates:
        target = constitution_target(candidate)
        if target is None:
            continue
        owner, relative = target
        try:
            result = subprocess.run(
                ["git", "show", f"HEAD:{relative}"],
                cwd=owner, capture_output=True, text=True, timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            continue  # git unavailable — nothing to compare against, fail open
        if result.returncode == 0:
            return result.stdout
    return None  # not committed yet, or no git repo — nothing to compare against


def main() -> None:
    # Registration gate (framework ADR 0017): a no-op for an unregistered repo under
    # a user-level install; always open in modes A/B.
    if not hook_should_run(os.environ.get("CLAUDE_PROJECT_DIR", ".")):
        return

    data = read_hook_input()
    path = data.get("tool_input", {}).get("file_path", "") or data.get("tool_response", {}).get("filePath", "")
    if not path:
        return

    project = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    abspath = path if os.path.isabs(path) else os.path.join(project, path)

    # Self-gating: this hook fires on every Write/Edit in the multi-project
    # settings variant, so it decides relevance itself rather than trusting
    # a literal-prefix `if` condition that only ever matches one of the two
    # path shapes a tool call can report (relative in modes A/B, the
    # resolved absolute path in mode C, where no link redirects a relative
    # one).
    target = constitution_target(abspath)
    if target is None:
        return
    relative = target[1]

    try:
        with open(abspath, encoding="utf-8") as f:
            current_content = f.read()
    except FileNotFoundError:
        return

    if os.path.basename(abspath) == BASELINE_FILENAME:
        # framework ADR 0018: a hand edit here is lost on the next framework upgrade.
        # Still nudge-only — the framework repo itself edits this file
        # legitimately, and a hook can't tell the two apart.
        print(json.dumps({
            "systemMessage": (
                f"{relative} is the framework-owned baseline layer — a framework "
                "upgrade replaces it. In an adopted project, amend constitution.md "
                "beside it instead; edit this file only in the framework repository, "
                "bumping its version."
            ),
        }))
        return

    current_version = read_version(current_content)
    if not current_version:
        print(json.dumps({
            "systemMessage": f"{relative} has no `version` in its frontmatter — add one (see its own Governance section).",
        }))
        return

    previous_content = _committed_copy(abspath)
    if previous_content is None:
        return
    if previous_content == current_content:
        return  # no actual change since last commit

    previous_version = read_version(previous_content)
    if previous_version and previous_version == current_version:
        print(json.dumps({
            "systemMessage": (
                f"{relative} changed but `version` is still {current_version} — "
                "amendments must bump version/last_amended in the same change "
                "(see the file's own Governance section)."
            ),
        }))


if __name__ == "__main__":
    main()
