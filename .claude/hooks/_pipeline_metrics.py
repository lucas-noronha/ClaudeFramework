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
from _project_paths import linked_worktree, state_file_path  # noqa: E402

LOG_FILENAME = "pipeline-metrics.jsonl"
LOCK_WAIT = 1.0  # seconds; a stuck lock must never block a hook
_LOCK_OFFSET = 1 << 30  # Windows locks a byte range; far from any real line


def _lock(f) -> bool:
    """Advisory exclusive lock on the open log, bounded wait. False on
    timeout or when locking is unavailable: the caller appends anyway."""
    deadline = time.monotonic() + LOCK_WAIT
    while True:
        try:
            if os.name == "nt":
                import msvcrt
                f.seek(_LOCK_OFFSET)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except ImportError:
            return False
        except OSError:
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.01)


def _unlock(f) -> None:
    try:
        if os.name == "nt":
            import msvcrt
            f.seek(_LOCK_OFFSET)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except (ImportError, OSError):
        pass


def log_event(project: str, event: str, **fields) -> None:
    """`project` is this session's CLAUDE_PROJECT_DIR; where the log
    actually lands is resolved from it, not assumed to be under it.

    The log is project-scoped: every checkout of a project (linked
    worktrees included) appends to the same file, and an event from a
    linked worktree carries `checkout` (its admin name) so `metrics.py`
    can tell concurrent features apart (framework ADR 0022 section 3).
    Appends take an advisory lock; on timeout the line is written anyway.
    """
    record = {"ts": time.time(), "event": event, **fields}
    wt = linked_worktree(project)
    if wt:
        record["checkout"] = wt["admin"]
    path = state_file_path(project, LOG_FILENAME, "project")
    data = (json.dumps(record) + "\n").encode("utf-8")
    try:
        with open(path, "ab") as f:
            locked = _lock(f)
            try:
                f.seek(0, os.SEEK_END)
                f.write(data)
                f.flush()
            finally:
                if locked:
                    _unlock(f)
    except OSError:
        pass
