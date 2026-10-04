---
description: Triages complexity and produces the actual technical plan for a validated spec (architect + ADR for structural changes, a proportional plan for standard ones, nothing for trivial ones), plus a Definition of Done and Test plan numbered against the spec's own FR/AC items.
argument-hint: path to the spec (docs/product/specs/NNNN-name.md)
---

Before anything else in this command: apply the `project-registration`
skill's check — it resolves where this session's `docs/` and `CLAUDE.md`
actually live (registering the project first if it isn't yet), and in
the common case costs one check and changes nothing.

Language: write free text in {{LANGUAGE}}; frontmatter keys, enumerated values, `## Tasks`/`## Reconciliation`, the reconciliation outcome phrases and `Approved`/`Returned` stay English.

**Prerequisite — the spec's `status`, settled here.** A technical plan is
never written over an unvalidated or dead requirement, and approving is
the human's call. This is the moment the pipeline asks for it, so nobody
has to remember to edit the frontmatter by hand:

- **`approved`** → continue with step 1.
- **`draft`** → ask, with a single `AskUserQuestion`: "Spec NNNN is still
  `draft`. Approve it now?"
  - **Approve and plan** — say plainly what approving means: the
    requirements are validated.
  - **Not yet** — stop here. Say what's left (the open questions `/spec`
    listed) and that the next `/plan` will ask
    again.
  - **Abandon it** — set `status: abandoned` and stop.

  On approval, change only the canonical spec's frontmatter `status:
  draft` → `status: approved` (one edit, nothing else in the file), say
  so in one line, then continue with step 1.
- **`abandoned`** → stop and warn. Don't resurrect a dropped feature
  silently. If the user wants it back, they set it to `draft` and run
  `/plan` again.
- **`implemented`** → stop: there is nothing left to plan. Point at
  `/reconcile` for checking it against today's code, or at `/spec` for a
  follow-up.

1. Delegate the spec's complexity classification to the `triage`
   subagent (trivial / standard / structural).
2. **Trivial** — record the tier and stop there. A plan for a
   single-file, no-new-rule change is overengineering; `coder`/`quickfix`
   follows the project's already-documented pattern directly.
3. **Standard** — write a short technical plan yourself: what changes
   (files/modules touched), the approach in a few sentences, and any
   real risk worth flagging before `/tasks` breaks it down. If
   `superpowers` is enabled this session, invoke its `writing-plans`
   skill to produce it; otherwise write it directly (absorbed fallback,
   see `plugin-awareness`). Keep it proportional — a short paragraph,
   not a design document.
4. **Structural** — delegate to the `architect` subagent to assess
   cross-module impact and, if needed, draft a new ADR (`status:
   proposed`, never `accepted` — that's a human call). Once `architect`
   has answered, write the same technical-plan artifact as step 3
   (`writing-plans` when enabled), informed by whatever the ADR
   settled — this is where the deepest planning effort in this
   pipeline belongs, not `/tasks`.
5. **Scope check** (standard and structural alike): before recording
   the plan, check it against the spec's own "Functional requirements"
   and "Explicitly out of scope" sections. If the natural implementation
   approach would touch a file, module, or concern the spec never asked
   for (or one it explicitly ruled out), flag it explicitly instead of
   folding it in silently — a real scope gap belongs back in `/spec`,
   not smuggled into the plan. Also check the plan's approach against
   the constitution, if present — flag a conflict the same way, don't
   plan around it silently. **There can be two of them, and you check
   the approach against both whenever both exist** (see
   framework ADR 0015):
   the supreme layer at the **shared** `docs/` root —
     `docs/constitution-baseline.md` plus `docs/constitution.md` (framework ADR 0018) —
   (always, non-negotiable floor — it is shared material, so
   `project-registration`'s step 4 tells you where to read it from),
   plus `<project-subtree>/constitution.md` **if that project has one**
   (optional, additive only — never read it as overriding, narrowing or
   relaxing a supreme principle; if it looks like it contradicts one,
   flag that as its own finding rather than reconciling it in the plan).
   In **mode A** (`project-registration` stopped at its step 1 — no
   registry entry, relative paths unchanged) there is no project layer,
   just the supreme pair in the repo's own `docs/`, and this is today's
   single-file check, unchanged.
6. **Definition of Done + Test plan** (standard and structural alike):
   write two short checklists, both numbered against the spec's own
   `FR-NN`/`AC-NN` items — never free-floating, so a test or a DoD line
   can always be traced back to the requirement it exists for:
   - **Definition of Done**: build/tests pass, `reviewer` approved,
     every `AC-NN` this spec touches is satisfied, plus anything
     feature-specific worth calling out (a migration verified against
     real data, a feature flag confirmed off by default). Keep it to
     the handful of lines that actually matter for this feature, not a
     generic boilerplate checklist.
   - **Test plan**: one line per unit test this feature will end up
     with, as a plain scenario ("rejects the request when the email is
     missing"), each tagged with the `FR-NN`/`AC-NN` it backs. This is
     the list `coder`'s test-first pass works through per task, and
     what `reviewer` checks actual test coverage against — it isn't
     just documentation.
   If `superpowers` is enabled, the same `writing-plans` invocation
   from steps 3/4 can produce these alongside the rest of the plan;
   otherwise write them directly (absorbed fallback).

Record the result at the bottom of the spec itself, in a "Technical
plan" section: the complexity tier, the ADR reference (if any), and —
for standard/structural — the plan, Definition of Done, and Test plan
from steps 3/4/6 (trivial gets tier only, nothing else). `/tasks` reads
this section next; it does no technical judgment of its own and
invents no new test beyond this list, so whatever it needs to know
belongs here.
