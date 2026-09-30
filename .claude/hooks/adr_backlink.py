"""PostToolUse: when a newly-written ADR declares `supersedes: NNNN`,
backlink the old ADR's `superseded_by: null` to point at the new one.
Writes the filesystem directly (not through the Edit tool), so it
never interacts with the ADR immutability guard.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _project_paths import normalize, resolve_docs_root  # noqa: E402


def main() -> None:
    data = json.load(sys.stdin)
    path = data.get("tool_input", {}).get("file_path", "") or data.get("tool_response", {}).get("filePath", "")
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
    if normalize(os.path.dirname(abspath)) != normalize(decisions_dir):
        return

    try:
        with open(abspath, encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return

    supersedes_match = re.search(r"^supersedes:\s*(\S+)", content, re.MULTILINE)
    if not supersedes_match or supersedes_match.group(1) in ("null", "~", ""):
        return

    old_id = supersedes_match.group(1)
    id_match = re.search(r"^id:\s*(\d{4})", content, re.MULTILINE)
    if not id_match:
        return
    new_id = id_match.group(1)

    candidates = [
        p for p in glob.glob(os.path.join(decisions_dir, f"{old_id}-*.md"))
        if os.path.basename(p) != os.path.basename(abspath)
    ]
    if not candidates:
        return
    old_path = candidates[0]

    with open(old_path, encoding="utf-8") as f:
        old_content = f.read()

    if "superseded_by: null" not in old_content:
        return  # already linked, or unexpected format — leave it alone

    updated = old_content.replace("superseded_by: null", f"superseded_by: {new_id}", 1)
    with open(old_path, "w", encoding="utf-8") as f:
        f.write(updated)

    print(json.dumps({
        "systemMessage": f"ADR {old_id} backlinked: superseded_by: {new_id}",
    }))


if __name__ == "__main__":
    main()
