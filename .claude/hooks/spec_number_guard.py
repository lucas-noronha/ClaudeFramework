"""PreToolUse guard: block Write of a new spec file whose NNNN prefix
collides with a different, already-existing spec. Guards against two
specs getting the same number (e.g. from parallel sessions/worktrees).
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _project_paths import hook_should_run, normalize, read_hook_input, resolve_docs_root  # noqa: E402


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
    specs_dir = os.path.join(resolve_docs_root(project), "product", "specs")

    # Self-gating: this hook fires on every Write/Edit in the multi-project
    # settings variant, so it decides relevance itself rather than trusting
    # a literal-prefix `if` condition — it compares the tool-reported
    # path's own directory against the resolved specs_dir directly instead,
    # which works regardless of which of the two path shapes a tool call
    # reports (see resolve_docs_root in _project_paths.py).
    if normalize(os.path.dirname(abspath)) != normalize(specs_dir):
        return

    base = os.path.basename(abspath)

    if ".validation-" in base:
        return

    match = re.match(r"^(\d{4})-.+\.md$", base)
    if not match:
        return

    num = match.group(1)
    for candidate in glob.glob(os.path.join(specs_dir, f"{num}-*.md")):
        cand_base = os.path.basename(candidate)
        if cand_base == base or ".validation-" in cand_base:
            continue
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"Spec number {num} is already used by {cand_base} — "
                    "pick the next available number."
                ),
            }
        }))
        return


if __name__ == "__main__":
    main()
