"""PreToolUse (Bash|PowerShell): inside a subagent, allow only read-only
git (framework spec 0007 FR-10/FR-12, ADR 0025 section 5).

Parallel subagents share one working tree, so a subagent that runs a
tree-changing git command (checkout, reset, stash, commit, ...) can wipe
a sibling's uncommitted work. The main session is never affected: the
hook payload only carries `agent_id`/`agent_type` for a subagent's call.

Stateless and fail-open:
  - no `agent_id`/`agent_type`, no `command`, or no `git` token: allow at
    once, before any file is read (the shared helper is imported lazily,
    on the deny path only);
  - unbalanced quotes, a parser exception or an unrecognized shape: allow;
  - `hook_should_run` is asked only when about to deny, so an unregistered
    mode C repo is never blocked.

It guards against accidents, not adversaries: shapes it doesn't parse
(`xargs git ...`, variable expansion, deeper nesting) are allowed.
"""
import json
import os
import re
import sys

GIT_TOKEN = re.compile(r"(?i)(?<![\w-])git(?:\.exe)?(?![\w-])")

ALWAYS_ALLOWED = {
    "status", "diff", "log", "show", "rev-parse", "ls-files", "check-ignore",
    "blame", "grep", "cat-file", "describe",
}
READ_FORMS = {"worktree": {"list"}, "stash": {"list", "show"}}

# git global options that take a separate argument when written without `=`.
GLOBAL_WITH_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}

# `branch`/`tag` listing: short flag letters and long flags that mutate.
# (`branch -a` lists all branches; `tag -a`/`-s` create a tag; `-v` only verifies.)
MUTATING_SHORT = {
    "branch": set("dDmMcCfu"),
    "tag": set("dafsumF"),
}
MUTATING_LONG = {
    "--delete", "--move", "--copy", "--force", "--set-upstream-to",
    "--unset-upstream", "--edit-description", "--set-upstream", "--create-reflog",
}
LISTING_OPTS_WITH_ARG = {
    "--contains", "--no-contains", "--merged", "--no-merged", "--points-at",
    "--sort", "--format", "--column",
}

PREFIX_WORDS = {"env", "command", "exec", "nohup", "time", "sudo"}
POSIX_SHELLS = {"bash", "sh", "zsh", "dash"}
POWERSHELLS = {"powershell", "pwsh"}


def split_segments(command: str):
    """Split on `&&`, `||`, `;`, `|`, `&`, newlines and parentheses, outside
    quotes. A `&` inside a redirection (`2>&1`, `&>`) is not a separator.
    Raises ValueError on an unbalanced quote.
    """
    segments, current, quote, i, n = [], [], None, 0, len(command)
    while i < n:
        ch = command[i]
        if quote:
            current.append(ch)
            if ch == "\\" and quote == '"' and i + 1 < n:
                current.append(command[i + 1])
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            current.append(ch)
        elif ch == "&" and ((i > 0 and command[i - 1] in "<>") or (i + 1 < n and command[i + 1] in "<>")):
            current.append(ch)
        elif ch in ";|&\n\r()":
            segments.append("".join(current))
            current = []
        else:
            current.append(ch)
        i += 1
    if quote:
        raise ValueError("unbalanced quote")
    segments.append("".join(current))
    return [s for s in segments if s.strip()]


def tokenize(segment: str):
    """Whitespace tokens with both quote styles removed. Backslashes stay
    literal (Windows paths), except an escaped quote inside double quotes.
    """
    tokens, current, quote, has = [], [], None, False
    i, n = 0, len(segment)
    while i < n:
        ch = segment[i]
        if quote:
            if ch == "\\" and quote == '"' and i + 1 < n and segment[i + 1] in '"\\':
                current.append(segment[i + 1])
                i += 1
            elif ch == quote:
                quote = None
            else:
                current.append(ch)
        elif ch in "'\"":
            quote, has = ch, True
        elif ch.isspace():
            if has or current:
                tokens.append("".join(current))
                current, has = [], False
        else:
            current.append(ch)
        i += 1
    if quote:
        raise ValueError("unbalanced quote")
    if has or current:
        tokens.append("".join(current))
    return tokens


