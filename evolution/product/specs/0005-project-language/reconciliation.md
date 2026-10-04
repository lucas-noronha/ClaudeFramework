---
doc_type: spec-reconciliation
spec: 0005
summary: Spec-vs-code reconciliation outcomes written by reviewer and /reconcile.
context_budget: ~750 tokens
---

## Reconciliation

- [task 1] FR-02: matches spec (after one fix)
- [task 1] NFR-05: matches spec (`legacy_split` requires an actual split; shim uses the same predicate)
- [task 2] FR-12: matches spec
- [task 2] AC-07: matches spec as amended (only the two old-default assertions changed; the templates one accepts either key until task 12)
- [task 2] AC-10: matches spec
- [task 3] FR-05: matches spec (record schema; `dest`/`output_sha256` only in modes A/B)
- [task 3] FR-06: matches spec (`plan` lists new and changed only, with a token estimate; replace/keep honoured)
- [task 3] NFR-06: matches spec (LF-normalized, BOM-free hash; unchanged sources never re-translated)
- [task 3] AC-09: matches spec (English `plan`/`apply` are no-ops with no record; `en` and `en-US` tested)
- [task 4] FR-08: matches spec
- [task 4] FR-11: matches spec
- [task 4] NFR-04: matches spec
- [task 4] AC-03: matches spec
- [task 4] AC-10: matches spec
- [task 5] FR-06: matches spec (`recover-placeholders`)
- [task 5] FR-11: matches spec (cross-file step realized as a `sync-index` subcommand run after `apply`)
- [task 6] FR-06: matches spec
- [task 6] FR-10: matches spec
- [task 6] AC-05: matches spec (mode B re-translates changed paths, conflicted or clean; `take-upstream` trusts the caller to pass only listed paths, which `/setup-framework` must state)
- [task 7] FR-05: matches spec
- [task 7] FR-08: matches spec
- [task 7] FR-11: matches spec
- [task 7] NFR-04: matches spec (prompt also states the check's length-ratio bound and verdict-word count)
- [task 8] FR-05: matches spec
- [task 8] FR-06: matches spec
- [task 8] NFR-01: matches spec
- [task 8] NFR-02: matches spec
- [task 8] AC-05: matches spec
- [task 8] AC-08: matches spec
- [task 9] FR-07: matches spec
- [task 9] AC-06: matches spec
- [task 11] FR-01: matches spec
- [task 11] NFR-05: matches spec
- [task 11] AC-01: matches spec
- [task 13] FR-01: matches spec
- [task 13] FR-07: matches spec
- [task 13] FR-10: matches spec
- [task 13] NFR-06: matches spec
- [task 13] AC-01: matches spec
- [task 13] AC-04: matches spec
- [task 13] AC-06: matches spec
- [task 14] FR-08: matches spec
- [task 14] AC-07: matches spec
- [task 12] FR-03: matches spec
- [task 12] FR-04: matches spec
- [task 12] FR-07: matches spec
- [task 12] FR-08: matches spec
- [task 12] FR-11: matches spec
- [task 12] FR-12: matches spec
- [task 10] FR-03: matches spec
- [task 10] NFR-05: matches spec (shim acts only with split keys and no setup language, never deletes companions, fails open)
- [task 10] AC-02: matches spec
- [task 10] AC-08: matches spec

