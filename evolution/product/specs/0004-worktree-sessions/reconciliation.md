---
doc_type: spec-reconciliation
spec: 0004
summary: Spec-vs-code reconciliation outcomes written by reviewer and /reconcile.
context_budget: ~500 tokens
---

## Reconciliation

- [task 1] FR-01: matches spec
- [task 1] FR-02: matches spec
- [task 1] FR-03: matches spec
- [task 1] FR-04: matches spec
- [task 1] FR-09: matches spec
- [task 1] AC-01: matches spec
- [task 1] AC-02: matches spec
- [task 1] AC-05: matches spec
- [task 1] AC-06: matches spec
- [task 1] AC-07: matches spec
- [task 1] NFR-01: matches spec
- [task 1] NFR-02: matches spec
- [task 2] FR-05: matches spec
- [task 2] AC-04: matches spec (partial: handoff part; metrics part is task 3)
- [task 4] FR-07: matches spec
- [task 4] AC-03: matches spec (script half; the /worktree call is task 5)
- [task 4] NFR-03: matches spec
- [task 3] FR-06: matches spec
- [task 3] AC-04: matches spec (metrics half; task 2 covers the handoff half)
- [task 3] NFR-01: matches spec (events without `checkout` count as main; a main-only log renders as before)
- [task 5] FR-07: matches spec (`/worktree` runs the link script, handles exit 1/2, names `--repair`)
- [task 5] FR-08: matches spec
- [task 5] AC-03: matches spec (the `/worktree` half; gitignore lines in place)
- [task 6] FR-11: matches spec
- [task 6] AC-08: matches spec (brief part: worktree header names repo and branch; main brief unchanged)
- [task 7] FR-10: matches spec (optional root `CLAUDE.md` note, append-only, confirm-first, tells the session to run `--repair`)
- [task 7] FR-12: matches spec (mode B volume/symlink check; "any drive" reversed for mode B only)
- [task 7] AC-08: matches spec (setup part)
- [task 8] AC-01: matches spec
- [task 8] FR-04: matches spec
- [task 8] NFR-04: matches spec
- [task 9] docs: matches spec

