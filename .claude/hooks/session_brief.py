"""SessionStart: inject a short, deterministic status brief (git
status + specs still in flight (not `implemented` or `abandoned`) +
the last session's handoff note, if any) so Claude doesn't have to
spend tool calls re-discovering it at the start of every session.
"""
import glob
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _project_paths import resolve_docs_root, state_file_path  # noqa: E402

HANDOFF_CHAR_LIMIT = 800  # bound the cost of a stale/verbose last_assistant_message


def main() -> None:
    project = os.environ.get("CLAUDE_PROJECT_DIR", ".")

    # git status is about the *code* repo, so it stays on CLAUDE_PROJECT_DIR;
    # the handoff note and the specs are project content, which lives in
    # the resolved subtree once this session is registered (ADR 0013).
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=project, capture_output=True, text=True, timeout=10,
        )
        git_status = result.stdout.strip()
    except Exception:
        git_status = ""

    handoff = ""
    handoff_path = state_file_path(project, "session-handoff.md")
    try:
        with open(handoff_path, encoding="utf-8") as f:
            raw = f.read()
        body = re.sub(r"^(<!--.*?-->\n?)+", "", raw, flags=re.DOTALL).strip()
        if body:
            handoff = body[:HANDOFF_CHAR_LIMIT]
            if len(body) > HANDOFF_CHAR_LIMIT:
                handoff += " [...]"
    except FileNotFoundError:
        pass

    pending = []
    specs_dir = os.path.join(resolve_docs_root(project), "product", "specs")
    for path in sorted(glob.glob(os.path.join(specs_dir, "*.md"))):
        if ".validation-" in os.path.basename(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                head = f.read(500)
        except Exception:
            continue
        match = re.search(r"^status:\s*(.+)$", head, re.MULTILINE)
        status = match.group(1).strip() if match else ""
        if status and status not in ("implemented", "abandoned"):
            pending.append(f"{os.path.basename(path)}: {status}")

    lines = [
        "Git status: " + (git_status if git_status else "(clean)"),
        "Specs not yet implemented: " + ("; ".join(pending) if pending else "(none)"),
    ]
    if handoff:
        lines.append("Last session's handoff note: " + handoff)

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n".join(lines),
        }
    }))


if __name__ == "__main__":
    main()
