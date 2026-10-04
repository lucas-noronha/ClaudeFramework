"""PreToolUse guard: block Write of a new spec (a legacy `NNNN-name.md` file
or a new `NNNN-name/` folder) whose NNNN prefix collides with a different,
already-existing spec in any layout — legacy file, folder or lite folder
(framework ADR 0024 section 3). Guards against two specs getting the same
number (e.g. from parallel sessions/worktrees). Writing a file inside an
existing spec folder (plan, tasks, reconciliation, notes) is not a new spec
and is never denied.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _project_paths import hook_should_run, normalize, read_hook_input, specs_dir as resolve_specs_dir  # noqa: E402
import _spec_layout  # noqa: E402


def _entry_stem(name: str) -> str:
    return name[:-3] if name.endswith(".md") else name


def _deny(num: str, other: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"Spec number {num} is already used by {other} — "
                "pick the next available number."
            ),
        }
    }))


def main() -> None:
    # Registration gate (framework ADR 0017): a no-op for an unregistered repo under
    # a user-level install; always open in modes A/B.
    if not hook_should_run(os.environ.get("CLAUDE_PROJECT_DIR", ".")):
        return

    data = read_hook_input()
    path = data.get("tool_input", {}).get("file_path", "")
    if not path:
        return

    project = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    abspath = path if os.path.isabs(path) else os.path.join(project, path)
    specs_dir = resolve_specs_dir(project)

    # Self-gating: this hook fires on every Write/Edit in the multi-project
    # settings variant, so it decides relevance itself rather than trusting
    # a literal-prefix `if` condition — it compares the tool-reported
    # path's own directory against the resolved specs_dir directly instead,
    # which works regardless of which of the two path shapes a tool call
    # reports (see resolve_docs_root in _project_paths.py).
    parent = normalize(os.path.dirname(abspath))
    root = normalize(specs_dir)
    base = os.path.basename(abspath)

    if parent == root:
        # Legacy-layout file directly in the specs folder.
        match = re.match(r"^(\d{4})-.+\.md$", base)
        if not match or ".validation-" in base:
            return
        entry = _entry_stem(base)
    elif normalize(os.path.dirname(parent)) == root:
        # A file inside a `NNNN-name/` folder: only a *new* folder is a new spec.
        folder = os.path.basename(parent)
        match = re.match(r"^(\d{4})-.+", folder)
        if not match or not base.endswith(".md") or ".validation-" in base:
            return
        if os.path.isdir(parent):
            return
        entry = folder
    else:
        return

    num = match.group(1)
    for ref in _spec_layout.iter_specs(specs_dir):
        other = os.path.basename(ref["folder"] or ref["spec_file"] or "")
        if not other or ".validation-" in other or _entry_stem(other) == entry:
            continue
        if ref["number"] == num:
            _deny(num, other)
            return


if __name__ == "__main__":
    main()
