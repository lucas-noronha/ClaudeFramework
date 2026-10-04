---
doc_type: spec-plan
spec: 0007
summary: How spec 0007 is built — lifecycle events, transcript verdicts, a blocking concurrency-aware gate, a subagent-only git guard, one reconciliation writer — in dependency order, with its Definition of Done and Test plan.
context_budget: ~2000 tokens
---

# Technical plan

**Tier:** structural. **ADR:** framework ADR 0025
(`evolution/decisions/0025-safe-parallel-orchestration.md`, `proposed`). It amends ADRs 0004,
0009, 0011, 0020, 0023 and 0024 §4, and supersedes none. `/tasks` and `/implement` wait until
it is accepted. ADR 0025 settles the mechanics and records the captured hook inputs (NFR-06);
this plan only orders them.

## Approach, in dependency order

1. **Shared helper and lifecycle events.**
   - A new `.claude/hooks/_subagents.py` holds `role_of`, the gate's existing read-only rule
     (moved unchanged) and the transcript readers.
   - `pipeline_metrics.py` logs `subagent_started` (on `SubagentStart`) and `subagent_stopped`
     (on `SubagentStop`), each with `agent_id`, `agent_type` and `role`, stamped with the
     checkout per ADR 0022. The PostToolUse hook keeps logging only `subagent_dispatched`.
2. **Verdict on stop.**
   - The verdict is the first line of the last text-bearing assistant message in
     `agent_transcript_path`, with records sharing its `message.id` joined and leading markdown
     stripped.
   - `spec_id` comes from the first user message and matches both path shapes and both slash
     directions.
   - The PostToolUse verdict parse goes away (FR-01–FR-03).
3. **Gate.** `run_build_test.py`:
   - computes `concurrent` at start from a byte-capped log tail, for this checkout and the open
     feature (or the last 60 minutes when none is open), excluding itself and read-only agents.
     It is omitted when the stopping agent has no start event;
   - `gate_run` gains `agent_id` and `blocked`;
   - on failure it captures the output and exits 2 with a header plus a tail of about 80 lines /
     8 KB on stderr, while `stop_hook_active` is false. When `stop_hook_active` is true it exits
     1, which breaks the loop;
   - when `concurrent` > 0, the header tells the agent not to touch files outside its task;
   - a missing `build_test_cmd` stays a non-blocking exit 1 (FR-06, FR-07, FR-19).
4. **`/metrics`.** `metrics.py`:
   - splits failures into solo and concurrent;
   - counts rework as solo failures plus `Returned` verdicts;
   - shows a "missing verdicts: N" flag;
   - adds the new keys to `--json`;
   - gains `wave-start` and `gates`, so the coordinator sees each wave's final gate results.

   Legacy logs render with identical numbers (FR-04, FR-08, FR-09, NFR-01).
5. **Git guard.** A new `.claude/hooks/subagent_git_guard.py` on PreToolUse `Bash|PowerShell`.
   - It allows at once, with no file read, when there is no `agent_id`/`agent_type` or no `git`
     token.
   - Otherwise it splits compound commands and strips env, `&`, path and `.exe` prefixes. It
     recurses one level into `-c`/`-Command` and skips git's global options.
   - It applies the read-only allowlist, with `branch`/`tag` allowed only as listings, and
     denies with a reason.
   - `hook_should_run` is checked only on the deny path; anything unparseable is allowed
     (FR-10, FR-12, NFR-02, NFR-04, NFR-05).
6. **Prompts.**
   - `coder`, `quickfix` and `reviewer` get the git allowlist rule.
   - `coder` and `quickfix` get the editing rule: the Edit tool or a script file, never a bash
     heredoc or `sed` with backslashes.
   - `reviewer` returns its lines under `Reconciliation:` and never writes them.
   - `Reconciliation:` joins `translation.py`'s `LITERALS` (FR-10, FR-13, FR-18, NFR-07).
7. **Commands.**
   - `/implement`:
     - every task prompt repeats the git rule;
     - the coordinator appends reconciliation lines to the resolver's target;
     - after a wave, a concurrent failure gets one re-run of the build (using `wave-start` /
       `gates`), and the stop rule counts only failures actually returned to a task;
     - the pre-wave delete/rename check runs before dispatch.
   - `/tasks` gets the delete/rename rule (FR-08, FR-11, FR-14, FR-16, FR-17).
8. **Wiring and docs.**
   - Both settings templates get a `SubagentStart` entry, a second `SubagentStop` group and the
     guard. Mode C picks them up through the template merge, recorded for uninstall.
   - `.claude/README.md`, `setup-framework.md` (the gate sentence), the `run_build_test.py`
     docstring and `CHANGELOG.md` are updated.

