"""Shared helper for pipeline_metrics.py and spec_status_sync.py —
append one JSON line per pipeline-observability event to the git-ignored
pipeline-metrics.jsonl (see .gitignore.framework-additions). Not a hook
entry point itself, not wired in settings.json directly — imported by
the hooks that are.

The log belongs to one project, not to one `.claude/`: with a shared
`.claude/` backing several target repos, `<project>/.claude/` is the
same physical file for all of them, so one project's metrics would leak
into another's (framework ADR 0013). `state_file_path` routes it to the project's
own subtree when this session is registered, and leaves it at today's
`<project>/.claude/pipeline-metrics.jsonl` when it isn't.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _project_paths import state_file_path  # noqa: E402

LOG_FILENAME = "pipeline-metrics.jsonl"


def log_event(project: str, event: str, **fields) -> None:
    """`project` is this session's CLAUDE_PROJECT_DIR; where the log
    actually lands is resolved from it, not assumed to be under it.
    """
    record = {"ts": time.time(), "event": event, **fields}
    path = state_file_path(project, LOG_FILENAME)
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        pass
