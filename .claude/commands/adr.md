---
description: Records an architecture decision directly, outside the /plan pipeline — for a decision that isn't attached to any single implementation task (e.g. changing a CI provider, adopting a new convention).
argument-hint: short description of the decision to record
---

This is the "we just decided something, write it down" path — use it
instead of `/plan` when there's no spec/task driving the decision.

1. Delegate to the `architect` subagent with the decision description
   in $ARGUMENTS. Have it follow the `adr-writing` skill's format and
   draft the file at `docs/decisions/000N-short-name.md` (next
   sequential number), with `status: proposed`.
2. If the decision supersedes an existing ADR, have `architect` set
   `supersedes: 000X` in the new file's frontmatter — the
   `adr_backlink` hook takes care of updating the old ADR's
   `superseded_by` field automatically once the new file is written.
3. Never mark the new ADR `accepted` on the agent's own initiative —
   report the draft to the user and wait for explicit approval before
   changing its status.
