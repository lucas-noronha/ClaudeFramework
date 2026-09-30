"""PostToolUse: nudge (never block, never auto-edit) when CLAUDE.md's
own "Index — load only what you need" table quotes a different ~Cost
than the doc it points at actually declares in its own frontmatter.

Deliberately a nudge, not an auto-rewrite like decision_index.py/
spec_index.py/skill_index.py: those three own a file marked "do not
edit by hand" top to bottom, so silently regenerating it is safe.
CLAUDE.md is the opposite — a hand-authored file with editorial prose
around this one table — so a hook has no business rewriting a line
inside it without a human looking. This exists because that exact drift
happened in practice: several docs' context_budget frontmatter changed
without anyone remembering to update CLAUDE.md's copy of the number.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _project_paths import resolve_docs_root, resolve_project_root  # noqa: E402


def extract_number(text: str):
    m = re.search(r"(\d+)", text)
    return int(m.group(1)) if m else None


def main() -> None:
    data = json.load(sys.stdin)
    path = data.get("tool_input", {}).get("file_path", "") or data.get("tool_response", {}).get("filePath", "")
    if not path:
        return

    project = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    root = resolve_project_root(project)
    abspath = path if os.path.isabs(path) else os.path.join(project, path)
    docs_dir = resolve_docs_root(project)

    normalized = abspath.replace("\\", "/")
    normalized_docs_dir = docs_dir.replace("\\", "/").rstrip("/")

    if not normalized.startswith(normalized_docs_dir + "/") or not normalized.endswith(".md"):
        return
    if os.path.basename(abspath) == "README.md":
        return  # auto-generated indexes, not docs with their own budget

    try:
        with open(abspath, encoding="utf-8") as f:
            doc_content = f.read()
    except FileNotFoundError:
        return

    fm_match = re.match(r"^---\n(.*?)\n---", doc_content, re.DOTALL)
    if not fm_match:
        return
    budget_match = re.search(r"^context_budget:\s*(.+)$", fm_match.group(1), re.MULTILINE)
    if not budget_match:
        return
    doc_budget = extract_number(budget_match.group(1))
    if doc_budget is None:
        return  # e.g. "~fill in once written" — nothing yet to compare

    # CLAUDE.md doesn't exist until /setup-framework renames the
    # template — fall back to the template so this still works pre-setup
    # (including in this framework's own repo).
    claude_md_path = os.path.join(root, "CLAUDE.md")
    if not os.path.isfile(claude_md_path):
        claude_md_path = os.path.join(root, "CLAUDE.md.template")
        if not os.path.isfile(claude_md_path):
            return

    try:
        with open(claude_md_path, encoding="utf-8") as f:
            claude_md = f.read()
    except FileNotFoundError:
        return

    rel_doc_path = os.path.relpath(abspath, root).replace("\\", "/")

    # Find the Index table row whose backtick-quoted path matches this
    # doc, then pull the number out of its trailing ~Cost cell.
    row_pattern = re.compile(
        r"^\|.*`" + re.escape(rel_doc_path) + r"`.*\|\s*(~[^|]+?)\s*\|\s*$",
        re.MULTILINE,
    )
    row_match = row_pattern.search(claude_md)
    if not row_match:
        return  # not indexed in CLAUDE.md at all — nothing to check here

    index_budget = extract_number(row_match.group(1))
    if index_budget is None:
        return  # e.g. "~fill in" — nothing yet to compare

    if index_budget != doc_budget:
        rel_claude_md = os.path.relpath(claude_md_path, root).replace("\\", "/")
        print(json.dumps({
            "systemMessage": (
                f"{rel_claude_md}'s Index table says {rel_doc_path} costs "
                f"~{index_budget} tok, but its own frontmatter now says "
                f"~{doc_budget} tok. Update the Index row — this file is "
                "hand-authored, so nothing does it for you automatically."
            ),
        }))


if __name__ == "__main__":
    main()
