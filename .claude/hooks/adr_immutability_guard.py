"""PreToolUse guard: block Edit on an ADR whose frontmatter status is
`accepted`. Enforces the "ADRs are immutable once accepted" convention
(CLAUDE.md rule 2 in the template) — supersede instead of editing in
place.
"""
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
    tool_input = data.get("tool_input", {})
    path = tool_input.get("file_path", "")
    if not path:
        return

    project = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    abspath = path if os.path.isabs(path) else os.path.join(project, path)
    decisions_dir = os.path.join(resolve_docs_root(project), "decisions")

    # Self-gating: this hook fires on every Write/Edit in the multi-project
    # settings variant, so it decides relevance itself rather than trusting
    # a literal-prefix `if` condition — it compares the tool-reported
    # path's own directory against the resolved decisions_dir directly
    # instead, which works regardless of which of the two path shapes a
    # tool call reports (see resolve_docs_root in _project_paths.py).
    if normalize(os.path.dirname(abspath)) != normalize(decisions_dir) or not abspath.endswith(".md"):
        return

    try:
        with open(abspath, encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return

    match = re.search(r"^status:\s*(\S+)", content, re.MULTILINE)
    status = match.group(1) if match else ""

    if status != "accepted":
        return

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"{os.path.basename(abspath)} is status: accepted — ADRs are "
                "immutable once accepted (CLAUDE.md rule 2). Write a new ADR "
                "that supersedes this one instead of editing it in place."
            ),
        }
    }))


if __name__ == "__main__":
    main()
