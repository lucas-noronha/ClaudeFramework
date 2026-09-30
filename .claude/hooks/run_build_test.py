"""SubagentStop gate: run this project's own build/test command.

In classic mode `settings.json` can hold the command literally, because
one `settings.json` serves one project — that's what Domain 1 resolves
`{{BUILD_TEST_CMD}}` into. Once a single shared `.claude/` backs several
target repos (ADR 0013), static text can't hold two projects' different
commands, so the shared wiring calls this instead and the command comes
from the project's committed `project-config.json` at runtime.

Exits with the command's own exit code, untouched: this is the
deterministic gate that blocks `SubagentStop` on a failing build or test
run, and swallowing a non-zero status would quietly turn the framework's
one hard quality gate into a no-op.

Unlike the fail-open read helpers it imports, a missing `build_test_cmd`
fails *loud* — on the one hook whose entire job is running that command,
its absence is a real misconfiguration, not something to skip silently.

`shell=True` is deliberate and no wider a trust boundary than today's:
the string comes from the project's own committed `project-config.json`,
written by /setup-framework from the developer's own answer, and lands in
exactly the shell slot `settings.json` puts it in now — where a real
command like `dotnet build && npm test` needs shell semantics to work at
all. No untrusted or session-supplied input reaches it.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _project_paths import read_project_config, resolve_project_root  # noqa: E402

CONFIG_KEY = "build_test_cmd"


def main() -> int:
    project = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    root = resolve_project_root(project)
    command = read_project_config(root).get(CONFIG_KEY)

    if not isinstance(command, str) or not command.strip():
        print(
            f"No `{CONFIG_KEY}` in {os.path.join(root, 'project-config.json')} — "
            "this project has no build/test command registered, so the "
            "deterministic gate can't run. Re-run /setup-framework to register "
            "it.",
            file=sys.stderr,
        )
        return 1

    # No capture: stdout/stderr are inherited so the build's own output
    # still streams into the session exactly as a literal command did.
    # cwd is the code repo, not the resolved subtree — the source to
    # build lives in the target repo, only its configuration doesn't.
    return subprocess.run(command.strip(), shell=True, cwd=project).returncode


if __name__ == "__main__":
    sys.exit(main())
