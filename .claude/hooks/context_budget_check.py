"""PostToolUse: nudge (never block) when a doc under docs/ has grown
well past its own frontmatter's `context_budget` estimate. Turns the
framework's "don't let a doc bloat, split it" discipline from a prose
reminder into a mechanical check, at zero token cost — no tokenizer
dependency, just a rough chars-per-token heuristic, so it's a nudge to
go look, not an authoritative token count.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _project_paths import hook_should_run, read_hook_input, resolve_docs_root, resolve_project_root  # noqa: E402

CHARS_PER_TOKEN = 4  # rough, stdlib-only heuristic — good enough for a drift nudge
OVERAGE_FACTOR = 2  # only nudge past 2x the stated budget, to avoid noisy near-misses


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
        return  # auto-generated indexes, not authored docs with a budget of their own

    try:
        with open(abspath, encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return

    fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    frontmatter = fm_match.group(1) if fm_match else ""

    budget_match = re.search(r"^context_budget:\s*(.+)$", frontmatter, re.MULTILINE)
    if not budget_match:
        return

    number_match = re.search(r"(\d+)", budget_match.group(1))
    if not number_match:
        return  # e.g. "~fill in once written" — nothing to compare against yet
    stated_budget = int(number_match.group(1))

    estimated_tokens = len(content) // CHARS_PER_TOKEN

    if estimated_tokens > stated_budget * OVERAGE_FACTOR:
        rel = os.path.relpath(abspath, root).replace("\\", "/")
        print(json.dumps({
            "systemMessage": (
                f"{rel} is roughly {estimated_tokens} tokens, well past its own "
                f"context_budget (~{stated_budget}). Consider splitting it — "
                "one subject per file — or updating context_budget if the growth "
                "is deliberate."
            ),
        }))


if __name__ == "__main__":
    main()