def program_name(token: str) -> str:
    name = re.split(r"[\\/]", token)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def is_assignment(token: str) -> bool:
    return re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", token) is not None


def branch_or_tag_is_listing(sub: str, args) -> bool:
    listing = any(a in ("-l", "--list") for a in args)
    skip = False
    for arg in args:
        if skip:
            skip = False
            continue
        if arg.startswith("--"):
            flag = arg.split("=", 1)[0]
            if flag in MUTATING_LONG:
                return False
            if flag in LISTING_OPTS_WITH_ARG and "=" not in arg:
                skip = True
        elif arg.startswith("-") and len(arg) > 1:
            if set(arg[1:]) & MUTATING_SHORT[sub]:
                return False
        elif not listing:
            return False  # a positional name creates a branch or tag
    return True


def git_violation(args):
    """None when `args` (everything after the `git` word) is read-only,
    else the offending subcommand text.
    """
    i = 0
    while i < len(args) and args[i].startswith("-"):
        takes_arg = args[i] in GLOBAL_WITH_ARG
        i += 2 if takes_arg else 1
    rest = args[i:]
    if not rest:
        return None  # bare `git`, `git --version`, `git --help`
    sub, tail = rest[0], rest[1:]
    if sub in ALWAYS_ALLOWED:
        return None
    if sub in READ_FORMS:
        first = next((a for a in tail if not a.startswith("-")), None)
        return None if first in READ_FORMS[sub] else sub + (" " + first if first else "")
    if sub in ("branch", "tag"):
        return None if branch_or_tag_is_listing(sub, tail) else sub + " (mutating form)"
    return sub


def check(command: str, depth: int = 0):
    """The first offending `git ...` text in `command`, or None."""
    for segment in split_segments(command):
        tokens = tokenize(segment)
        while tokens and (is_assignment(tokens[0]) or program_name(tokens[0]) in PREFIX_WORDS):
            tokens.pop(0)
        if not tokens:
            continue
        name = program_name(tokens[0])
        if name == "git":
            bad = git_violation(tokens[1:])
            if bad is not None:
                return "git " + bad
        elif depth == 0 and len(tokens) > 2 and name in POSIX_SHELLS | POWERSHELLS | {"cmd"}:
            flags = {"-c", "-command", "/c"}
            for idx, tok in enumerate(tokens[1:], start=1):
                if tok.lower() in flags:
                    found = check(" ".join(tokens[idx + 1:]), depth + 1)
                    if found:
                        return found
                    break
    return None


def read_payload() -> dict:
    try:
        raw = sys.stdin.buffer.read()
        data = json.loads(raw.decode("utf-8-sig") or "{}")
    except (AttributeError, OSError, UnicodeDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def main() -> None:
    try:
        data = read_payload()
        if not (data.get("agent_id") or data.get("agent_type")):
            return
        tool_input = data.get("tool_input")
        command = tool_input.get("command") if isinstance(tool_input, dict) else None
        if not isinstance(command, str) or not GIT_TOKEN.search(command):
            return
        offending = check(command)
    except Exception:  # fail open (NFR-02)
        return
    if offending is None:
        return

    # Deny path only: the registration gate (framework ADR 0017) reads files.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _project_paths import hook_should_run  # noqa: E402
    if not hook_should_run(os.environ.get("CLAUDE_PROJECT_DIR", ".")):
        return

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"Read-only git inside a subagent (framework spec 0007 FR-10): `{offending}` "
                "can change the working tree shared with parallel subagents. Allowed: status, "
                "diff, log, show, rev-parse, ls-files, check-ignore, blame, grep, cat-file, "
                "describe, worktree list, stash list/show, branch/tag as listings. Don't run it "
                "- report the command in your final message so the main session runs it. To "
                "compare against a baseline use `git show HEAD:<path>` or `git diff -- <paths>`."
            ),
        }
    }))


if __name__ == "__main__":
    main()
