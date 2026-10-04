---
doc_type: adr
id: 0010
status: accepted
date: {{DATE}}
supersedes: null
superseded_by: null
context_budget: ~700 tokens
---

# ADR 0010 — Give `docs/constitution.md` technical teeth, none of it gated on the file existing

Like ADR 0001–0009, this documents a decision about *this framework's
own* tooling (kept as a worked example).

## Context

ADR 0007 made `docs/constitution.md` supreme and checked by `/spec`,
`/plan`, `coder`/`quickfix`, and `reviewer` — but "checked" there meant
an agent's own judgment when reading the file, nothing mechanical. A
violation (a hardcoded secret, an unvetted dependency) could still slip
through if an agent simply didn't think to look. Raised directly as a
follow-up: give the same principles real detection, not just a prompt
asking an agent to remember them — while keeping the explicit
constraint that none of it should require `docs/constitution.md` to
exist, since not every project adopting this framework will have
written one yet.

## Options considered

- **A real secrets scanner (gitleaks/trufflehog) as the hook.**
  Rejected as the *only* option — it's a real dependency a fresh
  project wouldn't have installed yet, and this framework's own hooks
  are otherwise stdlib-only (see `context_budget_check.py`'s own
  rationale for the same trade-off). Left as a documented upgrade path
  in the shipped hook's docstring instead of a hard requirement.
- **A generic "secret/token/key = long string" regex, blocking.**
  Rejected — this framework's own `{{PLACEHOLDER}}` and `.example`
  conventions would trip it constantly; a hook noisy enough to fight
  the project's own scaffolding trains people to stop reading its
  denials, which defeats the point.
- **High-confidence structural patterns only (real key formats, a
  private-key header), hard-blocked via `PreToolUse`; everything else
  left to `security-review` at the reviewer/coder layer; dependency
  vetting left to a project-supplied audit command like
  `{{BUILD_TEST_CMD}}` (chosen).**

## Decision

- **`secret_leak_guard.py`** (new, active by default — no `.example`
  suffix, stdlib-only): `PreToolUse` on any `Edit`/`Write`, denies when
  the new content matches a high-confidence credential pattern (AWS key
  ID, GitHub/Slack tokens, a private-key block). Never reads
  `docs/constitution.md`; works identically whether or not the file
  exists.
- **`dependency_audit.py.example`** (new, needs a real project command
  like `auto_format.py.example` already does): `PostToolUse`, no-ops
  unless the touched file is a recognized dependency manifest
  (`package.json`, `requirements.txt`, the solution file, `Cargo.toml`,
  `go.mod`), then runs that ecosystem's audit command and reports
  findings as a `systemMessage`. Same reasoning: never reads
  `docs/constitution.md`.
- **`security-review` skill wired into `reviewer` and `coder`**: for a
  security-sensitive diff (auth, secrets/credentials, input handling),
  both now invoke it as a complementary pass, same posture as the
  existing `code-review`/`pr-review-toolkit` invocation. When
  `docs/constitution.md` exists, a finding that maps to one of its Core
  Principles is folded into the verdict under that principle's name;
  when it doesn't exist, the skill still runs and still counts — its
  value doesn't depend on that file.

## Rationale

Splits the "give it teeth" goal by how confidently each concern can be
checked without external tooling or project context: credential
*format* is checkable with zero false positives via stdlib regex, so it
hard-blocks; credential *vetting quality* and dependency vulnerabilities
both need real tools or judgment this framework can't ship generically,
so they're a `.example` slot and a skill invocation respectively, not a
guess dressed up as certainty. Keeps the "hard guard vs. nudge vs.
project-supplied command" split this framework already uses elsewhere
(ADR 0001, `context_budget_check.py`'s own docstring) instead of
inventing a fourth category.

## Consequences

- `secret_leak_guard.py` runs on **every** `Edit`/`Write`, repo-wide —
  the broadest-scoped hook this framework ships. A false positive on a
  genuine non-secret is possible (an oddly-shaped test fixture, say);
  the denial message says exactly how to work around it (rephrase past
  the pattern), so it's a friction cost, not a hard wall.
- `dependency_audit.py.example` needs the same one-time fill-in
  `auto_format.py.example` already needs — `/setup-framework` Domain 1
  now covers both, not just the formatter.
- Neither hook, nor the `security-review` wiring, requires
  `docs/constitution.md` to exist — a project that skips writing one
  still gets all three; the file only adds the "map the finding to a
  named principle" framing on top, nothing is gated on its presence.
- Coverage stays deliberately partial: `secret_leak_guard.py`'s pattern
  list is a starting set (five formats), not exhaustive — a project
  with a different cloud provider's key format gets no protection until
  someone adds it, or the project swaps in a real scanner per the
  hook's own docstring.

## References

`.claude/hooks/secret_leak_guard.py`,
`.claude/hooks/dependency_audit.py.example`, `.claude/agents/reviewer.md`,
`.claude/agents/coder.md`, `docs/decisions/0007-constitution-document.md`
