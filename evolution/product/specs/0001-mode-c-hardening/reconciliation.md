---
doc_type: spec-reconciliation
spec: 0001
summary: Spec-vs-code reconciliation outcomes written by reviewer and /reconcile.
context_budget: ~500 tokens
---

## Reconciliation

Recorded after the fact: this spec was implemented directly on 2026-10-03, without `/plan` and `/tasks`; the sections below document what was actually done, so the pipeline's own bookkeeping holds.

- [task 2] FR-01: diverged — prefix and rewriting as specified; the framework's reference ADRs are no longer installed in the namespace (framework ADR 0021 keeps them out of every install)
- [task 3] FR-02: matches spec
- [task 1] FR-03: matches spec
- [task 2] FR-04: matches spec
- [task 4] FR-05: matches spec — spec_index names framework ADR 0008 instead of linking it (ADR 0021)
- [task 2] FR-06: matches spec
- [task 2] FR-07: matches spec — through project_tools.py and project config
- [task 2] FR-08: diverged — the rule is generated as Edit(//c/...), not Write(...): Claude Code 2.1.252 never uses Write(path) rules for file checks (verified 2026-10-03); hook `if` filters moved onto handlers, where they work
- [task 1] FR-09: matches spec
- [task 5] FR-10: matches spec
- [task 6] FR-11: matches spec
- [task 7] FR-12: matches spec
- [task 2] NFR-01: matches spec — the installer refuses to overwrite an installed file edited by hand
- [task 8] NFR-02: matches spec — agent instruction; no mechanical check possible
- [task 2] NFR-03: matches spec
- [task 2] AC-01: couldn't verify — install with colliding personal commands verified by tests; `/cfw-spec` end to end inside a real session not exercised yet
- [task 1] AC-02: matches spec
- [task 3] AC-03: matches spec
- [task 2] AC-04: matches spec
- [task 9] AC-05: matches spec — hook-level test, plus hook wiring confirmed in a real Claude Code session
- [task 5] AC-06: matches spec
- [task 7] AC-07: couldn't verify — verified on a synthetic doc tree only; not yet run on a copy of the real context folder

