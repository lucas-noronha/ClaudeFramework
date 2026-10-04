---
doc_type: spec-tasks
spec: 0007
summary: The nine ordered, dependency-annotated tasks that build spec 0007, each carrying its own Test plan lines and approach pointer.
context_budget: ~2000 tokens
---

## Tasks

Layers are framework layers: **hooks/scripts** (Python, tested) and **commands/docs** (prose read by
agents). No task touches sensitive data or a new table. Shared files that force an order:
`pipeline_metrics.py` (tasks 1, 2), `run_build_test.py` (tasks 1, 3). Every task follows
framework ADR 0025; the approach pointer under each task names its section of `plan.md`.

- [x] 1. **Shared helper and lifecycle events** — hooks/scripts: new `.claude/hooks/_subagents.py` (`role_of`, the gate's read-only rule moved unchanged from `run_build_test.py`, which now imports it, and the transcript readers); `pipeline_metrics.py` logs `subagent_started`/`subagent_stopped` (`agent_id`, `agent_type`, `role`, checkout-stamped); PostToolUse keeps only `subagent_dispatched`. — Depends on: none — Tests: P01
  - Approach: plan.md step 1; ADR 0025 (events).
  - Test P01: `subagent_started` and `subagent_stopped` are logged with `agent_id`, `agent_type` and `role`, checkout-stamped — FR-05, AC-04
- [x] 2. **Verdict on stop** — hooks/scripts: `pipeline_metrics.py` reads the reviewer verdict on `SubagentStop` from `agent_transcript_path` (last text-bearing assistant message, records sharing its `message.id` joined, leading markdown stripped; `spec_id` from the first user message, both path shapes and slash directions); the PostToolUse verdict parse is removed. — Depends on: 1 — Tests: P04, P05, P06
  - Approach: plan.md step 2; ADR 0025 (verdict). If the transcript's final message isn't written yet when `SubagentStop` fires, add a short bounded retry and say so.
  - Test P04: the verdict is read from a background reviewer's transcript: `Approved`, `Returned`, bold markdown, and split records joined by `message.id` — FR-01, AC-01
  - Test P05: the verdict's `spec_id` is parsed from a legacy path and a folder path, with either slash direction — FR-02, AC-02
  - Test P06: PostToolUse no longer logs a verdict, so a foreground reviewer is counted exactly once — FR-03, AC-01
- [x] 3. **Concurrency-aware, blocking gate** — hooks/scripts: `run_build_test.py` computes `concurrent` at start from a byte-capped log tail (this checkout, open feature or last 60 min, excluding itself and read-only agents; omitted without a start event); `gate_run` gains `agent_id` and `blocked`; failure → exit 2 with a header and a tail of ~80 lines / 8 KB on stderr while `stop_hook_active` is false, exit 1 when true; the header warns about sibling files when `concurrent` > 0; a missing `build_test_cmd` stays a non-blocking exit 1. Name any existing exit-code assertion you update (AC-13). — Depends on: 1 — Tests: P02, P03, P10, P11
  - Approach: plan.md step 3; ADR 0025 (concurrent, gate).
  - Test P02: `concurrent` at gate start excludes the stopping agent and read-only agents, counts per checkout and within the window, and survives a line cut at the tail boundary — FR-06, AC-04
  - Test P03: `concurrent` is omitted when the stopping agent has no start event — FR-06, NFR-01
  - Test P10: the gate exits 2 with a bounded tail on failure while `stop_hook_active` is false, and 1 when it is true; a pass exits 0; a missing `build_test_cmd` does not block — FR-19, AC-15
  - Test P11: a concurrent failure still fails, the suite runs once, and the header warns about sibling files — FR-06, FR-07, AC-05
- [x] 4. **`/metrics` for parallel waves** — hooks/scripts: `.claude/scripts/metrics.py` splits solo/concurrent failures, rework = solo failures + `Returned`, a "missing verdicts: N" flag, new `--json` keys, and the `wave-start` / `gates` subcommands; legacy logs render the same numbers. — Depends on: 1 — Tests: P07, P08, P09, P12
  - Approach: plan.md step 4; ADR 0025 (metrics, orchestration).
  - Test P07: `/metrics` shows "missing verdicts: N" when reviewer dispatches outnumber verdicts — FR-04, AC-03
  - Test P08: `/metrics` splits solo and concurrent failures, and rework counts solo failures plus `Returned` — FR-09, AC-06
  - Test P09: this repo's real log renders the same numbers as before, plus the flag — NFR-01, AC-13
  - Test P12: `metrics.py wave-start` and `gates` return each wave's final gate results — FR-08, AC-07
- [x] 5. **Subagent git guard** — hooks/scripts: new `.claude/hooks/subagent_git_guard.py` (PreToolUse `Bash|PowerShell`): fast-path allow with no file read when there is no `agent_id`/`agent_type` or no `git` token; otherwise split compound commands, strip prefixes, recurse one level into `-c`/`-Command`, skip git global options, apply the read-only allowlist (`branch`/`tag` as listings only), deny with a reason; `hook_should_run` only on the deny path; unparseable input is allowed. — Depends on: none — Tests: P13, P14, P15, P16
  - Approach: plan.md step 5; ADR 0025 (guard).
  - Test P13: the guard allows every main-session call (no `agent_id`) — FR-12, AC-08
  - Test P14: the guard denies mutating git inside a subagent, table-driven over Bash and PowerShell forms (`&&`, `;`, pipes, `git -C`, `& git`, `git.exe`, full paths, `-c k=v`, `--git-dir=`, mutating `branch`/`tag` flags) — FR-10, FR-12, AC-08
  - Test P15: the guard allows read-only git and non-git commands without reading a file, and allows unparseable input — NFR-02, NFR-04, AC-09
  - Test P16: the guard never blocks in an unregistered mode C repo — NFR-05
- [x] 6. **Agent prompts** — commands/docs plus one script: `coder`, `quickfix` and `reviewer` get the read-only git rule; `coder` and `quickfix` the editing rule (Edit tool or a script file, never a bash heredoc or `sed` with backslashes); `reviewer` returns its lines under `Reconciliation:` and never writes them; `Reconciliation:` joins `translation.py`'s `LITERALS`. — Depends on: none — Tests: P18
  - Approach: plan.md step 6; ADR 0025 (prompts).
  - Test P18: `translation.py` `LITERALS` include `Reconciliation:` — NFR-07
- [x] 7. **Orchestration commands** — commands/docs: `/implement` (every task prompt repeats the git rule; the coordinator appends reconciliation lines to the resolver's target; after a wave, a concurrent failure gets one re-run via `metrics.py wave-start`/`gates`, and the stop rule counts only failures returned to a task; the pre-wave delete/rename check) and `/tasks` (the delete/rename rule). — Depends on: none (uses ADR 0025's CLI contract for `wave-start`/`gates`) — Tests: none (prose; checked by `reviewer` against AC-07, AC-11, AC-12)
  - Approach: plan.md step 7; ADR 0025 (orchestration).
- [x] 8. **Wiring and docs** — hooks/scripts plus docs: both settings templates get a `SubagentStart` entry, a second `SubagentStop` group and the guard (PreToolUse `Bash|PowerShell`); the mode C template merge records them for uninstall; `.claude/README.md`, `setup-framework.md`'s gate sentence, the `run_build_test.py` docstring and `CHANGELOG.md` updated. — Depends on: 1, 2, 3, 5, 7 — Tests: P17
  - Approach: plan.md step 8; ADR 0025 (wiring).
  - Test P17: the shipped prompts and settings carry the rules; both templates wire `SubagentStart`, `SubagentStop` and the guard; the mode C merge records them for uninstall — FR-10, FR-11, FR-18, AC-10
- [x] 9. **Real-session verification** — coordinator: with the new hooks wired in this repo's local settings, verify AC-15 (a deliberately failing gate blocks a foreground and a background `coder`; a second failure in the same stop chain exits 1), confirm when a reviewer's final message lands in its transcript, and check whether the Agent tool's returned id equals `agent_id`; record the results in `reconciliation.md`. — Depends on: 8 — Tests: none (manual, Definition of Done)
  - Approach: plan.md "Scope check" (not yet captured); ADR 0025 (risks).
  - Also observed during this spec's own sweep (2026-10-04), to confirm and record: a background subagent's hand-back report can arrive while the agent stays listed as "running" with no completion notification (task 7's coder had to be stopped by hand, with no Python process alive), and the reverse — a "completed" notification arriving before the hand-back, while the agent was still editing files (task 6's coder rewrote a test during its own re-review). The coordinator must not treat either signal alone as "the agent is done".
