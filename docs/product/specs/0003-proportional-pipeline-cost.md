---
doc_type: spec
id: 0003
status: draft
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
- [ ] AC-02: A session that dispatches only Explore/triage subagents runs the build/test gate
      zero times.
- [ ] AC-03: Editing an approved spec in a project with no language split starts no agent
      hook.
- [ ] AC-04: With `review_policy: final-only`, a standard spec's tasks complete without
      per-task reviewer passes, and `/review` still runs over the cumulative diff.
- [ ] AC-05: After two features on one project (one per path), `/metrics` shows subagent
      count, gate runs and reviewer findings side by side.

## Impact on existing architecture

- `triage` becomes callable outside `/plan`. Amends ADR 0004 (plan/tasks/implement
  rebalance).
- `run_build_test.py` gains an agent filter.
- The validation-summary hook is split into a command pre-check plus an agent.

## Reconciliation
