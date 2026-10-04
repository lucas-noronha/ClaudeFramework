---
doc_type: spec
id: 0003
status: implemented
area: pipeline-cost
relates_to: []
context_budget: ~1700 tokens
---

# Proportional pipeline cost — a fast lane and cheaper gates

## Feature name

Make the pipeline's cost proportional to the change: a trivial fix should not pay for a
spec, a plan and review agents.

## Business context

Triage exists but lives **inside `/plan`**, which requires an approved spec. A trivial change
therefore still walks `/spec` → `/plan` (tier only) → `/tasks` → `/implement`. The trivial
tier skips the plan detail and the per-task review, but not the spec or the command chain.
The first adopter kept a personal `quickfix` skill outside the framework precisely for this
gap.

Fixed costs paid on every change today:
- `run_build_test.py` runs on **every** `SubagentStop`. It has no filter by agent type, so
  Explore, triage, researcher and architect subagents trigger a full build and test run.
- The validation-summary agent hook starts a Sonnet agent on every edit to an approved spec.
  It does this even when the project has no language split, and only then decides to stop
  (its step 0e).
- A `cfw-reviewer` pass per standard task, plus the final `/review`.

## Functional requirements

- FR-01: A fast-lane entry command (e.g. `/quick <request>`) runs `triage` on a free-text
  request, with no spec required:
  - **trivial** → `cfw-quickfix` directly, with the build/test gate, no spec and no
    per-task review. For census projects it writes a ledger pending entry (0002 FR-04). The
    result is reported with the tier.
  - **standard** → offers a *lite spec*: FRs + ACs + an inline task list, in one file under
    `product/specs/`, then `/implement` on it. `/plan` is skipped unless the user asks for it.
  - **structural** → stops and routes to the full `/spec` → `/plan` path (architect + ADR).
- FR-02: The build/test gate runs only when the stopping subagent can have changed code
  (`cfw-coder`, `cfw-quickfix`, or any agent that edited files under `CLAUDE_PROJECT_DIR`
  during its run). Read-only agents never trigger it.
- FR-03: The validation-summary sync is decided by a cheap command hook: it reads
  `project-config.json` and returns immediately when canonical == stakeholder language. It
  starts the agent only for projects with a split and only for specs in `approved` or
  `implemented`.
- FR-04: A per-project `review_policy` in `project-config.json`: `per-task` (today's
  default), `final-only` (only the whole-feature `/review`), or `structural-only`.
- FR-05: `pipeline_metrics` records per feature: tier, number of subagents, gate runs,
  reviewer verdicts and rework. `/metrics` compares the fast lane and the full path on the
  same project, so policies are chosen from data.

## Non-functional requirements

- NFR-01: The fast lane keeps every non-negotiable: constitution checks, the build/test gate
  and scope rules. Only the planning and review ceremony shrinks.
- NFR-02: Changing `review_policy` never requires editing shared machinery.

## Explicitly out of scope

- Changing model tiers per agent (covered by `model-tiering.md`).
- Removing the final `/review`.

## Roles and permissions involved

Developer using the pipeline; framework maintainer choosing defaults.

## Related specs

- 0002-living-architecture-docs — relationship: the fast lane writes the same ledger pending
  entry (0002 FR-04).

## Acceptance criteria

- [ ] AC-01: A one-file typo fix via the fast lane produces no spec file and no reviewer
      pass. It runs the gate exactly once and reports tier `trivial`.
- [x] AC-02: A session that dispatches only Explore/triage subagents runs the build/test gate
      zero times.
- [x] AC-03: Editing an approved spec in a project with no language split starts no agent
      hook.
- [ ] AC-04: With `review_policy: final-only`, a standard spec's tasks complete without
      per-task reviewer passes, and `/review` still runs over the cumulative diff.
- [x] AC-05: After two features on one project (one per path), `/metrics` shows subagent
      count, gate runs and reviewer findings side by side.

## Impact on existing architecture

- `triage` becomes callable outside `/plan`. Amends ADR 0004 (plan/tasks/implement
  rebalance).
- `run_build_test.py` gains an agent filter.
- The validation-summary hook is split into a command pre-check plus an agent.

## Reconciliation

Recorded after the fact: this spec was implemented directly on 2026-10-03, without `/plan` and `/tasks`; the sections below document what was actually done, so the pipeline's own bookkeeping holds.

- [task 1] FR-01: matches spec
- [task 2] FR-02: matches spec — known gap: a non-coder agent editing only through Bash doesn't trigger the gate
- [task 3] FR-03: diverged — the command hook decides as specified, but hands the sync to the session through additionalContext instead of starting an agent hook (a hook can't start an agent conditionally)
- [task 4] FR-04: matches spec
- [task 5] FR-05: matches spec — attribution by time window; overlapping features are flagged
- [task 1] NFR-01: matches spec
- [task 4] NFR-02: matches spec
- [task 1] AC-01: couldn't verify — command instruction only; not yet exercised in a real session
- [task 2] AC-02: matches spec — tests plus real SubagentStop payloads captured 2026-10-03
- [task 3] AC-03: matches spec
- [task 4] AC-04: couldn't verify — command instruction only
- [task 5] AC-05: matches spec

## Technical plan

Recorded after the fact: this spec was implemented directly on 2026-10-03, without `/plan` and `/tasks`; the sections below document what was actually done, so the pipeline's own bookkeeping holds.

**Tier:** structural. **ADR:** framework ADR 0020 (amends 0004). Traceability per FR/AC: `CHANGELOG.md`.

## Tasks

- [x] 1. `/quick` fast lane; `triage` and `quickfix` accept free-text requests — Tests: FR-01, NFR-01, AC-01
- [x] 2. Build/test gate filtered by agent type and the subagent's own transcript — Tests: FR-02, AC-02
- [x] 3. `validation_sync_check.py` replaces the always-on agent hook — Tests: FR-03, AC-03
- [x] 4. `review_policy` in `/implement` and `/review` — Tests: FR-04, NFR-02, AC-04
- [x] 5. Per-feature metrics: `subagent_dispatched`, `gate_run`, feature markers, `/metrics` — Tests: FR-05, AC-05
