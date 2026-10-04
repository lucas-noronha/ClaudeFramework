"""SubagentStop gate: run this project's own build/test command — but
only when the subagent that just stopped can have changed code (spec
0003 FR-02, framework ADR 0020).

Where the command comes from: in modes B/C one shared `settings.json`
serves several projects (framework ADR 0013), so static text can't hold their
different commands; the command is read at runtime from the project's
`project-config.json` (the optional `.claude/project-config.json` in
mode A, framework ADR 0020).

Which stops run it. Before framework ADR 0020 every `SubagentStop` ran the full
build, so read-only subagents like Explore, `triage`, `researcher` and
`architect` each paid for one. Now:

1. A code-writing role (`coder`, `quickfix`, with or without an install
   prefix such as `cfw-coder`) always runs it.
2. Any other subagent runs it only if its own transcript
   (`agent_transcript_path`) shows an Edit/Write/MultiEdit/NotebookEdit
   on a file under `CLAUDE_PROJECT_DIR`, outside the framework's docs
   root and `.claude/`. Writing an ADR or appending to a spec's
   Reconciliation section doesn't count as a code change.
3. With no transcript to read, a subagent known to be read-only skips:
   a built-in like Explore, or an agent definition whose `tools:` list
   has no write-capable tool.
4. Anything else runs the gate. When in doubt, build.

Known gap, named rather than hidden: a non-code-writer agent that edits
code only through Bash is invisible to step 2. The final `/review` still
runs over the whole diff.

Exit codes (framework ADR 0025). A pass exits 0. A failure exits 2 while
`stop_hook_active` is false: Claude Code hands stderr (a header plus the last
~80 lines / 8 KB of the build's output) back to the stopping agent so it fixes
its own failure before it ends. When `stop_hook_active` is true the agent
already got that chance, so the gate exits 1 (non-blocking) to break the loop.
The hand-back is best-effort: a subagent that ends through a `SubagentHandback`
tool call isn't resumed by exit 2 (spec 0007 task 9), so `/implement` reads
this gate's `gate_run` with `metrics.py gates` and returns a failure itself.
A missing `build_test_cmd` stays a non-blocking exit 1: on the one hook whose
entire job is running that command, its absence is a real misconfiguration,
but not something the agent can fix.

`concurrent` (logged on `gate_run`, omitted when unknown) is the number of
other, code-capable subagents of this checkout that overlapped this one in the
open feature (or the last 60 minutes), read from a byte-capped tail of the
metrics log. When above 0 the failure header warns the agent that a failure
may come from a sibling's files and that it must not touch files outside its
own task.

`shell=True` is deliberate and no wider a trust boundary than before:
the string comes from the project's own config, written by setup or
registration from the developer's own answer. No session-supplied input
reaches it.
"""
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _pipeline_metrics import LOG_FILENAME, log_event  # noqa: E402
from _subagents import WRITE_TOOLS, is_read_only, read_jsonl, role_of  # noqa: E402
from _project_paths import (  # noqa: E402
    hook_should_run,
    linked_worktree,
    load_project_config,
    normalize,
    project_config_path,
    read_hook_input,
    resolve_docs_root,
    state_file_path,
)

CONFIG_KEY = "build_test_cmd"
CODE_WRITER_ROLES = {"coder", "quickfix"}
LOG_TAIL_BYTES = 256 * 1024
CONCURRENT_WINDOW_SECONDS = 60 * 60
OUTPUT_TAIL_LINES = 80
OUTPUT_TAIL_BYTES = 8 * 1024


def _inside(path: str, root: str) -> bool:
    try:
        rel = os.path.relpath(path, root)
    except ValueError:
        return False
    rel = normalize(rel)
    return rel != ".." and not rel.startswith("../") and not os.path.isabs(rel)


def edited_code_files(transcript_path: str, project: str):
    """Code files this subagent edited, per its own transcript, or None
    when the transcript can't be read. Docs-root and `.claude/` edits are
    excluded: they are framework artifacts, not code a build can break.
    """
    try:
        with open(transcript_path, encoding="utf-8") as f:
            lines = f.readlines()
    except (OSError, TypeError):
        return None

    docs_root = resolve_docs_root(project)
    claude_dir = os.path.join(project, ".claude")
    edited = []
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        content = (record.get("message") or {}).get("content") if isinstance(record, dict) else None
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "tool_use" or item.get("name") not in WRITE_TOOLS:
                continue
            tool_input = item.get("input") or {}
            path = tool_input.get("file_path") or tool_input.get("notebook_path")
            if not path:
                continue
            abspath = path if os.path.isabs(path) else os.path.join(project, path)
            if not _inside(abspath, project) or _inside(abspath, docs_root) or _inside(abspath, claude_dir):
                continue
            edited.append(normalize(abspath))
    return edited


def should_run_gate(data: dict, project: str):
    """`(run, reason)` — see the module docstring for the four rules."""
    agent_type = str(data.get("agent_type") or data.get("subagent_type") or "")
    if role_of(agent_type) in CODE_WRITER_ROLES:
        return True, f"{agent_type} writes code"

    transcript = data.get("agent_transcript_path")
    if transcript:
        edited = edited_code_files(transcript, project)
        if edited is not None:
            if edited:
                return True, f"{agent_type or 'subagent'} edited {len(edited)} code file(s)"
            return False, f"{agent_type or 'subagent'} edited no code"

    if is_read_only(project, agent_type):
        return False, f"{agent_type} is read-only"
    return True, "could not tell whether code changed"


