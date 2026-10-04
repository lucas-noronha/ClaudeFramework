"""PostToolUse (Edit/Write): run a project's own formatter and dependency
audit, as declared in its config — the per-project opt-in that replaces
`auto_format.py`/`dependency_audit.py` wherever one set of hooks serves
several projects (framework ADR 0017, framework spec 0001 FR-07/D8).

Those two `.example` hooks are per-project by nature: their commands
name one stack's formatter and one solution file. In a shared install
they can't be resolved into machinery every project runs, and they
blocked mode C's setup on a prerequisite that couldn't apply. This hook
is the shared, generic half. Each project opts in through its own config
(`project-config.json`, or `.claude/project-config.json` in mode A):

    "project_tools": {
      "format": [
        {"glob": "src/*.cs", "command": "dotnet format whitespace --include {file}"}
      ],
      "dependency_audit": [
        {"manifest": "package.json", "command": "npm audit --omit=dev"},
        {"manifest": "*.csproj", "command": "dotnet list {file} package --vulnerable"}
      ]
    }

`glob` is matched against the edited file's path relative to the repo
(fnmatch, so `*` also crosses `/`); `manifest` against its basename.
`{file}` becomes the edited file's absolute path, double-quoted. No
`project_tools` key means nothing runs: absent config is opt-out, not an
error.

Best-effort like the hooks it replaces. A formatter failure is ignored,
and an audit's non-zero exit is reported as a systemMessage, never a
block. `shell=True` carries the same trust boundary as `build_test_cmd`:
the command comes from the project's own config, written by its
developer.
"""
import fnmatch
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _project_paths import hook_should_run, load_project_config, normalize, read_hook_input  # noqa: E402

FORMAT_TIMEOUT = 60
AUDIT_TIMEOUT = 120


def _command(template: str, abspath: str) -> str:
    return template.replace("{file}", f'"{abspath}"')


def main() -> None:
    project = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    if not hook_should_run(project):
        return

    data = read_hook_input()
    path = data.get("tool_input", {}).get("file_path", "") or data.get("tool_response", {}).get("filePath", "")
    if not path:
        return

    tools = load_project_config(project).get("project_tools")
    if not isinstance(tools, dict):
        return

    abspath = path if os.path.isabs(path) else os.path.join(project, path)
    try:
        rel = normalize(os.path.relpath(abspath, project))
    except ValueError:
        return
    if rel.startswith("../"):
        return  # not this repo's code (e.g. a doc in the project subtree)

    for entry in tools.get("format") or []:
        if isinstance(entry, dict) and entry.get("command") and fnmatch.fnmatch(rel, entry.get("glob", "")):
            try:
                subprocess.run(_command(entry["command"], abspath), shell=True, cwd=project,
                               timeout=FORMAT_TIMEOUT, capture_output=True)
            except (OSError, subprocess.SubprocessError):
                pass

    basename = os.path.basename(abspath)
    reports = []
    for entry in tools.get("dependency_audit") or []:
        if not (isinstance(entry, dict) and entry.get("command") and fnmatch.fnmatch(basename, entry.get("manifest", ""))):
            continue
        command = _command(entry["command"], abspath)
        try:
            result = subprocess.run(command, shell=True, cwd=project, timeout=AUDIT_TIMEOUT,
                                    capture_output=True, text=True)
        except (OSError, subprocess.SubprocessError):
            continue  # audit tool missing — never block the turn over it
        if result.returncode != 0:
            tail = (result.stdout or result.stderr or "")[-800:]
            reports.append(f"Dependency audit ({command}) flagged something after {basename} changed:\n{tail}")

    if reports:
        print(json.dumps({"systemMessage": "\n\n".join(reports)}))


if __name__ == "__main__":
    main()
