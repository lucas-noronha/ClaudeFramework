"""Shared helper for the subagent-aware hooks (pipeline_metrics.py,
run_build_test.py) — framework ADR 0025. Not a hook entry point, not wired
in settings.json: imported, like `_spec_layout.py`.

Holds the role resolution, the gate's read-only rule (moved here
unchanged from run_build_test.py) and the generic transcript readers.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _project_paths import framework_config  # noqa: E402

WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
# Built-in subagents that never change a project's code.
NON_CODE_BUILTINS = {"Explore", "Plan", "claude-code-guide", "statusline-setup", "output-style-setup"}


def role_of(agent_type: str) -> str:
    """`cfw-coder` → `coder`: strips an install prefix, so a user-level
    install's renamed agents still match (framework ADR 0017).
    """
    prefix = framework_config().get("prefix")
    if prefix and agent_type.startswith(prefix + "-"):
        return agent_type[len(prefix) + 1:]
    return agent_type


def _agent_definition_is_read_only(project: str, agent_type: str) -> bool:
    config = framework_config()
    candidates = [os.path.join(project, ".claude", "agents", agent_type + ".md")]
    if config.get("config_dir"):
        candidates.append(os.path.join(config["config_dir"], "agents", agent_type + ".md"))
    candidates.append(os.path.expanduser(os.path.join("~", ".claude", "agents", agent_type + ".md")))
    for candidate in candidates:
        try:
            with open(candidate, encoding="utf-8") as f:
                head = f.read(2000)
        except OSError:
            continue
        fm = re.match(r"^---\n(.*?)\n---", head, re.DOTALL)
        tools = re.search(r"^tools:\s*(.+)$", fm.group(1), re.MULTILINE) if fm else None
        if not tools:
            return False  # no tools line = inherits every tool, including writes
        listed = {t.strip() for t in tools.group(1).split(",")}
        return not (listed & (WRITE_TOOLS | {"Bash"}))
    return False


def is_read_only(project: str, agent_type: str) -> bool:
    """A built-in known not to change code, or an agent definition whose
    `tools:` list has no write-capable tool.
    """
    return agent_type in NON_CODE_BUILTINS or bool(agent_type and _agent_definition_is_read_only(project, agent_type))


def read_jsonl(path, tail_bytes=None) -> list:
    """Records of a JSONL transcript, bad lines skipped; `[]` when it can't
    be read. With `tail_bytes`, only the end of the file is read (the
    first, possibly partial, line of that window is dropped).
    """
    try:
        with open(path, "rb") as f:
            partial = False
            if tail_bytes:
                size = f.seek(0, os.SEEK_END)
                if size > tail_bytes:
                    f.seek(size - tail_bytes)
                    partial = True
                else:
                    f.seek(0)
            raw = f.read()
    except (OSError, TypeError, ValueError):
        return []
    lines = raw.decode("utf-8", errors="replace").split("\n")
    lines = [line.rstrip("\r") for line in lines]
    if partial and lines:
        lines = lines[1:]
    records = []
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


HANDBACK_TOOL = "SubagentHandback"


def _block_text(item) -> str:
    """A text block's text, or the report a subagent hands back through the
    `SubagentHandback` tool (its `input.message`) — some harnesses end a
    subagent that way instead of with a final text message."""
    if not isinstance(item, dict):
        return ""
    if item.get("type") == "text":
        return str(item.get("text") or "")
    if item.get("type") == "tool_use" and item.get("name") == HANDBACK_TOOL:
        return str((item.get("input") or {}).get("message") or "")
    return ""


def _text_of(record: dict) -> str:
    """Text of one record's message (string, `[{type: text}]`, or a
    `SubagentHandback` tool call's message)."""
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(t for t in (_block_text(item) for item in content) if t)
    return ""


def last_assistant_text(records: list) -> str:
    """The final reply: the text of the last `assistant` record that has
    text, joined in order with the other records sharing its `message.id`.
    `""` when there is none.
    """
    last = None
    for record in records:
        if record.get("type") == "assistant" and _text_of(record).strip():
            last = record
    if last is None:
        return ""
    message_id = (last.get("message") or {}).get("id")
    if not message_id:
        return _text_of(last)
    parts = [
        _text_of(r) for r in records
        if r.get("type") == "assistant" and (r.get("message") or {}).get("id") == message_id
    ]
    return "\n".join(p for p in parts if p)


def first_user_text(records: list) -> str:
    """Text of the first `user` record that has any; `""` when none."""
    for record in records:
        if record.get("type") == "user":
            text = _text_of(record)
            if text.strip():
                return text
    return ""
