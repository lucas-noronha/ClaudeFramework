"""PostToolUse: nudge (never block) when a doc under docs/ is missing
the frontmatter keys the rest of this framework's tooling depends on
(`doc_type`, `status`, `context_budget`). Without these, a doc silently
falls outside the cost-aware indexing this framework relies on
(CLAUDE.md's index, context_budget_check.py, the "load the narrowest
doc" discipline) — better to flag it once than have it go unnoticed.
"""
import json
import os
import re
import sys

REQUIRED_KEYS = ["doc_type", "status", "context_budget"]


def main() -> None:
    data = json.load(sys.stdin)
    path = data.get("tool_input", {}).get("file_path", "") or data.get("tool_response", {}).get("filePath", "")
    if not path:
        return

    project = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    abspath = path if os.path.isabs(path) else os.path.join(project, path)
    docs_dir = os.path.join(project, "docs")

    normalized = abspath.replace("\\", "/")
    normalized_docs_dir = docs_dir.replace("\\", "/").rstrip("/")

    if not normalized.startswith(normalized_docs_dir + "/") or not normalized.endswith(".md"):
        return
    if os.path.basename(abspath) == "README.md":
        return  # auto-generated indexes, not authored docs

    try:
        with open(abspath, encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return

    fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    rel = os.path.relpath(abspath, project).replace("\\", "/")

    if not fm_match:
        print(json.dumps({
            "systemMessage": (
                f"{rel} has no frontmatter block at all — add doc_type/status/"
                "context_budget so it participates in this framework's indexing "
                "and context-budget discipline (see any existing doc for the shape)."
            ),
        }))
        return

    frontmatter = fm_match.group(1)
    missing = [k for k in REQUIRED_KEYS if not re.search(rf"^{k}:\s*\S", frontmatter, re.MULTILINE)]

    if missing:
        print(json.dumps({
            "systemMessage": f"{rel} is missing frontmatter field(s): {', '.join(missing)}.",
        }))


if __name__ == "__main__":
    main()
