---
doc_type: spec-reconciliation
spec: 0007
summary: Spec-vs-code reconciliation outcomes written by reviewer and /reconcile.
context_budget: ~50 tokens
---

## Reconciliation

- [task 7] AC-07: matches spec
- [task 7] AC-11: matches spec
- [task 7] AC-12: matches spec — the check sits in orchestration step 3 instead of the ADR's "step 5", which is the same pre-dispatch point; the numbering differs.
- [task 1] FR-05: matches spec
- [task 1] AC-04: matches spec
- [task 6] NFR-07: matches spec (the `Reconciliation:` literal is in `translation.py` `LITERALS`, which excludes the `## Reconciliation` heading; test P18 passes)
- [task 6] FR-10: matches spec (the read-only git rule and the full allowlist are in coder, quickfix and reviewer; the editing rule is in coder and quickfix)
- [task 6] FR-13: matches spec (per-task reviewer returns its lines under `Reconciliation:` and never writes them)
- [task 6] FR-15: matches spec (the `/reconcile` sweep and `final-only` `/review` stay single writers, `Edit` retained) — first pass removed `Edit` and changed the sweep scope; returned by reviewer and reverted
- [task 6] FR-18: matches spec (the editing rule is in coder and quickfix, so there are no heredoc or backslash-`sed` edits)
- [task 4] FR-04: matches spec
- [task 4] FR-08: matches spec
- [task 4] FR-09: matches spec
- [task 4] NFR-01: matches spec
- [task 4] AC-03: matches spec
- [task 4] AC-06: matches spec
- [task 4] AC-07: matches spec
- [task 4] AC-13: matches spec
- [task 5] FR-10: matches spec — first pass denied `git branch -a` (short-flag set shared with `tag`); returned by reviewer and fixed with per-subcommand sets
- [task 5] FR-12: matches spec
- [task 5] NFR-02: matches spec
- [task 5] NFR-04: matches spec
- [task 5] NFR-05: matches spec
- [task 5] AC-08: matches spec
- [task 5] AC-09: matches spec
- [task 2] FR-01: matches spec — first pass omitted `agent_id` on `reviewer_verdict` (ADR 0025 item 3); returned by reviewer and added
- [task 2] FR-02: matches spec
- [task 2] FR-03: matches spec
- [task 2] AC-01: matches spec
- [task 2] AC-02: matches spec
- [task 2] ADR 0025 item 3 "tail is read": diverged — the whole transcript is read because `first_user_text` needs the head; harmless. A bounded retry (up to 4 reads, 0.25 s apart, reviewer role only) covers a final message not yet flushed at `SubagentStop`.
- [task 3] FR-06: diverged — `concurrent` also counts siblings that stopped at or after the stopping agent's own start, which the ADR's "in flight at gate start" does not (an over-count, which the ADR accepts as safe). The blocked-gate in-flight rule is implemented. It still excludes the stopping agent and read-only agents and filters by checkout and window.
- [task 3] FR-07: matches spec
- [task 3] FR-19: matches spec — first pass wrote the full output to stderr when `stop_hook_active` was true; aligned to the bounded header + tail on follow-up
- [task 3] NFR-01: matches spec
- [task 3] AC-04: matches spec
- [task 3] AC-05: matches spec
- [task 3] AC-13: matches spec — no existing exit-code assertion changed.
- [task 3] AC-15: matches spec — tested half only. The real-session half belongs to task 9.
- [task 8] FR-10: matches spec
- [task 8] FR-11: matches spec
- [task 8] FR-18: matches spec — first pass left `.claude/README.md`'s mode C gate bullet saying the gate propagates the build's exit code; returned by reviewer and fixed, together with `docs/workflow/governance-and-observability.md` §3–§4 and `docs/workflow/ai-first-development.md`, which tasks 1–7 had made untrue
- [task 8] AC-10: matches spec

### Task 9 — real-session verification (2026-10-04, coordinator)

Hooks wired into `.claude/settings.local.json` (`SubagentStart`, second `SubagentStop` group, guard on `Bash|PowerShell`); they took effect mid-session without a restart. A temporary failing test (`tests/test_zz_task9_deliberate_failure.py`, since deleted) made the gate fail.

