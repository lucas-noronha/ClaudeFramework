"""PreToolUse: block an Edit/Write whose new content matches a
high-confidence secret pattern (cloud/VCS/chat-provider credential
formats, a private-key block). Zero external dependency, stdlib-only
regex — works out of the box, unlike a real scanner (gitleaks,
trufflehog, secretlint), which a project can still swap into this same
hook slot for deeper coverage (entropy-based detection, provider-
specific rules) once it has one available. This mechanically enforces
`docs/constitution.md`'s Principle I where that file exists, and is
good practice on its own where it doesn't — it never reads or requires
that file, so nothing here depends on it being present.

Deliberately conservative: only patterns with a near-zero false-positive
rate hard-block (a real key format, a private-key header). A generic
"secret/token/key = long string" assignment is common in legitimate
scaffolding (this very framework's own `{{PLACEHOLDER}}` convention,
`.example` files) — flagging that reliably needs project context this
hook doesn't have, so it's deliberately left out rather than shipped
noisy enough to train someone to ignore it.
"""
import json
import os
import re
import sys

SECRET_PATTERNS = [
    ("AWS access key ID", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("AWS secret access key assignment", re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*['\"][A-Za-z0-9/+=]{40}['\"]")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("GitHub fine-grained PAT", re.compile(r"github_pat_[A-Za-z0-9_]{22,}")),
    ("Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("Private key block", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
]


def main() -> None:
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input", {})
    text = tool_input.get("content")
    if text is None:
        text = tool_input.get("new_string", "")
    if not text:
        return

    for label, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"This write matches a {label} pattern — looks like a real credential "
                        "about to be committed, not a placeholder. Move it to an environment "
                        "variable or secrets manager instead (docs/constitution.md Principle I, "
                        "if this project has one). If this is a genuine false positive, "
                        "rephrase the string so it no longer matches the pattern in "
                        ".claude/hooks/secret_leak_guard.py."
                    ),
                }
            }))
            return


if __name__ == "__main__":
    main()
