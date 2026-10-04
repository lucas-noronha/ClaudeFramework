"""SessionStart: deterministically flag when the repo's dominant
language has an official marketplace LSP plugin that isn't enabled
globally. Zero LLM cost — a suggestion only, never a block. Extend
LANGUAGE_PLUGINS the day the official marketplace ships another
language's LSP; this can't discover that on its own.

Respects a per-machine dismiss list (DISMISS_FILE) so a plugin the user
already declined via /setup-framework doesn't nag on every session —
without it, this would become noise the moment someone deliberately
chooses not to install something.
"""
import json
import os
import subprocess
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _project_paths import hook_should_run, state_file_path  # noqa: E402

MIN_FILES = 3  # ignore a handful of incidental files of a language
DISMISS_FILENAME = ".plugin-gap-dismissed.json"  # per-machine, gitignored

LANGUAGE_PLUGINS = {
    ".cs": "csharp-lsp",
    ".ts": "typescript-lsp",
    ".tsx": "typescript-lsp",
}


def dismissed_plugins(project: str) -> set:
    # Per-project state: a shared `.claude/` would otherwise let one
    # target repo's dismissal silence the suggestion for all of them.
    try:
        with open(state_file_path(project, DISMISS_FILENAME), encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("dismissed", []))
    except Exception:
        return set()


def list_project_files(project: str):
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=project, capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.splitlines()
    except Exception:
        pass

    files = []
    skip_dirs = {".git", "node_modules", "bin", "obj", "dist", "build", "venv", ".venv"}
    for root, dirs, filenames in os.walk(project):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for name in filenames:
            files.append(os.path.join(root, name))
    return files


def enabled_plugins() -> set:
    settings_path = os.path.expanduser(os.path.join("~", ".claude", "settings.json"))
    try:
        with open(settings_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return set()

    enabled = data.get("enabledPlugins", {})
    return {name.split("@", 1)[0] for name, is_on in enabled.items() if is_on}


def main() -> None:
    # Registration gate (framework ADR 0017): a no-op for an unregistered repo under
    # a user-level install; always open in modes A/B.
    if not hook_should_run(os.environ.get("CLAUDE_PROJECT_DIR", ".")):
        return

    project = os.environ.get("CLAUDE_PROJECT_DIR", ".")

    try:
        counts = Counter()
        for path in list_project_files(project):
            _, ext = os.path.splitext(path)
            if ext in LANGUAGE_PLUGINS:
                counts[ext] += 1

        already_enabled = enabled_plugins()
        already_dismissed = dismissed_plugins(project)

        missing = []
        seen_plugins = set()
        for ext, count in counts.items():
            if count < MIN_FILES:
                continue
            plugin = LANGUAGE_PLUGINS[ext]
            if plugin in already_enabled or plugin in already_dismissed or plugin in seen_plugins:
                continue
            seen_plugins.add(plugin)
            missing.append(f"{plugin} ({count} {ext} files)")

        if not missing:
            return

        message = (
            "Optional plugin(s) matching this repo's language aren't enabled "
            "globally: " + ", ".join(missing) + ". Run /setup-framework to review, "
            "install, or dismiss so this stops asking."
        )
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": message,
            }
        }))
    except Exception:
        return  # never block session start over a best-effort suggestion


if __name__ == "__main__":
    main()
