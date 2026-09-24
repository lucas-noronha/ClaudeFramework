"""PreToolUse guard: block Write of a new spec file whose NNNN prefix
collides with a different, already-existing spec. Guards against two
specs getting the same number (e.g. from parallel sessions/worktrees).
"""
import glob
import json
import os
import re
import sys


def main() -> None:
    data = json.load(sys.stdin)
    path = data.get("tool_input", {}).get("file_path", "")

    project = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    abspath = path if os.path.isabs(path) else os.path.join(project, path)
    specs_dir = os.path.join(project, "docs", "product", "specs")

    normalized_dir = os.path.dirname(abspath).replace("\\", "/").rstrip("/")
    if normalized_dir != specs_dir.replace("\\", "/").rstrip("/"):
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
