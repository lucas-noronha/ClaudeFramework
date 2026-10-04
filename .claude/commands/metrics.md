---
description: Shows what each feature cost on this project — subagents dispatched, build/test gate runs and failures, reviewer verdicts, rework — with the fast lane and the full path side by side, so a review policy or lane is chosen from data.
---

Run `python "${CLAUDE_PROJECT_DIR:-.}/.claude/scripts/metrics.py" report`
and show its tables to the user as they are. The script reads this
project's own `pipeline-metrics.jsonl`; a routed project has it in its
subtree, so pass `--project-dir "$CLAUDE_PROJECT_DIR"` and the script
resolves the rest. See framework ADR 0020
for what each column counts.

Then add at most three lines of reading, never more:

- whether the fast lane is actually cheaper here, and by how much;
- whether reviewer passes are finding things (`Returned` > 0) or only
  costing time — relevant to this project's `review_policy`
  (`per-task`, `final-only`, `structural-only`);
- any feature marked overlapped, whose numbers are approximate.

Say nothing when there are fewer than two features in a lane, beyond
"not enough data yet". Don't change any setting from here; suggesting a
`review_policy` change is fine, applying it is the user's call.
