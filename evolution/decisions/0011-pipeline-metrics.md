---
doc_type: adr
id: 0011
status: accepted
date: {{DATE}}
supersedes: null
superseded_by: null
context_budget: ~650 tokens
---

# ADR 0011 — A raw pipeline-observability event log, no new service

Like ADR 0001–0010, this documents a decision about *this framework's
own* tooling (kept as a worked example).

## Context

Whether this pipeline is actually working — how often `reviewer`
returns a task before approving it, how long a spec sits between
`draft` and `implemented`, how often "## Reconciliation" entries come
back `diverged` — existed only anecdotally. Nothing recorded it.

## Options considered

- **A dashboard/service.** Rejected outright — this framework ships no
  infrastructure of its own and isn't going to start for a nice-to-have;
  every existing hook is a local file operation, never a network call.
- **Compute metrics on demand by re-deriving from spec files (git log,
  file timestamps).** Rejected — status transitions and reviewer
  verdicts aren't reliably reconstructable after the fact (a spec's
  frontmatter only ever shows the *current* status, not its history);
  the moment of the event is the only reliable place to capture it.
- **A git-ignored, append-only `.jsonl` event log, written by hooks at
  the moment each event happens (chosen).** No schema migration, no
  service, human- or agent-readable with `jq`/a quick script whenever
  someone actually wants to look.

## Decision

`.claude/pipeline-metrics.jsonl` (git-ignored, per-machine — added to
`.gitignore.framework-additions`), one JSON object per line, four event
types: `spec_created`, `spec_implemented` (both carry `spec_id`/`area`,
letting `draft`→`implemented` elapsed time be computed as
`spec_implemented.ts - spec_created.ts`), `reconciliation_snapshot`
(current counts of matches/diverged/out-of-scope in a spec's
"## Reconciliation" section — a snapshot on every touch, not an
incremental delta, so it's correct regardless of how the edit landed),
and `reviewer_verdict` (Approved/Returned, best-effort `spec_id`).
`spec_status_sync.py` logs `spec_implemented` itself, reusing the exact
transition it already computes; a new `pipeline_metrics.py` handles the
other three, via a shared `_pipeline_metrics.py` helper (not a hook
itself — just the `log_event` function both import).

## Rationale

An event log needs zero maintenance and never goes stale the way a
computed dashboard would if the computation logic drifted from the
hooks generating the underlying state — the same reasoning already
behind this framework's `decision_index.py`/`spec_index.py` (rebuild
from source of truth, never hand-maintained). Snapshot-not-delta for
reconciliation counts sidesteps needing to track "what was here last
time" in a second piece of state.

## Consequences

- **`reviewer_verdict` is the one event with a real reliability gap**,
  called out plainly rather than shipped quietly: it depends on
  reading the subagent-dispatch tool's `PostToolUse` payload, matched
  on both plausible tool names (`Task`, `Agent`) since which one a
  given Claude Code version actually uses isn't something this
  framework can verify generically. If neither ever fires, no
  `reviewer_verdict` events appear — silently, since every hook here
  fails open by design. Worth checking empirically after adopting this
  (run `/review` once, then check the log) rather than trusting it
  blind.
- No aggregation ships — "how many times did `reviewer` return before
  Approved" is a query over the raw log (group by `spec_id`, count
  `Returned` before the next `Approved`), not something this ADR
  computes. A summarizer (script or a future slash command) is a
  natural next step if the raw log turns out to be useful, not
  something to build speculatively now.
- Purely additive and informational — nothing here gates, blocks, or
  changes any existing command's behavior.

## References

`.claude/hooks/pipeline_metrics.py`, `.claude/hooks/_pipeline_metrics.py`,
`.claude/hooks/spec_status_sync.py`, `.gitignore.framework-additions`
