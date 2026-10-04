---
description: Fast lane — triages a free-text request with no spec required, then fixes a trivial change directly (quickfix + build/test gate, no spec, no review), offers a one-file lite spec for a standard one, and routes a structural one to the full /spec → /plan path. Pipeline cost proportional to the change.
argument-hint: what to change, in plain words
---

Before anything else in this command: apply the `project-registration`
skill's check — it resolves where this session's `docs/` and `CLAUDE.md`
actually live (registering the project first if it isn't yet), and in
the common case costs one check and changes nothing.

Why this exists: `triage` used to live only inside `/plan`, behind an
approved spec, so even a typo fix paid for `/spec` → `/plan` → `/tasks`
→ `/implement`. This lane makes the ceremony proportional to the change
(see `docs/decisions/0020-proportional-pipeline-cost.md`). **Only the
ceremony shrinks.** The constitution, the build/test gate and every
scope rule apply exactly as in the full path.

1. Delegate classification of $ARGUMENTS to the `triage` subagent, with
   the request text only (and the file paths it names, if any). Report
   the tier to the user in one line.

2. **Trivial** (one file, no new business rule):
   - Record the start:
     `python "${CLAUDE_PROJECT_DIR:-.}/.claude/scripts/metrics.py" start --feature quick-<YYYYMMDD-HHMM> --lane fast --tier trivial`.
   - Delegate to `quickfix` with the request and the constitution
     path(s) `project-registration` resolved. No spec file, no `/plan`,
     no `/tasks`.
   - The build/test gate runs automatically when `quickfix` stops. If it
     fails, hand the failure back to `quickfix` once; if it fails again,
     stop and report — never pass a red gate off as done.
   - No `reviewer` pass — the same rule `/implement` applies to every
     quickfix-tier task (`docs/workflow/model-tiering.md`).
   - If this project has the census enabled (its config's
     `census.enabled`), record the change for the next `/update-docs`:
     `python "${CLAUDE_PROJECT_DIR:-.}/.claude/scripts/census.py" ledger add-pending --spec quick --task "<one-line summary>" --files <files quickfix changed>`.
     Never touch the watermark.
   - Record the finish (`metrics.py finish --feature <same id>`) and
     report: tier `trivial`, the file changed, the gate result.

3. **Standard** (a feature inside an existing boundary): offer a **lite
   spec** (`AskUserQuestion`: lite spec now / full `/spec` path / cancel).
   On "lite spec":
   - Write **one file** at `<project docs>/product/specs/NNNN-short-name.md`
     (next free number), with this frontmatter: `doc_type: spec`, `id`,
     `status: approved`, `lite: true`, `tier: standard`, `area`,
     `relates_to`, `context_budget`. `area`/`relates_to` are inferred as
     in `/spec` step 4. The body holds only: a one-paragraph context,
     `## Functional requirements` (FR-NN), `## Acceptance criteria`
     (AC-NN), `## Tasks` (checkboxes in `/tasks`' exact format, each with
     `Depends on:` and `Tests:` naming the AC/FR it covers), and an empty
     `## Reconciliation`.
   - Show the user the file before writing it, and write it with
     `status: approved` only after they approve it in that same
     question. The person who asked for the change is the approver here;
     there's no separate stakeholder round. If the project has a
     language split and the user wants the stakeholder to validate,
     that's the full path, not this one.
   - Check the requirements against the constitution layers first, the
     same check `/spec` step 3 does. A conflict stops the lane and goes
     back to the user.
   - Then run `/implement` on that spec (orchestration mode). `/plan` is
     skipped unless the user asks for it; `/implement` records the
     feature as lane `fast`, tier `standard`.

4. **Structural** (new module/boundary, cross-module dependency change,
   or anything needing an ADR): stop. Tell the user this needs the full
   path, `/spec` → `/plan` (architect + ADR) → `/tasks` → `/implement`,
   and offer to start `/spec` with $ARGUMENTS as its description.

Never mention plugins or subagent names beyond the tier and the outcome.
