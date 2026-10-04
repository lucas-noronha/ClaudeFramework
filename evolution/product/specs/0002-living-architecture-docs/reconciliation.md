---
doc_type: spec-reconciliation
spec: 0002
summary: Spec-vs-code reconciliation outcomes written by reviewer and /reconcile.
context_budget: ~400 tokens
---

## Reconciliation

Recorded after the fact: this spec was implemented directly on 2026-10-03, without `/plan` and `/tasks`; the sections below document what was actually done, so the pipeline's own bookkeeping holds.

- [task 1] FR-01: matches spec
- [task 1] FR-02: matches spec
- [task 3] FR-03: matches spec — command steps are instructions; the ledger logic they rely on is tested
- [task 3] FR-04: matches spec
- [task 4] FR-05: matches spec — default keys resumo/naoResponde, configurable via routing_keys
- [task 5] FR-06: matches spec
- [task 5] FR-07: matches spec — the independent pass is reviewer's new doc-verification scope
- [task 1] FR-08: matches spec — probe paths are git glob pathspecs (`**` crosses folders)
- [task 5] FR-09: matches spec
- [task 5] NFR-01: matches spec — stated as a rule; not mechanically checked
- [task 1] NFR-02: matches spec — writes only under <docs root>/architecture/census/
- [task 1] NFR-03: matches spec
- [task 1] AC-01: matches spec — reproduced on a synthetic repo; the adopter's real .NET repos not run yet
- [task 2] AC-02: matches spec — synthetic C# source
- [task 1] AC-03: matches spec
- [task 1] AC-04: matches spec
- [task 5] AC-05: couldn't verify — agent instruction only; needs a real review over a draft doc
- [task 4] AC-06: matches spec

