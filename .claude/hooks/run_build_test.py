"""SubagentStop gate: run this project's own build/test command — but
only when the subagent that just stopped can have changed code (spec
0003 FR-02, ADR 0020).

Where the command comes from: in modes B/C one shared `settings.json`
serves several projects (ADR 0013), so static text can't hold their
different commands; the command is read at runtime from the project's
`project-config.json` (the optional `.claude/project-config.json` in
mode A, ADR 0020).

Which stops run it. Before ADR 0020 every `SubagentStop` ran the full
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

Exits with the command's own exit code, untouched: swallowing a non-zero
status would quietly turn the framework's one hard quality gate into a
no-op. A missing `build_test_cmd` still fails loud — on the one hook
whose entire job is running that command, its absence is a real
misconfiguration.

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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _pipeline_metrics import log_event  # noqa: E402
from _project_paths import (  # noqa: E402
    framework_config,
    hook_should_run,
    load_project_config,
    normalize,
    project_config_path,
    read_hook_input,
    resolve_docs_root,
)

CONFIG_KEY = "build_test_cmd"
CODE_WRITER_ROLES = {"coder", "quickfix"}
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
# Built-in subagents that never change a project's code.
NON_CODE_BUILTINS = {"Explore", "Plan", "claude-code-guide", "statusline-setup", "output-style-setup"}


def role_of(agent_type: str) -> str:
    """`cfw-coder` → `coder`: strips an install prefix, so a user-level
    install's renamed agents still match (ADR 0017).
    """
    prefix = framework_config().get("prefix")
    if prefix and agent_type.startswith(prefix + "-"):
        return agent_type[len(prefix) + 1:]
    return agent_type


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

    if agent_type in NON_CODE_BUILTINS or (agent_type and _agent_definition_is_read_only(project, agent_type)):
        return False, f"{agent_type} is read-only"
    return True, "could not tell whether code changed"


def main() -> int:
    # Registration gate (ADR 0017): a no-op for an unregistered repo under
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

    # No capture: stdout/stderr are inherited so the build's own output
    # still streams into the session exactly as a literal command did.
    # cwd is the code repo, not the resolved subtree — the source to
    # build lives in the target repo, only its configuration doesn't.
    returncode = subprocess.run(command.strip(), shell=True, cwd=project).returncode
    log_event(
        project, "gate_run",
        agent_type=data.get("agent_type") or data.get("subagent_type"),
        reason=reason, exit_code=returncode,
    )
    return returncode


if __name__ == "__main__":
    sys.exit(main())
