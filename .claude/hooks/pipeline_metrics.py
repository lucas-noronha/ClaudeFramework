"""PostToolUse: append pipeline-observability events to the git-ignored
.claude/pipeline-metrics.jsonl — no dashboard, no new service, just a
raw event stream a human (or an agent, on request) can summarize later
(e.g. with `jq`). Purely additive: never blocks, never rewrites
anything a human wrote. See docs/decisions/0011-pipeline-metrics.md.

Wired to several different triggers in settings.json, all landing here:

- Write to docs/product/specs/*.md (a new spec) -> "spec_created"
- Edit/Write to docs/product/specs/*.md -> "reconciliation_snapshot"
  (counts "## Reconciliation" lines by outcome; a snapshot of the
  CURRENT total, not a delta, so it's correct regardless of how the
  Edit was actually applied under the hood)
- PostToolUse on a subagent dispatch whose subagent_type is "reviewer"
  -> "reviewer_verdict" (Approved/Returned, best-effort spec id parsed
  from the prompt handed to it)

A fourth event this framework's metrics use, "spec_implemented", is
logged by spec_status_sync.py itself, not here — that hook already
computes the exact status transition; duplicating the detection here
would risk drifting out of sync with it if that logic ever changes.

Best-effort throughout: never raises, never blocks, no-ops on any
shape it doesn't recognize. The reviewer_verdict trigger depends on
your Claude Code version's subagent-dispatch tool actually being named
"Task" or "Agent" (both matched in settings.json) — if neither ever
fires after a few `/review`/`/implement` runs, no reviewer_verdict
events will appear; adjust the matcher to whatever your version uses.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _pipeline_metrics import log_event  # noqa: E402

RECONCILIATION_SECTION = re.compile(r"^##\s*Reconciliation\s*$(.*?)(?=^##\s|\Z)", re.MULTILINE | re.DOTALL)


def spec_frontmatter(content: str):
    fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    frontmatter = fm_match.group(1) if fm_match else ""
    id_match = re.search(r"^id:\s*(\d{4})", frontmatter, re.MULTILINE)
    area_match = re.search(r"^area:\s*(.+)$", frontmatter, re.MULTILINE)
    status_match = re.search(r"^status:\s*(.+)$", frontmatter, re.MULTILINE)
    return (
        id_match.group(1) if id_match else None,
        area_match.group(1).strip() if area_match else None,
        status_match.group(1).strip() if status_match else None,
    )


def handle_spec_write(project: str, abspath: str, is_new_write: bool) -> None:
    try:
        with open(abspath, encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return

    spec_id, area, status = spec_frontmatter(content)
    if not spec_id:
        return

    if is_new_write and status == "draft":
        log_event(project, "spec_created", spec_id=spec_id, area=area)

    section = RECONCILIATION_SECTION.search(content)
    if not section:
        return
    body = section.group(1)
    matches = len(re.findall(r"^\s*-\s*\[task \S+\].*?:\s*matches spec", body, re.MULTILINE))
    diverged = len(re.findall(r"^\s*-\s*\[task \S+\].*?:\s*diverged", body, re.MULTILINE))
    out_of_scope = len(re.findall(r"^\s*-\s*\[task \S+\]\s*out of scope", body, re.MULTILINE))
    if matches or diverged or out_of_scope:
        log_event(
            project, "reconciliation_snapshot", spec_id=spec_id,
            matches=matches, diverged=diverged, out_of_scope=out_of_scope,
        )


def handle_subagent_dispatch(project: str, data: dict) -> None:
    tool_input = data.get("tool_input", {})
    subagent_type = tool_input.get("subagent_type") or tool_input.get("subagent")
    if subagent_type != "reviewer":
        return

    raw_response = data.get("tool_response", "")
    if isinstance(raw_response, dict):
        text = raw_response.get("result") or raw_response.get("content") or raw_response.get("output") or ""
        if isinstance(text, list):
            text = " ".join(str(part) for part in text)
    else:
        text = str(raw_response)

    stripped = text.strip().lstrip("*").strip()
    if stripped.startswith("Approved"):
        verdict = "Approved"
    elif stripped.startswith("Returned"):
        verdict = "Returned"
    else:
        return  # doesn't match reviewer's documented reply format — skip rather than guess

    prompt_text = str(tool_input.get("prompt", "") or tool_input.get("description", ""))
    spec_match = re.search(r"(\d{4})-[\w-]+\.md", prompt_text)
    log_event(project, "reviewer_verdict", verdict=verdict, spec_id=spec_match.group(1) if spec_match else None)


def main() -> None:
    data = json.load(sys.stdin)
    project = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    tool_name = data.get("tool_name", "")

    if tool_name in ("Task", "Agent"):
        handle_subagent_dispatch(project, data)
        return

    path = data.get("tool_input", {}).get("file_path", "") or data.get("tool_response", {}).get("filePath", "")
    if not path:
        return
    abspath = path if os.path.isabs(path) else os.path.join(project, path)
    specs_dir = os.path.join(project, "docs", "product", "specs")
    normalized_dir = os.path.dirname(abspath).replace("\\", "/").rstrip("/")
    if normalized_dir != specs_dir.replace("\\", "/").rstrip("/"):
        return
    base = os.path.basename(abspath)
    if base == "README.md" or ".validation-" in base:
        return

    handle_spec_write(project, abspath, is_new_write=(tool_name == "Write"))


if __name__ == "__main__":
    main()
