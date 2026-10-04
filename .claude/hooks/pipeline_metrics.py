"""PostToolUse: append pipeline-observability events to the git-ignored
.claude/pipeline-metrics.jsonl — no dashboard, no new service, just a
raw event stream a human (or an agent, on request) can summarize later
(e.g. with `jq`). Purely additive: never blocks, never rewrites
anything a human wrote. See framework ADR 0011.

Wired to several different triggers in settings.json, all landing here:

- Write to a spec (docs/product/specs/NNNN-*.md, or a folder's spec.md)
  -> "spec_created"
- Edit/Write to a spec's reconciliation target -> "reconciliation_snapshot"
  (a folder's reconciliation.md, or the "## Reconciliation" section of a
  lite/legacy single file; counts lines by outcome; a snapshot of the
  CURRENT total, not a delta, so it's correct regardless of how the
  Edit was actually applied under the hood; framework ADR 0024)
- PostToolUse on any subagent dispatch -> "subagent_dispatched"
  (framework ADR 0020: the per-feature subagent count `/metrics` compares)
- SubagentStop of a "reviewer" (or `<prefix>-reviewer`) -> "reviewer_verdict"
  (Approved/Returned read from the end of its transcript, spec id from the
  transcript's first user message; framework ADR 0025)

Other events land in the same log from elsewhere: "spec_implemented"
from spec_status_sync.py (it already computes the exact status
transition, so duplicating the detection here could drift), "gate_run"
from run_build_test.py, and "feature_started"/"feature_finished" from
`.claude/scripts/metrics.py`, which `/implement` and `/quick` call to
mark which feature the events in between belong to.

Best-effort throughout: never raises, never blocks, no-ops on any
shape it doesn't recognize. subagent_dispatched depends on your Claude
Code version's subagent-dispatch tool being named "Task" or "Agent"
(both matched in settings.json).
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _pipeline_metrics import log_event  # noqa: E402
import _spec_layout  # noqa: E402
from _subagents import first_user_text, last_assistant_text, read_jsonl, role_of  # noqa: E402
from _project_paths import hook_should_run, read_hook_input, specs_dir as specs_dir_of  # noqa: E402

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


def handle_spec_write(project: str, ref: dict, abspath: str, is_new_write: bool) -> None:
    """`ref` is the `_spec_layout` reference of the edited file (framework
    ADR 0024 section 4): the spec's id and status come from its `spec.md`
    (or the legacy file), the reconciliation from wherever the layout keeps
    it — a folder's `reconciliation.md` (whole file) or the `## Reconciliation`
    section of a lite/legacy single file.
    """
    spec_file = ref.get("spec_file")
    spec_id = area = status = None
    if spec_file:
        spec_id, area, status = spec_frontmatter(_spec_layout.read_text(spec_file))
    spec_id = spec_id or (ref.get("id") if re.fullmatch(r"\d{4}", str(ref.get("id") or "")) else None)
    if not spec_id:
        return

    if is_new_write and ref.get("role") == "spec" and status == "draft":
        log_event(project, "spec_created", spec_id=spec_id, area=area)

    target = ref.get("reconciliation") or {}
    target_file = target.get("file")
    if not target_file or os.path.normcase(os.path.abspath(target_file)) != os.path.normcase(os.path.abspath(abspath)):
        return  # an edit to plan/tasks/notes (or a folder's spec.md) carries no reconciliation
    content = _spec_layout.read_text(abspath)
    if target.get("section"):
        section = RECONCILIATION_SECTION.search(content)
        if not section:
            return
        body = section.group(1)
    else:
        body = content
    matches = len(re.findall(r"^\s*-\s*\[task \S+\].*?:\s*matches spec", body, re.MULTILINE))
    diverged = len(re.findall(r"^\s*-\s*\[task \S+\].*?:\s*diverged", body, re.MULTILINE))
    out_of_scope = len(re.findall(r"^\s*-\s*\[task \S+\]\s*out of scope", body, re.MULTILINE))
    if matches or diverged or out_of_scope:
        log_event(
            project, "reconciliation_snapshot", spec_id=spec_id,
            matches=matches, diverged=diverged, out_of_scope=out_of_scope,
        )


def handle_subagent_lifecycle(project: str, data: dict, event: str) -> None:
    """`SubagentStart` / `SubagentStop` (framework ADR 0025): log the
    lifecycle event with only the fields the input carries.
    """
    fields = {}
    if data.get("agent_id"):
        fields["agent_id"] = data["agent_id"]
    agent_type = data.get("agent_type")
    if agent_type:
        fields["agent_type"] = agent_type
        fields["role"] = role_of(str(agent_type))
    log_event(project, event, **fields)
    if event == "subagent_stopped" and fields.get("role") == "reviewer":
        log_verdict_from_transcript(project, data)


# `NNNN-name.md` (legacy file), `NNNN-name/` or `NNNN-name\` (folder), either slash direction.
SPEC_REF = re.compile(r"(\d{4})-[\w-]+(?:\.md|[/\\])")
VERDICT_RETRIES = 4
VERDICT_RETRY_DELAY = 0.25  # seconds; the final message may land just after SubagentStop fires


def parse_verdict(text: str):
    stripped = text.lstrip().lstrip("*_#>`- \t\r\n")
    for verdict in ("Approved", "Returned"):
        if stripped.startswith(verdict):
            return verdict
    return None


def log_verdict_from_transcript(project: str, data: dict) -> None:
    """Framework ADR 0025: the reviewer's verdict is read from its own
    transcript on `SubagentStop`, so a background reviewer (whose PostToolUse
    response is only an ack) is counted too. Bounded retry: the transcript's
    final message may not be flushed yet when the hook fires.
    """
    path = data.get("agent_transcript_path")
    if not path:
        return
    verdict, records = None, []
    for attempt in range(VERDICT_RETRIES):
        records = read_jsonl(path)
        verdict = parse_verdict(last_assistant_text(records))
        if verdict or attempt == VERDICT_RETRIES - 1:
            break
        time.sleep(VERDICT_RETRY_DELAY)
    if not verdict:
        return  # doesn't match reviewer's documented reply format — skip rather than guess
    spec_match = SPEC_REF.search(first_user_text(records))
    fields = {"agent_id": data["agent_id"]} if data.get("agent_id") else {}
    log_event(project, "reviewer_verdict", verdict=verdict,
              spec_id=spec_match.group(1) if spec_match else None, **fields)


def handle_subagent_dispatch(project: str, data: dict) -> None:
    tool_input = data.get("tool_input", {})
    subagent_type = str(tool_input.get("subagent_type") or tool_input.get("subagent") or "general-purpose")

    # Every dispatch is counted (framework ADR 0020): `/metrics` compares the
    # subagent count per feature between the fast lane and the full path.
    log_event(project, "subagent_dispatched", subagent_type=subagent_type, role=role_of(subagent_type))
    # The reviewer verdict is NOT read here (framework ADR 0025): it is logged
    # once, on SubagentStop, from the reviewer's transcript.


def main() -> None:
    # Registration gate (framework ADR 0017): a no-op for an unregistered repo under
    # a user-level install; always open in modes A/B.
    if not hook_should_run(os.environ.get("CLAUDE_PROJECT_DIR", ".")):
        return

    data = read_hook_input()
    project = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    hook_event = data.get("hook_event_name")
    if hook_event in ("SubagentStart", "SubagentStop"):
        handle_subagent_lifecycle(project, data, "subagent_started" if hook_event == "SubagentStart" else "subagent_stopped")
        return
    tool_name = data.get("tool_name", "")

    if tool_name in ("Task", "Agent"):
        handle_subagent_dispatch(project, data)
        return

    path = data.get("tool_input", {}).get("file_path", "") or data.get("tool_response", {}).get("filePath", "")
    if not path:
        return
    abspath = path if os.path.isabs(path) else os.path.join(project, path)
    specs_dir = specs_dir_of(project)

    # Self-gating: this hook fires on every Write/Edit in the multi-project
    # settings variant, so it decides relevance itself rather than trusting
    # a literal-prefix `if` condition — `_spec_layout.classify` compares the
    # tool-reported path against the resolved specs_dir (a legacy file, or a
    # file one folder level down), which works regardless of which of the
    # two path shapes a tool call reports (see resolve_docs_root in
    # _project_paths.py).
    base = os.path.basename(abspath)
    if ".validation-" in base:
        return
    ref = _spec_layout.classify(specs_dir, abspath)
    if ref is None:
        return

    handle_spec_write(project, ref, abspath, is_new_write=(tool_name == "Write"))


if __name__ == "__main__":
    main()
