---
doc_type: constitution
version: 1.0.0
ratified: {{DATE}}
last_amended: {{DATE}}
status: active
context_budget: ~500 tokens
---

# Project constitution

This document is supreme: no spec, technical plan, or code may
knowingly contradict a principle below. It is loaded before `/spec`,
`/plan`, `coder`/`quickfix`, and `reviewer` do their work — if a
request conflicts with a principle here, that conflict gets flagged
explicitly (back to the human, or into a deliberate amendment of this
file) instead of quietly worked around. Unlike an ADR, this file isn't
frozen once accepted — it's amended over the project's life, but only
through the versioned procedure in **Governance** below, never a
silent edit. `constitution_amendment_check.py` nudges (never blocks)
when the content changes without `version`/`last_amended` moving too.

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

**VI. — add your project's own non-negotiable here.** (placeholder —
a business invariant, a compliance rule, a tenancy boundary — whatever
this project can never silently violate; delete this line once you've
written a real one, or leave it as an explicit "none yet")

## Standards this pipeline already enforces for you

The deterministic build/test gate, `reviewer`'s checklist, and this
project's own `docs/architecture/` docs cover code quality and
structure — this file doesn't repeat those, only the handful of things
worth being non-negotiable regardless of architecture or stack.

## Governance

- **Amendment procedure**: a change to this file bumps `version`
  (semver) and `last_amended` in the same edit. **MAJOR** — a
  principle is removed or redefined in a way that changes what's
  allowed. **MINOR** — a new principle or section is added. **PATCH**
  — wording/clarification only, no behavioral change.
- Every amendment states its reason in the commit or PR that carries
  it — this file has no changelog section of its own to avoid
  duplicating what git history already holds.
- This is deliberately not a hard technical gate (see
  `docs/decisions/0007-constitution-document.md` for why): an agent
  can still get it wrong, same trust model the rest of this pipeline
  already runs on for architecture docs and ADRs.