def concurrent_agents(project: str, agent_id, now=None):
    """Other code-capable subagents of this checkout that overlapped the
    stopping one, or None when it has no start event to measure from.

    Reads only a byte-capped tail of the metrics log. The window is the
    open feature of this checkout (its last unfinished `feature_started`),
    or the last 60 minutes when none is open. A sibling counts when it
    started inside the window before now and is in flight (its latest event is
    a start or a blocking gate) or stopped only after this agent started. Read-only agents never count.
    """
    if not agent_id:
        return None
    now = time.time() if now is None else now
    log_path = state_file_path(project, LOG_FILENAME, "project")
    wt = linked_worktree(project)
    checkout = wt["admin"] if wt else "main"
    events = [
        e for e in read_jsonl(log_path, tail_bytes=LOG_TAIL_BYTES)
        if (e.get("checkout") or "main") == checkout and isinstance(e.get("ts"), (int, float))
    ]
    own_start = None
    open_features = []
    for e in events:
        kind = e.get("event")
        if kind == "subagent_started" and e.get("agent_id") == agent_id:
            own_start = e["ts"]
        elif kind == "feature_started":
            open_features.append(e)
        elif kind == "feature_finished":
            for i in range(len(open_features) - 1, -1, -1):
                if open_features[i].get("feature") == e.get("feature"):
                    del open_features[i]
                    break
    if own_start is None:
        return None
    window_start = open_features[-1]["ts"] if open_features else now - CONCURRENT_WINDOW_SECONDS
    # Latest start / stop / blocking gate per agent: a start or a blocked gate
    # (the agent was sent back to work) means in flight.
    latest = {}
    for e in events:
        kind = e.get("event")
        if kind == "gate_run" and e.get("blocked") is True:
            kind = "blocked"
        elif kind not in ("subagent_started", "subagent_stopped"):
            continue
        if e.get("agent_id"):
            latest[e["agent_id"]] = (e["ts"], kind)
    siblings = set()
    for e in events:
        other = e.get("agent_id")
        if e.get("event") != "subagent_started" or not other or other == agent_id:
            continue
        if e["ts"] < window_start or e["ts"] > now:
            continue
        last_ts, last_kind = latest[other]
        if last_kind == "subagent_stopped" and last_ts < own_start:
            continue
        if is_read_only(project, str(e.get("agent_type") or "")):
            continue
        siblings.add(other)
    return len(siblings)


def output_tail(text: str) -> str:
    """The last ~80 lines of `text`, capped at ~8 KB (cut on a character)."""
    tail = "\n".join(text.splitlines()[-OUTPUT_TAIL_LINES:])
    raw = tail.encode("utf-8")
    if len(raw) > OUTPUT_TAIL_BYTES:
        tail = raw[-OUTPUT_TAIL_BYTES:].decode("utf-8", errors="ignore")
    return tail


def failure_header(command: str, returncode: int, concurrent) -> str:
    lines = [f"Build/test gate FAILED (exit {returncode}): {command}"]
    if concurrent:
        lines.append(
            f"{concurrent} other agent(s) are working in this checkout at the same time, so this "
            "failure may come from a sibling's files. Fix only what your own task changed and "
            "do not touch files outside your task."
        )
    lines.append("Last lines of the output:")
    return "\n".join(lines)


def main() -> int:
    # Registration gate (framework ADR 0017): a no-op for an unregistered repo under
    # a user-level install; always open in modes A/B.
    project = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    if not hook_should_run(project):
        return 0

    data = read_hook_input()
    if not isinstance(data, dict):
        data = {}

    run, reason = should_run_gate(data, project)
    if not run:
        return 0

    command = load_project_config(project).get(CONFIG_KEY)
    if not isinstance(command, str) or not command.strip():
        print(
            f"No `{CONFIG_KEY}` in {normalize(project_config_path(project))} — "
            "this project has no build/test command registered, so the "
            "deterministic gate can't run. Re-run /setup-framework (mode A) "
            "or the project registration (modes B/C) to record it.",
            file=sys.stderr,
        )
        return 1

    agent_id = data.get("agent_id")
    concurrent = concurrent_agents(project, agent_id)

    # Output is captured (stderr merged into stdout) so a failure can hand a
    # bounded tail back to the agent; a pass echoes it unchanged.
    # cwd is the code repo, not the resolved subtree — the source to
    # build lives in the target repo, only its configuration doesn't.
    proc = subprocess.run(
        command.strip(), shell=True, cwd=project,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    output = proc.stdout.decode("utf-8", errors="replace")
    failed = proc.returncode != 0
    blocked = failed and not data.get("stop_hook_active")
    fields = {}
    if concurrent is not None:
        fields["concurrent"] = concurrent
    log_event(
        project, "gate_run",
        agent_type=data.get("agent_type") or data.get("subagent_type"),
        reason=reason, exit_code=proc.returncode, agent_id=agent_id, blocked=blocked, **fields,
    )
    if not failed:
        sys.stdout.write(output)
        sys.stdout.flush()
        return 0
    stream = sys.stderr
    if blocked:
        print(failure_header(command.strip(), proc.returncode, concurrent), file=stream)
        print(output_tail(output), file=stream)
        return 2
    print(failure_header(command.strip(), proc.returncode, concurrent), file=stream)
    print(output_tail(output), file=stream)
    return 1


if __name__ == "__main__":
    sys.exit(main())
