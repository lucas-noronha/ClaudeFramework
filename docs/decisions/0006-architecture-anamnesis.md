---
doc_type: adr
id: 0006
status: proposed
date: {{DATE}}
supersedes: null
superseded_by: null
context_budget: ~1000 tokens
---

# ADR 0006 — `/setup-framework` may draft the architecture blank slots from detected patterns, never finalize them silently

Like ADR 0001–0005, this documents a decision about *this framework's
own* tooling (kept as a worked example).

## Context

This framework deliberately ships `docs/architecture/module-structure.md`
and `frontend.md` as blank slots. This repository's own `README.md`
records *why*, under "What's new here" — an earlier generalization pass
shipped these pre-filled with the source project's actual pattern
(layered modules, a facade-based frontend), plus matching example
skills; on reflection, both were removed because they baked one
project's architecture opinions into a template meant to work for any
architecture or stack. `/setup-framework`'s Domain 1 (step 6) enforces
the same restraint today: it explicitly refuses to guess these files'
content from a file scan.

In practice, though, most real adoptions of this framework land on an
**existing** codebase, not a green field — the codebase already has
real, discoverable structure (folder conventions, a layering pattern,
an observable dependency direction) that a human then has to describe
from scratch by hand, in prose, from memory. That's exactly the kind of
"re-derive knowledge a scan could surface faster" cost this framework's
own context-economy principle (`docs/workflow/ai-first-development.md`)
argues against elsewhere.

## Options considered

- **Leave both files as blank slots, human writes from scratch (status
  quo).** Respects the "don't presume architecture" principle to the
  letter, but leaves real, already-observable information undiscovered
  until a human manually documents it.
- **Auto-fill and finalize these files from detection.** Rejected —
  this is the exact mistake this framework already reversed once: a
  detection heuristic can misread an accidental pattern as an
  intentional rule, and `coder`/`reviewer` would then trust a wrong
  rule mechanically, with nothing prompting a human to catch it.
- **Add an optional step that drafts these files from detected
  patterns, explicitly marked for human review, never silently
  finalized (chosen).** Gets the speed benefit of automated pattern
  recognition across many files — something an agent is fast at and a
  human tediously is not — without repeating the earlier mistake. The
  safeguard is the "draft, not final" framing itself, not the accuracy
  of the detection: this framework already trusts that exact pattern
  elsewhere (`/adr` drafts `status: proposed` and is never allowed to
  self-accept; ADR immutability requires a human act to move past
  `proposed`).

## Decision

- New **Domain 4 — Architecture anamnesis** in `/setup-framework`,
  positioned after Domain 1 (needs the resolved `{{BACKEND_DIR}}`/
  `{{FRONTEND_DIR}}` placeholders first). Runs only if
  `module-structure.md.template`/`frontend.md.template` are still
  untouched — skip entirely, never overwrite, if a human already wrote
  real content into either.
- Ask first whether to run it at all: it reads a real slice of the
  existing codebase (a genuine token cost) and is pointless on a
  scaffold with no code yet to describe.
- Detect, per side that exists (`{{BACKEND_DIR}}`/`{{FRONTEND_DIR}}` or
  a non-monorepo root): the top-level layout and naming conventions
  (e.g. `controllers`/`services`/`repositories`, feature folders,
  `components`/`pages`), and a **sample** (not exhaustive — a handful
  of representative files, not every file) check of actual import
  direction between the detected layers, enough to state a rule with
  cited examples, not prove it exhaustively.
- Draft the real content of `module-structure.md`/`frontend.md`'s
  "Layout" / "Dependency rules" / "Where new code goes" sections from
  what was found, citing example files as evidence for each claim, and
  rename `.template` → `.md` at this point (same rename-not-copy
  convention as Domain 1). Prepend a clearly marked banner: *"Detected
  automatically from existing code on `{{DATE}}` — read fully and
  correct anything wrong before trusting this; `coder` and `reviewer`
  treat this file as ground truth."*
- If the repo is a genuine green field with no discernible pattern yet,
  skip and say so plainly — the original blank-slot, fill-by-hand
  behavior is untouched.
- The close-out summary (`## Close`) changes conditionally: if Domain 4
  ran and drafted content, it says so and asks for a human read-through
  before the first `/spec`; if it didn't run (declined, or nothing to
  detect), the close-out keeps its original wording — these are still
  blank slots to fill by hand.

## Rationale

The part of the earlier, reversed decision that was actually unsafe was
presenting one **fixed** opinion as this framework's own shipped
default, trusted without review. This proposal never does that: it
inspects the **project's own actual code** and produces a
project-specific draft that is explicitly untrusted until a human reads
it — the same posture this framework already takes toward `/adr`'s own
drafts. It's a reapplication of an existing safeguard, not a new risk,
and it only fires on an existing codebase where there's something real
to detect.

## Consequences

- Domain 4 costs real tokens (reading a sample of the actual codebase)
  — worth it when adopting onto a non-trivial existing codebase, skip
  it (or answer no) on a green field.
- Detection can be wrong. The banner and the close-out message say so
  explicitly rather than implying the file is finished — a human must
  actually read it, not rubber-stamp it.
- If declined, skipped, or the files were already filled by hand,
  behavior is identical to before this ADR: Domain 1 step 6 and the
  original close-out wording still apply unchanged.
- `README.md`'s own "on reflection" retrospective note needs one
  follow-up line pointing at this ADR, so a future reader doesn't read
  that paragraph and conclude this ADR silently walked back its lesson
  — it applies the same lesson more carefully instead of ignoring it.

## References

`README.md` ("What's new here vs. the project this was extracted
from" — the retrospective note this ADR follows up on),
`.claude/commands/setup-framework.md`, `.claude/commands/adr.md` (the
draft/never-self-accept pattern being reused),
`docs/architecture/module-structure.md.template`,
`docs/architecture/frontend.md.template`.
