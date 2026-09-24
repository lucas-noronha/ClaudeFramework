"""PreToolUse guard: block Edit on an ADR whose frontmatter status is
`accepted`. Enforces the "ADRs are immutable once accepted" convention
(CLAUDE.md rule 2 in the template) — supersede instead of editing in
place.
"""
import json
import os
import re
import sys


def main() -> None:
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input", {})
    path = tool_input.get("file_path", "")

    project = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    abspath = path if os.path.isabs(path) else os.path.join(project, path)
    normalized = abspath.replace("\\", "/")

    if "docs/decisions/" not in normalized or not normalized.endswith(".md"):
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
