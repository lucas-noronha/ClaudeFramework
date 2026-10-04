"""PostToolUse: flip a spec's frontmatter `status` to `implemented`
automatically once every checkbox in its "## Tasks" section (written
by /tasks, checked off by /implement) is checked. Mirrors adr_backlink.py's
pattern of keeping cross-file/cross-section consistency without relying
on someone remembering to update it by hand. Writes the filesystem
directly (not through the Write/Edit tool), so it never re-triggers
itself.

Works across the spec layouts (framework ADR 0024 section 2): in a folder
the boxes live in `tasks.md` and the status in `spec.md`; in a lite folder
or a legacy single file both live in the one file. The write touches only
the `status:` line of the spec file's frontmatter, byte for byte (line
endings and encoding stay as they were), then the index is rebuilt in
process.

Deliberately conservative: only flips from a status that already implies
the stakeholder validation checkpoint happened (never from `draft`) —
this hook tightens bookkeeping, it never substitutes for that checkpoint.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _spec_layout  # noqa: E402
import spec_index  # noqa: E402
from _pipeline_metrics import log_event  # noqa: E402
from _project_paths import hook_should_run, read_hook_input, specs_dir  # noqa: E402

STATUSES_ELIGIBLE_TO_FLIP = {"approved"}
BOX_RE = re.compile(r"^\s*-\s*\[( |x|X)\]", re.MULTILINE)


def flip_due(ref) -> int:
    """The number of task boxes when this spec is due to flip from
    `approved` to `implemented` (at least one box, every box checked),
    else 0. Shared with `spec_index.py`, which stays silent when it holds.
    """
    status_file = ref.get("status_file") if ref else None
    if not status_file:
        return 0
    fm = _spec_layout.frontmatter(_spec_layout.read_text(status_file))
    if fm.get("status", "").strip() not in STATUSES_ELIGIBLE_TO_FLIP:
        return 0
    tasks = ref.get("tasks") or {}
    if not tasks.get("file"):
        return 0
    body = _spec_layout.section(_spec_layout.read_text(tasks["file"]), tasks.get("section") or "Tasks")
    if body is None:
        return 0
    boxes = BOX_RE.findall(body)
    if not boxes or any(b == " " for b in boxes):
        return 0
    return len(boxes)


def flip_status_bytes(raw: bytes):
    """`raw` with only the frontmatter `status:` line rewritten to
    `implemented`, every other byte kept; None when there is no such line.
    """
    bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    lines = raw[len(bom):].split(b"\n")
    if not lines or lines[0].rstrip(b"\r").strip() != b"---":
        return None
    for i in range(1, len(lines)):
        stripped = lines[i].rstrip(b"\r")
        if stripped.strip() == b"---":
            return None
        if re.match(rb"^status[ \t]*:", stripped):
            lines[i] = b"status: implemented" + lines[i][len(stripped):]
            return bom + b"\n".join(lines)
    return None


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
    abspath = path if os.path.isabs(path) else os.path.join(project, path)
    base = os.path.basename(abspath)
    if ".validation-" in base:
        return

    # Self-gating: this hook fires on every Write/Edit in the multi-project
    # settings variant, so the resolver decides relevance (a spec file or a
    # folder's spec.md/tasks.md, at the right depth) instead of a literal-prefix
    # `if` condition.
    ref = _spec_layout.classify(specs_dir(project), abspath)
    if ref is None or ref["role"] not in ("spec", "tasks"):
        return

    box_count = flip_due(ref)
    if not box_count:
        return

    status_file = ref["status_file"]
    try:
        with open(status_file, "rb") as f:
            raw = f.read()
    except OSError:
        return
    updated = flip_status_bytes(raw)
    if updated is None:
        return
    try:
        with open(status_file, "wb") as f:
            f.write(updated)
    except OSError:
        return  # fail open: a locked or read-only file never blocks the session

    fm = _spec_layout.frontmatter(_spec_layout.read_text(status_file))
    log_event(
        project, "spec_implemented",
        spec_id=ref["id"] or ref["number"] or base[:4],
        area=fm.get("area") or None,
    )
    try:
        spec_index.rebuild(project)
    except OSError:
        pass  # the flip itself landed; a stale index is refreshed by the next spec edit

    print(json.dumps({
        "systemMessage": f"{base}: all {box_count} tasks checked off — status flipped to implemented.",
    }))


if __name__ == "__main__":
    main()
