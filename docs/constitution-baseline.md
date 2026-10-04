---
doc_type: constitution-baseline
version: 1.0.0
status: active
context_budget: ~400 tokens
---

# Constitution — framework baseline (Principles I–V)

This is the **baseline layer** of the constitution (ADR 0018). It ships
with the framework, and every framework upgrade replaces it wholesale.
**Never edit it in an adopted project.** An organization's or project's
own non-negotiables go in `constitution.md` beside it, numbered from VI
onward. Edit this file only in the framework repository itself, bumping
`version` in the same change.

The layers, read top to bottom, each one adding to and never weakening
the one above:

1. **This file** — the framework baseline, upgraded with the framework.
2. **`constitution.md`** — the organization layer in a shared docs root
   (modes B/C), or this project's own layer (mode A). Amended through
   its own Governance section, never replaced by an upgrade.
3. **`<project-subtree>/constitution.md`** — modes B/C only, optional,
   one project's additions (ADR 0015).

## Core principles

**I. Never commit or embed a secret.** No API key, password, token,
connection string, or private key in code, committed config, comments,
logs, or commit messages. Secrets come from environment variables or a
secrets manager, never hardcoded, never pasted into a prompt in
cleartext.

**II. No sensitive data in logs or error output.** Credentials,
tokens, full payment details, and regulated personal data are never
written to logs, stack traces, or error responses sent to a client.
Reference an ID instead of the raw value when tracing needs one.

**III. Validate at trust boundaries.** Input crossing in from outside
the system (HTTP request, upload, webhook, queue message) is validated
and sanitized at the boundary, before it reaches a query, a shell
command, or a template renderer.

**IV. Least privilege by default.** New code requests only the access
or scope it needs right now — never a broader credential "to be safe"
or "for later."

**V. Dependencies are vetted before they're added.** A new third-party
package is checked for maintenance status and known vulnerabilities
before it lands in the project; a dependency nothing uses anymore is
removed, not left "in case."
