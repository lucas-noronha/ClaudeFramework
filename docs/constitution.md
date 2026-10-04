---
doc_type: constitution
version: 2.0.0
ratified: {{DATE}}
last_amended: {{DATE}}
status: active
context_budget: ~450 tokens
---

# Constitution

This document is supreme: no spec, technical plan, or code may
knowingly contradict a principle below **or in
`constitution-baseline.md`**, the framework's baseline layer (Principles
I–V) that this file extends (ADR 0018). Both are loaded before `/spec`,
`/plan`, `coder`/`quickfix`, and `reviewer` do their work. If a request
conflicts with a principle in either, that conflict gets flagged
explicitly (back to the human, or into a deliberate amendment of this
file) instead of quietly worked around.

This file is the **organization layer**: in a shared docs root (modes
B/C) it binds every project; in mode A it is this project's own layer.
A framework upgrade never touches it. It may only add to the baseline,
never weaken or contradict it. Unlike an ADR, this file isn't frozen
once accepted — it's amended over its life, but only through the
versioned procedure in **Governance** below, never a silent edit.
`constitution_amendment_check.py` nudges (never blocks) when the content
changes without `version`/`last_amended` moving too.

## Core principles

Principles I–V live in `constitution-baseline.md`. Number this layer's
own from VI.

**VI. — add your organization's (or project's) own non-negotiable
here.** (placeholder — a business invariant, a compliance rule, a
tenancy boundary — whatever can never be silently violated; delete this
line once you've written a real one, or leave it as an explicit "none
yet")

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
- Never move a principle into `constitution-baseline.md` to "promote"
  it: that file is replaced on every framework upgrade, and the
  principle would be lost. A principle worth having in every adopter's
  baseline is a change to the framework repository itself.
- This is deliberately not a hard technical gate (see
  `docs/decisions/0007-constitution-document.md` for why): an agent
  can still get it wrong, same trust model the rest of this pipeline
  already runs on for architecture docs and ADRs.
