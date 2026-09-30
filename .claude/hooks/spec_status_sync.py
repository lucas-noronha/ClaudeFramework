"""PostToolUse: flip a spec's frontmatter `status` to `implemented`
automatically once every checkbox in its "## Tasks" section (written
by /tasks, checked off by /implement) is checked. Mirrors adr_backlink.py's
pattern of keeping cross-file/cross-section consistency without relying
on someone remembering to update it by hand. Writes the filesystem
directly (not through the Write/Edit tool), so it never re-triggers
itself.

Deliberately conservative: only flips from a status that already implies
the stakeholder validation checkpoint happened (never from `draft`) —
this hook tightens bookkeeping, it never substitutes for that checkpoint.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _pipeline_metrics import log_event  # noqa: E402
from _project_paths import normalize, resolve_docs_root  # noqa: E402

STATUSES_ELIGIBLE_TO_FLIP = {"approved"}


def main() -> None:
    data = json.load(sys.stdin)
    path = data.get("tool_input", {}).get("file_path", "") or data.get("tool_response", {}).get("filePath", "")
    if not path:
        return

    project = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    abspath = path if os.path.isabs(path) else os.path.join(project, path)
    specs_dir = os.path.join(resolve_docs_root(project), "product", "specs")

    # Self-gating: this hook fires on every Write/Edit in the multi-project
    # settings variant, so it decides relevance itself rather than trusting
    # a literal-prefix `if` condition — it compares the tool-reported
    # path's own directory against the resolved specs_dir directly instead,
    # which works regardless of which of the two path shapes a tool call
    # reports (see resolve_docs_root in _project_paths.py).
    if normalize(os.path.dirname(abspath)) != normalize(specs_dir):
        return
    base = os.path.basename(abspath)
    if base == "README.md" or ".validation-" in base:
        return

    try:
        with open(abspath, encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return

    fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not fm_match:
        return
    frontmatter = fm_match.group(1)

    status_match = re.search(r"^status:\s*(.+)$", frontmatter, re.MULTILINE)
    current_status = status_match.group(1).strip() if status_match else ""
    if current_status not in STATUSES_ELIGIBLE_TO_FLIP:
        return

    tasks_match = re.search(r"^##\s*Tasks\s*$(.*?)(?=^##\s|\Z)", content, re.MULTILINE | re.DOTALL)
    if not tasks_match:
        return
    tasks_section = tasks_match.group(1)

    boxes = re.findall(r"^\s*-\s*\[( |x|X)\]", tasks_section, re.MULTILINE)
    if not boxes:
        return
    if any(b == " " for b in boxes):
        return  # still some unchecked

    updated = content.replace(f"status: {current_status}", "status: implemented", 1)
    with open(abspath, "w", encoding="utf-8") as f:
        f.write(updated)

    id_match = re.search(r"^id:\s*(\d{4})", frontmatter, re.MULTILINE)
    area_match = re.search(r"^area:\s*(.+)$", frontmatter, re.MULTILINE)
    log_event(
        project, "spec_implemented",
        spec_id=id_match.group(1) if id_match else base[:4],
        area=area_match.group(1).strip() if area_match else None,
    )

    print(json.dumps({
        "systemMessage": f"{base}: all {len(boxes)} tasks checked off — status flipped to implemented.",
    }))


if __name__ == "__main__":
    main()
