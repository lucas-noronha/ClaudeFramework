"""Shared helper for pipeline_metrics.py and spec_status_sync.py —
append one JSON line per pipeline-observability event to the
git-ignored .claude/pipeline-metrics.jsonl (see
.gitignore.framework-additions). Not a hook entry point itself, not
wired in settings.json directly — imported by the hooks that are.
"""
import json
import os
import time

LOG_REL_PATH = os.path.join(".claude", "pipeline-metrics.jsonl")


def log_event(project: str, event: str, **fields) -> None:
    record = {"ts": time.time(), "event": event, **fields}
    path = os.path.join(project, LOG_REL_PATH)
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        pass
