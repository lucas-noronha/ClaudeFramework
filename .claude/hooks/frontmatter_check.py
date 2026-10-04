"""PostToolUse: nudge (never block) when a doc under docs/ is missing
the frontmatter keys the rest of this framework's tooling depends on
(`doc_type`, `status`, `context_budget`). Without these, a doc silently
falls outside the cost-aware indexing this framework relies on
(CLAUDE.md's index, context_budget_check.py, the "load the narrowest
doc" discipline) — better to flag it once than have it go unnoticed.

Architecture docs get one more nudge (framework ADR 0019, framework spec 0002 FR-05): a
missing routing summary key — the question the doc answers, which index
tables copy verbatim. The key names default to `summary`/`notFor` (the
older `resumo`/`naoResponde` stay readable as aliases) and are configurable
per project (`project-config.json` → `routing_keys`, see `_project_paths.routing_keys`).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _spec_layout  # noqa: E402
from _project_paths import hook_should_run, read_hook_input, resolve_docs_root, resolve_project_root, routing_keys, specs_dir  # noqa: E402

REQUIRED_KEYS = ["doc_type", "status", "context_budget"]
# A spec folder's companion files (plan, tasks, reconciliation, notes) carry no
# `status` (the status lives in spec.md) but do carry `spec` and a routing
# summary (framework ADR 0024 section 5). `tier:` is a known key: no nudge.
COMPANION_KEYS = ["doc_type", "spec", "summary", "context_budget"]


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
        return  # auto-generated indexes, not authored docs

    try:
        with open(abspath, encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return

    fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    rel = os.path.relpath(abspath, root).replace("\\", "/")

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
    ref = _spec_layout.classify(specs_dir(project), abspath)
    is_companion = bool(ref) and ref["layout"] != "legacy" and ref["role"] != "spec"
    summary_key = routing_keys(project)["summary"]["key"]
    summary_names = [summary_key, *routing_keys(project)["summary"]["aliases"]]
    missing = []
    for k in (COMPANION_KEYS if is_companion else REQUIRED_KEYS):
        names = summary_names if k == "summary" else [k]
        if not any(re.search(rf"^{re.escape(n)}:\s*\S", frontmatter, re.MULTILINE) for n in names):
            missing.append(summary_key if k == "summary" else k)

    messages = []
    if missing:
        messages.append(f"{rel} is missing frontmatter field(s): {', '.join(missing)}.")

    is_architecture = re.search(r"^doc_type:\s*architecture\s*$", frontmatter, re.MULTILINE) or rel.split("/")[-2:-1] == ["architecture"]
    if is_architecture and not is_companion:
        names = "|".join(re.escape(k) for k in summary_names)
        if not re.search(rf"^(?:{names}):\s*\S", frontmatter, re.MULTILINE):
            messages.append(
                f"{rel} has no `{summary_key}` — add the one question this doc answers "
                "(index tables copy it verbatim; see docs/workflow/living-architecture-docs.md)."
            )

    if messages:
        print(json.dumps({"systemMessage": " ".join(messages)}))


if __name__ == "__main__":
    main()
