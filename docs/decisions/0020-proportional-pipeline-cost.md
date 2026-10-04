---
doc_type: adr
id: 0020
status: proposed
date: 2026-10-03
supersedes: null
superseded_by: null
context_budget: ~1100 tokens
---

# ADR 0020 — A fast lane, cheaper gates and a per-project review policy

Like ADR 0001–0019, this documents a decision about *this framework's
own* tooling. **Amends ADR 0004**: `triage` is no longer reachable only
from inside `/plan`.

## Context

Spec 0003: pipeline cost didn't scale with the change. `triage` lived
inside `/plan`, behind an approved spec, so a typo fix still walked
`/spec` → `/plan` → `/tasks` → `/implement`; the first adopter kept a
personal `quickfix` skill outside the framework to escape that. Fixed
costs were paid on every change: the build/test gate ran on **every**
`SubagentStop`, including Explore, `triage`, `researcher` and
`architect`; the validation-summary agent hook started a Sonnet agent on
every edit to an approved spec, even without a language split; and a
`reviewer` pass ran per standard task on top of the final `/review`.

## Options considered

- **Make `/spec` and `/plan` shorter for small changes.** Rejected: it
  still forces the command chain and the spec file for a one-line fix.
- **Drop per-task review globally.** Rejected: whether it pays off is a
  property of the project, which is why a policy plus data beats a
  global default.
- **A fast-lane command, an agent filter on the gate, a deterministic
  pre-check for the validation sync, a per-project review policy, and
  per-feature metrics to choose between them (chosen).**

## Decision

- **`/quick <request>`** runs `triage` on free text, with no spec.
  `trivial` → `quickfix` + build/test gate, no spec, no review (plus a
  census pending entry where enabled). `standard` → a one-file *lite
  spec* (FRs, ACs, inline tasks, `lite: true`), approved by the
  requester in the same step, then `/implement`; `/plan` only on
  request. `structural` → stop, full `/spec` → `/plan` path. The
  constitution, the gate and scope rules are unchanged: only planning
  and review ceremony shrink.
- **The gate filters by agent** (`run_build_test.py` reads the
  `SubagentStop` input). It always runs for `coder`/`quickfix` (prefixed
  or not). For any other agent it runs only when that agent's own
  transcript shows an edit to code under `CLAUDE_PROJECT_DIR`, outside
  the docs root and `.claude/`. Read-only agents never run it. With no
  information at all, it builds.
- **The validation-summary sync is decided by a command hook**
  (`validation_sync_check.py`), in both settings templates. No split →
  nothing. Not `approved`/`implemented` → nothing. Requirements
  unchanged since the companion's recorded `source_hash` → nothing.
  Only otherwise does it hand the session an exact sync instruction,
  with absolute paths. The two `agent` hooks are gone. A hook can't start
  an agent conditionally, so the "agent" step is the session itself,
  which may delegate.
- **`review_policy`** in the project config: `per-task` (default),
  `final-only`, or `structural-only`. `/implement` honours it, the final
  `/review` always runs, and when per-task passes were skipped `/review`
  writes the Reconciliation entries itself. Changing it never touches
  shared machinery.
- **Metrics per feature**: `subagent_dispatched` and `gate_run` events
  join the ADR 0011 log, `/implement` and `/quick` bracket each feature
  with `metrics.py start/finish` (lane, tier), and `/metrics` shows
  subagents, gate runs, gate failures, reviewer verdicts and rework per
  feature and per lane.
- **Mode A gets an optional `.claude/project-config.json`** (written by
  Domain 1), the same keys as a subtree's `project-config.json`. The
  mode A gate now calls `run_build_test.py` instead of embedding the
  command literally, so the agent filter applies in every mode. ADR
  0016 (still proposed) rejected this file for its own flags; its
  reasoning — "doesn't exist in mode A" — no longer holds, but its
  choice of `CLAUDE.md` for agent-read facts is unaffected.

## Rationale

Each fixed cost had a cheap deterministic precondition nobody was
checking: who stopped, whether the project has a split, whether the
requirements changed. Checking those in code costs nothing per event.
The fast lane removes ceremony without removing any gate, and the
metrics make the remaining trade-off — how much review a project needs
— a decision from data rather than a default.

## Consequences

- The filter relies on `agent_type` and `agent_transcript_path` in
  `SubagentStop` input. Both are documented, and both were confirmed on
  2026-10-03 by capturing real input from this framework's own session,
  with transcripts recording `tool_use` entries in the shape the gate
  parses. An older Claude Code without them falls back to "read-only
  agent definition → skip, otherwise build": safe, but less cheap.
- The same capture showed that hook stdin is UTF-8, which Python on
  Windows doesn't assume. Every hook now reads it through
  `read_hook_input()`; before, non-ASCII paths silently disabled the
  directory-scoped hooks.
- An agent that edits code only through Bash, and isn't `coder` or
  `quickfix`, doesn't trigger the gate. The final `/review` still sees
  the diff.
- A lite spec skips the stakeholder round. A project with a language
  split that needs stakeholder sign-off uses the full path.
- Metrics attribution is by time window. Two features running at once
  on one project are flagged as overlapped, not separated.
- Existing mode A projects keep their old `settings.json` (literal gate
  command, agent hooks) until they re-run Domain 1's settings step.

## References

`docs/product/specs/0003-proportional-pipeline-cost.md`,
`docs/decisions/0004-plan-tasks-implement-rebalance.md`,
`docs/decisions/0011-pipeline-metrics.md`,
`docs/decisions/0016-project-disciplines-configuration.md`,
`.claude/commands/quick.md`, `.claude/commands/metrics.md`,
`.claude/hooks/run_build_test.py`, `.claude/hooks/validation_sync_check.py`
