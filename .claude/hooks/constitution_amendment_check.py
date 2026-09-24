"""PostToolUse: nudge (never block) when docs/constitution.md changes
without its `version`/`last_amended` frontmatter moving in the same
change. Mirrors context_budget_check.py/frontmatter_check.py's posture
(warn, don't gate) rather than adr_immutability_guard.py's hard block —
a constitution is meant to be amended over the project's life (see its
own Governance section), so blocking edits would fight legitimate ones;
only silent, unversioned drift is worth flagging.
"""
import json
import os
import re
import subprocess
import sys


def read_version(text: str):
    fm_match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    frontmatter = fm_match.group(1) if fm_match else ""
    match = re.search(r"^version:\s*(\S+)", frontmatter, re.MULTILINE)
    return match.group(1) if match else None


def main() -> None:
    data = json.load(sys.stdin)
    path = data.get("tool_input", {}).get("file_path", "") or data.get("tool_response", {}).get("filePath", "")
    if not path:
        return

    project = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    abspath = path if os.path.isabs(path) else os.path.join(project, path)
    normalized = abspath.replace("\\", "/")

    if not normalized.endswith("docs/constitution.md"):
        return

    try:
        with open(abspath, encoding="utf-8") as f:
            current_content = f.read()
    except FileNotFoundError:
        return

    current_version = read_version(current_content)
    if not current_version:
        print(json.dumps({
            "systemMessage": "docs/constitution.md has no `version` in its frontmatter — add one (see its own Governance section).",
        }))
        return

    try:
        result = subprocess.run(
            ["git", "show", "HEAD:docs/constitution.md"],
            cwd=project, capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return  # git unavailable — nothing to compare against, fail open
    if result.returncode != 0:
        return  # not committed yet, or no git repo — nothing to compare against

    previous_content = result.stdout
    if previous_content == current_content:
        return  # no actual change since last commit

    previous_version = read_version(previous_content)
    if previous_version and previous_version == current_version:
        print(json.dumps({
            "systemMessage": (
                f"docs/constitution.md changed but `version` is still {current_version} — "
                "amendments must bump version/last_amended in the same change "
                "(see the file's own Governance section)."
            ),
        }))


if __name__ == "__main__":
    main()