## Scope check

Each item below is flagged, not folded in silently:

- **Spec alignment, done in this `/plan`.** FR-07 and AC-05 said the gate exits with the
  command's own code, which contradicted FR-19 (exit 2 to block), added later at the user's
  request. Both now defer to FR-19: a failure still fails, exit 2, and the suite runs once.
- **AC-13 ("existing suite passes unchanged").** Any existing test that asserts the gate
  propagates the command's exit code changes with FR-19. Only such assertions may be updated,
  and each one is named in its task.
- **Three interpretations from ADR 0025, for the human to confirm with the ADR:**
  - a second failure in the same stop chain exits 1, not 2;
  - NFR-04's "reads no file" applies to the guard's fast path only;
  - specs 0004 and 0005 will show the missing-verdict flag, though their numbers don't change.
- **Not yet captured, and verified during implementation:**
  - a reviewer transcript's final message, and whether it is written before `SubagentStop`
    fires (a short bounded retry if not);
  - exit-2 blocking for a foreground and a background subagent (AC-15);
  - whether the Agent tool's returned id equals `agent_id`. The fallback is to match failing
    output to tasks by their file lists.

Constitution: no conflict. Everything is stdlib, with no new dependency, and no secrets are
involved.

## Definition of Done

- [ ] The full suite passes, with the Test plan below. Only the gate exit-code assertions named
  under AC-13 change.
- [ ] `reviewer` approved every coder-tier task.
- [ ] AC-01–AC-06, AC-08–AC-10 and AC-13 are covered by tests.
- [ ] AC-07, AC-11 and AC-12 (command prose) are checked by `reviewer`.
- [ ] AC-14: ADR 0025 records the captures.
- [ ] AC-15 is verified in a real session: a deliberately failing gate blocks a foreground and a
  background `coder`, and a second failure exits 1. The result is recorded in
  `reconciliation.md`.
- [ ] `/metrics` on this repo's real log keeps 0004–0006's numbers, and adds only the flag.
- [ ] Framework ADR 0025 is `accepted` before implementation starts.

## Test plan

- P01: `subagent_started` and `subagent_stopped` are logged with `agent_id`, `agent_type` and
  `role`, checkout-stamped — FR-05, AC-04
- P02: `concurrent` at gate start excludes the stopping agent and read-only agents, counts per
  checkout and within the window, and survives a line cut at the tail boundary — FR-06, AC-04
- P03: `concurrent` is omitted when the stopping agent has no start event — FR-06, NFR-01
- P04: the verdict is read from a background reviewer's transcript: `Approved`, `Returned`,
  bold markdown, and split records joined by `message.id` — FR-01, AC-01
- P05: the verdict's `spec_id` is parsed from a legacy path and a folder path, with either slash
  direction — FR-02, AC-02
- P06: PostToolUse no longer logs a verdict, so a foreground reviewer is counted exactly once —
  FR-03, AC-01
- P07: `/metrics` shows "missing verdicts: N" when reviewer dispatches outnumber verdicts —
  FR-04, AC-03
- P08: `/metrics` splits solo and concurrent failures, and rework counts solo failures plus
  `Returned` — FR-09, AC-06
- P09: this repo's real log renders the same numbers as before, plus the flag — NFR-01, AC-13
- P10: the gate exits 2 with a bounded tail on failure while `stop_hook_active` is false, and 1
  when it is true; a pass exits 0; a missing `build_test_cmd` does not block — FR-19, AC-15
- P11: a concurrent failure still fails, the suite runs once, and the header warns about
  sibling files — FR-06, FR-07, AC-05
- P12: `metrics.py wave-start` and `gates` return each wave's final gate results — FR-08, AC-07
- P13: the guard allows every main-session call (no `agent_id`) — FR-12, AC-08
- P14: the guard denies mutating git inside a subagent, table-driven over Bash and PowerShell
  forms (`&&`, `;`, pipes, `git -C`, `& git`, `git.exe`, full paths, `-c k=v`, `--git-dir=`,
  mutating `branch`/`tag` flags) — FR-10, FR-12, AC-08
- P15: the guard allows read-only git and non-git commands without reading a file, and allows
  unparseable input — NFR-02, NFR-04, AC-09
- P16: the guard never blocks in an unregistered mode C repo — NFR-05
- P17: the shipped prompts and settings carry the rules; both templates wire `SubagentStart`,
  `SubagentStop` and the guard; the mode C merge records them for uninstall — FR-10, FR-11,
  FR-18, AC-10
- P18: `translation.py` `LITERALS` include `Reconciliation:` — NFR-07