- [task 9] Agent id: matches — the id the Agent tool returns equals the hook's `agent_id` (foreground and background probes), so failing output can be matched to tasks by id.
- [task 9] AC-15: diverged — the gate ran and exited 2 for both a foreground and a background `coder` (`gate_run` `blocked: true`, `exit_code: 1`), but neither subagent was resumed: each transcript holds one assistant record, no gate feedback, no second stop. So the "second failure exits 1" path could not be reached either. In this harness, subagents end by calling a `SubagentHandback` tool, and exit 2 on `SubagentStop` does not re-prompt them. The gate still records the failure, but it doesn't hand the failure back to the agent.
- [task 9] FR-01: diverged — no `reviewer_verdict` is logged in a real session. The reviewer's final reply is not a text-bearing assistant message but the `input.message` of a `SubagentHandback` `tool_use`, which `last_assistant_text` doesn't read (probe reviewer: `subagent_started`/`subagent_stopped` logged, no verdict). The ADR's captured transcript shape predates this. Fix: also accept a `SubagentHandback` tool_use's `input.message` as the final reply.
- [task 9] FR-06: diverged (over-count) — the background probe's gate logged `concurrent: 1`, counting the foreground probe as in flight because its latest event was a blocking `gate_run`, though it was never resumed. Harmless (it only tags a failure for re-check), but the blocked-means-in-flight rule assumes exit 2 resumes the agent.
- [task 9] Gate timing: the gate runs after the hand-back (~130 s here, against a 180 s hook timeout). Stopping a subagent between its hand-back and its completion notification kills its gate — this sweep's earlier `TaskStop`s did that, which is why several coders have no `gate_run`. The coordinator's "done" signal is the completion notification, not the hand-back. Projects whose `build_test_cmd` nears the hook timeout lose the gate result silently.

Resolved the same day (coordinator, at the user's request, without a new ADR):

- [task 9] FR-01: matches spec — `_subagents._text_of` also reads a `SubagentHandback` tool call's `input.message`, so the verdict is found in the shape the real transcript has (new test `test_p04_verdict_read_from_subagent_handback_call`; the probe reviewer's real transcript now parses as `**Approved**`).
- [task 9] AC-15: matches spec (amended) — FR-19 and AC-15 now say exit 2's hand-off is best-effort; `/implement` single-task step 5 waits for the completion notification (never stopping a subagent between hand-back and completion), reads the task's gate with `metrics.py gates` by `agent_id`, and returns a failure to that subagent itself. README, the `run_build_test.py` docstring, `docs/workflow/governance-and-observability.md` and CHANGELOG say the same. ADR 0025 (accepted, immutable) still describes exit 2 as the hand-off; this reconciliation and the spec record the change.
- [task 9] FR-06: diverged (accepted) — the blocked-means-in-flight over-count stays: the ADR accepts over-counts, and a harness that does resume on exit 2 needs the rule.
- [task 9] out of scope: `tests/test_parallel_metrics.py` P09 assumed a legacy-only real log; once a log holds a concurrent failure, the old script counts it as rework and FR-09 doesn't, so the test now expects `rework` to drop by `gate_failures_concurrent`.
- [task 9] Real-session re-check after the fixes: a probe reviewer's `Returned` is logged as `reviewer_verdict` with `spec_id: 0007` and its `agent_id`. A probe coder's failing gate (`blocked: true`) was found with `metrics.py gates` by its `agent_id`; the coordinator re-ran the build once (`concurrent` > 0), sent the failure tail to the same subagent, and the subagent received it. Resuming it fired `SubagentStart` again with the same `agent_id`, and its next gate passed (`exit_code: 0`, `blocked: false`). Both probes' `concurrent: 2` counted earlier probes left at a blocking `gate_run` that were never resumed — the accepted over-count, bounded by the 60-minute window.
- [task 9] out of scope (added at the user's request): `metrics.py pending` lists each `coder`/`quickfix` in this checkout, since the last `wave-start`, whose latest lifecycle event is a stop with no `gate_run` after it — hand-back arrived, gate still running or lost — with `waiting_s`. `/implement` orchestration step 6 uses it instead of tracking completion notifications from memory; one waiting past the hook timeout lost its gate, and the coordinator runs the build for it. Test: `test_pending_lists_stops_whose_gate_has_not_landed`.
- Pending (not done): gate timeout. The hook timeout (180 s in both templates) silently drops the gate when `build_test_cmd` runs longer. Follow-up for a future spec: have the gate warn when a run nears the timeout, and have `/setup-framework` suggest a timeout from the suite's measured duration.
