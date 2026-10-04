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

The same row also gets compared against the doc's routing summary
(`resumo` by default, configurable via `routing_keys`, framework ADR 0019): index
tables copy it verbatim, and the doc wins when the two diverge.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _project_paths import hook_should_run, load_project_config, read_hook_input, resolve_docs_root, resolve_project_root  # noqa: E402


def routing_summary_key(project: str) -> str:
    configured = load_project_config(project).get("routing_keys")
    if isinstance(configured, dict) and isinstance(configured.get("summary"), str) and configured["summary"]:
        return configured["summary"]
    return "resumo"


def extract_number(text: str):
    m = re.search(r"(\d+)", text)
    return int(m.group(1)) if m else None


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
    frontmatter = fm_match.group(1)
    budget_match = re.search(r"^context_budget:\s*(.+)$", frontmatter, re.MULTILINE)
    doc_budget = extract_number(budget_match.group(1)) if budget_match else None
    summary_key = routing_summary_key(project)
    summary_match = re.search(rf"^{re.escape(summary_key)}:\s*(.+)$", frontmatter, re.MULTILINE)
    doc_summary = summary_match.group(1).strip().strip("\"'") if summary_match else None
    if doc_budget is None and not doc_summary:
        return  # nothing this hook compares

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
    # doc: its first cell is the "I need..." text, its trailing cell the
    # ~Cost.
    row_pattern = re.compile(
        r"^\|\s*([^|]*?)\s*\|.*`" + re.escape(rel_doc_path) + r"`.*\|\s*(~[^|]+?)\s*\|\s*$",
        re.MULTILINE,
    )
    row_match = row_pattern.search(claude_md)
    if not row_match:
        return  # not indexed in CLAUDE.md at all — nothing to check here

    rel_claude_md = os.path.relpath(claude_md_path, root).replace("\\", "/")
    messages = []

    index_budget = extract_number(row_match.group(2))
    if doc_budget is not None and index_budget is not None and index_budget != doc_budget:
        messages.append(
            f"{rel_claude_md}'s Index table says {rel_doc_path} costs "
            f"~{index_budget} tok, but its own frontmatter now says "
            f"~{doc_budget} tok. Update the Index row — this file is "
            "hand-authored, so nothing does it for you automatically."
        )

    # Routing summary (framework ADR 0019): the index copies the doc's own summary
    # verbatim, and the doc wins on divergence.
    if doc_summary and row_match.group(1).strip() != doc_summary:
        messages.append(
            f"{rel_claude_md}'s Index row for {rel_doc_path} doesn't match the "
            f"doc's own `{summary_key}` (\"{doc_summary}\"). The doc wins — copy "
            "it into the row verbatim."
        )

    if messages:
        print(json.dumps({"systemMessage": " ".join(messages)}))


if __name__ == "__main__":
    main()
