---
doc_type: adr
id: 0025
status: accepted
date: 2026-10-04
supersedes: null
superseded_by: null
context_budget: ~4600 tokens
---

# ADR 0025 — Parallel waves share one tree safely: subagent lifecycle events, a blocking gate, a subagent git guard and one reconciliation writer

Like ADR 0001–0024, this documents a decision about *this framework's
own* tooling. It **amends**:

- ADR 0004: orchestration mode gains the coordinator as the only
  reconciliation writer, the subagent read-only git rule, the
  concurrent-failure re-check and the delete/rename pre-wave check.
  `/tasks` gains the delete/rename rule.
- ADR 0009: in a per-task review, `reviewer` returns its lines instead of
  appending them. Its `Edit` tool stays for `/reconcile` sweeps.
- ADR 0011: `reviewer_verdict` moves from PostToolUse to `SubagentStop`,
  which closes the reliability gap that ADR names. New events:
  `subagent_started` and `subagent_stopped`.
- ADR 0020: the gate blocks (exit 2), `gate_run` gains `concurrent`,
  `agent_id` and `blocked`, and rework counts only solo gate failures.
- ADR 0024 decision 4: `reviewer` no longer appends to the
  reconciliation target during `/implement`. The coordinator does.
- ADR 0023: the label `Reconciliation:` joins the invariant markers.

It supersedes none of them. ADR 0005 (one worktree per spec) and ADR
0022 (per-checkout scope) are reused unchanged.

## Context

Spec 0007 is approved, and its FR/NFR/AC are fixed. Specs 0004 and 0005,
run in parallel background waves, showed that one shared working tree,
one reconciliation and one metrics log were never designed for
concurrency:

- verdicts were lost (0/0 for 40 subagents);
- 7 of 15 gate runs failed on a sibling's half-written edit;
- a coder ran `git stash` on the shared tree;
- parallel reviewers raced on the reconciliation;
- a deletion broke a not-yet-run task's references;
- shell heredocs mangled `\n`.

The gate never blocked anything: it returned the test command's exit
code, and Claude Code treats any non-zero code other than 2 from
`SubagentStop` as a non-blocking error.

Facts of the current code shape the answer:

- **`pipeline_metrics.py`** parses the verdict from the `Agent` tool's
  PostToolUse `tool_response`. For a background agent that response is
  "Async agent launched…". `subagent_dispatched` has no agent id and no
  stop pairing.
- **`run_build_test.py`** already owns a read-only rule:
  `NON_CODE_BUILTINS`, plus an agent definition whose `tools:` has no
  `Edit`/`Write`/`MultiEdit`/`NotebookEdit`/`Bash`. `role_of` (prefix
  stripping) is duplicated in `pipeline_metrics.py`. Its output is
  inherited, not captured, so nothing bounded reaches stderr.
- **A missing `build_test_cmd`** returns 1 today: already a non-blocking
  error.
- **`hook_should_run`** (ADR 0017) promises that an unregistered repo
  under mode C never sees "a blocked tool call".
- **Mode C wiring is the multi-project template.**
  `install_user_level.py` resolves `settings.multi-project.json.example`
  and merges it group by group, with idempotency by command. A new event
  key (`SubagentStart`) is created and recorded like any other. Every
  `hooks/*.py` is copied, so a new hook needs no installer code change.

**Captured hook input (NFR-06)**, 2026-10-04, on this machine, with
Claude Code in VS Code. A temporary diagnostic hook dumped raw stdin on
`SubagentStart`, `SubagentStop` and PreToolUse(Bash), while a foreground
general-purpose subagent ran `git status --short`:

- **PreToolUse, main session**: `cwd`, `effort`, `hook_event_name`,
  `permission_mode`, `prompt_id`, `scratchpad_dir`, `session_id`,
  `tool_input`, `tool_name`, `tool_use_id`, `transcript_path`. **No
  `agent_id`, no `agent_type`.**
- **PreToolUse, inside a subagent**: the same keys **plus `agent_id`**
  (e.g. `ad78b50eff97b15aa`) **and `agent_type`**. `session_id` is the
  parent's.
- **`SubagentStart`**: `agent_id`, `agent_type`, `cwd`, `hook_event_name`,
  `prompt_id`, `scratchpad_dir`, `session_id`, `transcript_path` (the
  parent's).
- **`SubagentStop`**: `agent_id`, `agent_transcript_path` (the
  subagent's own JSONL), `agent_type`, `background_tasks`, `cwd`,
  `effort`, `hook_event_name`, `permission_mode`, `prompt_id`,
  `scratchpad_dir`, `session_crons`, `session_id`, `stop_hook_active`,
  `transcript_path`. **No final-message field**, so the verdict is read
  from `agent_transcript_path`.
- **`agent_id` is identical** across `SubagentStart`, the subagent's
  PreToolUse calls and `SubagentStop`.
- **Not yet captured**, and required before the tasks that depend on
  them (AC-14, AC-15):
  - the shape of a reviewer transcript's final assistant message, and
    whether it is flushed when `SubagentStop` fires;
  - exit-2 blocking on `SubagentStop`, for a foreground subagent and for
    a background one.

  Claude Code's documentation states that exit 2 blocks and feeds
  stderr back.

So every NFR-06 fallback is unneeded for the fields captured: the guard
ships, and `concurrent` is computed.

## Options considered

- **Verdict: keep the PostToolUse parse and add a `SubagentStop` one.**
  Rejected. A foreground reviewer would be counted twice (FR-03).
- **Verdict: read the parent transcript's tool result.** Rejected. A
  background result arrives later as a notification whose format isn't
  documented.
- **Concurrency: per-agent lock or marker files** under
  `.worktree-state/`. Rejected. That is new state with its own cleanup,
  and a crashed agent leaves a stale marker. The log already has a
  per-checkout scope (ADR 0022).
- **Concurrency: count `subagent_dispatched`.** Rejected. It has no id,
  no stop, and a background dispatch returns at once.
- **Concurrency: stamp `read_only` at `SubagentStart`.** Rejected. It
  would put a second copy of the read-only rule in the lifecycle hook.
  The gate evaluates siblings with its own rule at count time, so there
  is one rule in one place.
- **Gate: always exit 2 on failure.** Rejected. A failure the subagent
  can't fix (a sibling's file, a broken environment) loops forever.
- **Gate: cap blocks per `agent_id` from the log.** Rejected. That is a
  counter coupled to log tail reads. Claude Code already provides the
  anti-loop signal.
- **Guard: `permissions.deny` rules or an `if: Bash(git *)` filter.**
  Rejected:
  - a deny rule also binds the main session, which FR-12 forbids;
  - neither sees `cd x && git …`, `git -C . …` or PowerShell.
- **Reconciliation: let reviewers keep writing and rely on the Edit
  tool's stale-read retry** (ADR 0024's consequence). Rejected by
  FR-13/FR-14.
- **Reconciliation: one file per task, merged later.** Rejected. It
  changes ADR 0024's layout.
- **FR-08: learn gate outcomes only from subagent reports.** Rejected.
  A failure on the non-blocked last stop happens after the subagent's
  final message, so the subagent never reports it.
- **Chosen:** lifecycle events in the existing log, a gate that blocks
  once per stop chain, a stateless PreToolUse guard, and the coordinator
  as the single reconciliation writer with a log query for gate
  outcomes.

## Decision

1. **Events (`pipeline_metrics.py`, wired on three events).**
   - **`SubagentStart`** logs `subagent_started`
     `{agent_id, agent_type, role}`.
   - **`SubagentStop`** logs `subagent_stopped` `{agent_id, agent_type,
     role}`. When `role == reviewer`, it also logs the verdict (item 3).
   - **PostToolUse `Task|Agent`** logs only `subagent_dispatched`, as
     today. The verdict parse is removed (FR-03).
   - **Common rules.** `role` strips the install prefix (ADR 0017).
     `checkout` is stamped by `log_event` (ADR 0022). Each field is
     present only when the input carries it. The hook never prints and
     always exits 0. `hook_event_name` selects the branch.
   - **One shared helper, `.claude/hooks/_subagents.py`.** Imported,
     never wired, like `_spec_layout.py`. It holds `role_of`,
     `is_read_only(project, agent_type)` (the gate's current rule, moved
     there unchanged) and the transcript readers of item 3. Both hooks
     import it, and the duplicate `_role` goes away.
2. **`concurrent` (`run_build_test.py`, at gate start, FR-06).**
   - **Window.** Read the log from its end in chunks, capped (about
     1 MB), keeping only this checkout's events (`checkout`, absent =
     main). The window starts at this checkout's latest
     `feature_started` that has no matching `feature_finished`, or covers
     the last 60 minutes when no feature is open.
   - **In flight.** For each `agent_id`, take its latest event among
     `subagent_started`, `subagent_stopped` and a `gate_run` with
     `blocked: true`. The agent is in flight when that latest event is a
     start or a blocking gate: a blocked agent was sent back to work
     without a new `SubagentStart`.
   - **Count.** In-flight ids, minus the stopping agent's own `agent_id`,
     minus agents for which `is_read_only` holds (built-ins such as
     Explore, `triage`, `researcher`). A running `reviewer` counts,
     because it has `Edit` and `Bash`.
   - **Unknown.** The field is omitted when the input has no `agent_id`,
     or when the window holds no `subagent_started` for it (the start
     hook isn't wired, or an older Claude Code is running).
   - **Not counted.** A sibling whose gate is running has stopped
     editing, so it doesn't count. A sibling whose stop event isn't
     logged yet counts. That over-count only tags a failure for a
     re-check.
   - **`gate_run` gains** `agent_id`, `concurrent` (when known) and
     `blocked`. `exit_code` stays the command's own code.
3. **Verdict on `SubagentStop` (FR-01, FR-02).**
   - **Reading the transcript.** Read `agent_transcript_path` as JSONL,
     skipping bad lines. The final reply is the text blocks (string or
     `[{type: text}]` content) of the last `assistant` record that has
     text. Records sharing that record's `message.id` are joined in
     order. The tail is read, not the whole file.
   - **Parsing the verdict.** Take the first non-empty line. Strip
     leading markdown (`*`, `_`, `#`, `>`, `-`, spaces). It must then
     start with `Approved` or `Returned`. Anything else logs nothing,
     which covers sweeps and doc verification.
   - **`spec_id`.** From the transcript's first `user` message, with the
     regex `(\d{4})-[\w-]+(?:\.md|[\\/])`, which covers a legacy path, a
     folder path, and both separators.
   - **Field.** `reviewer_verdict` gains `agent_id`.
   - **Duplicates.** A repeated stop (after a block) may log a second
     verdict. `metrics.py` keeps the last verdict per `agent_id`, and
     counts events without an id one by one (the legacy case).
4. **The gate blocks (FR-19), once per stop chain.**
   - **Capture.** The command's stdout and stderr are captured together
     and decoded with `errors=replace`.
   - **Pass**: exit 0.
   - **Fail, with `stop_hook_active` false**: exit 2, `blocked: true`.
     stderr gets a one-line header, then the output's tail. The header
     reads `Build/test gate failed (exit X, concurrent N)`, or without
     `concurrent` when it is unknown. The tail is about 80 lines, capped
     at about 8 KB.
   - **Concurrent failure.** When `concurrent` > 0, the header adds a
     sentence: other subagents are editing this tree, so a failure in
     files outside your task is reported, never fixed by editing them.
   - **Fail, with `stop_hook_active` true**: exit 1 (non-blocking), the
     same stderr, `blocked: false`. The subagent got its one in-context
     fix attempt, and further failures belong to the coordinator (item
     6). This is how FR-19 meets Claude Code's anti-loop signal.
   - **Missing `build_test_cmd`**: still exit 1, a non-blocking nudge.
     A timeout (`timeout: 180`) is non-blocking as well.
   - **Docs.** The docstring, `.claude/README.md` and the
     `/setup-framework` sentences are aligned with this behaviour.
5. **Subagent git guard: `.claude/hooks/subagent_git_guard.py`**
   (PreToolUse, matcher `Bash|PowerShell`, FR-12).
   - **Allow at once**, with no file read, when `agent_id` and
     `agent_type` are both absent (the main session), when
     `tool_input.command` is missing, or when the command has no
     `git`/`git.exe` token.
   - **Parse.**
     - Split the command on `&&`, `||`, `;`, `|` and newlines.
     - Tokenize each segment with both quote styles.
     - Strip a leading `VAR=val`, `env`, `command`, `&`, a path prefix
       and `.exe`.
     - Recurse one level into `bash|sh -c "<s>"`,
       `powershell|pwsh -Command "<s>"` and `cmd /c <s>`.
     - Skip git's global options. `-C`, `-c`, `--git-dir`, `--work-tree`
       and `--namespace` take an argument, and `--no-pager`, `-P` and
       `--bare` don't.
   - **Allowlist (FR-10).**
     - Always allowed: `status`, `diff`, `log`, `show`, `rev-parse`,
       `ls-files`, `check-ignore`, `blame`, `grep`, `cat-file`,
       `describe`.
     - Allowed only in their read form: `worktree list`, `stash list`
       and `stash show`.
     - `branch` and `tag` are allowed only as listings: no positional
       argument unless `-l`/`--list`, and no mutating flag (`-d -D -m -M
       -c -C -f -u -a -s`, `--delete`, `--move`, `--copy`, `--force`,
       `--set-upstream-to`, `--unset-upstream`, `--edit-description`).
     - A bare `git` or `git --version` is allowed.
     - Everything else, aliases included, is denied.
   - **Deny.** Any segment that falls outside the allowlist produces
     `permissionDecision: "deny"`, and nothing ever produces `ask`. The
     reason names the rule ("read-only git inside a subagent, framework
     spec 0007 FR-10") and says to report the command so the main
     session runs it.
   - **Registration, on the deny path only.** Before denying, call
     `hook_should_run`. An unregistered mode C repo is allowed (ADR
     0017). The hot path stays file-free, which is how NFR-04 is read
     here.
   - **Fail open.** Unbalanced quotes, a parser exception or an
     unrecognized shape all allow (NFR-02). No subprocess is started.
6. **Orchestration (`/implement`, `/tasks`, prompts).**
   - **Wave markers and gate query.**
     - Before dispatching a wave, the coordinator runs
       `metrics.py wave-start --feature <id>`, which logs `wave_started`.
     - Once every subagent of the wave has stopped, it runs
       `metrics.py gates`. That prints, as JSON, the latest `gate_run`
       per `agent_id` in this checkout since the last `wave_started`.
   - **Re-check (FR-08).**
     - If any final gate failed with `concurrent` > 0, the coordinator
       runs the project's build/test command once.
     - If it passes, the concurrent failures are cleared.
     - If it fails, the coordinator attributes the failing output to
       tasks by their reported file lists and returns it to them.
     - A solo final failure is returned as is.
     - Step 7's "fails its gate twice" counts returned failures only.
   - **Dispatch prompt (FR-11).** Every task prompt repeats the FR-10
     allowlist and "never revert the tree to check a baseline: use
     `git show HEAD:<path>` or `git diff -- <paths>`".
   - **Reconciliation (FR-13–FR-15).**
     - In every per-task review, `reviewer` returns its lines under a
       line reading exactly `Reconciliation:`, after the verdict and any
       `Advisory:`/`Rule may be stale:`/`Constitution conflict:` lines.
       It never edits the reconciliation target in that scope.
     - The coordinator appends them verbatim with Edit, one reply at a
       time, to the resolver's target: `reconciliation.md`, or the
       `## Reconciliation` section of a legacy or lite file.
     - The PostToolUse Edit still logs `reconciliation_snapshot`.
     - `/reconcile` and `/review` under `final-only` stay single writers.
   - **Delete/rename (FR-16, FR-17).** No new task field: the
     `Depends on` and box formats stay as they are.
     - `/tasks` either folds the reference updates into the deleting or
       renaming task, or makes that task depend on every task that
       removes a reference. References are found by searching the repo
       when the tasks are written.
     - At step 5, `/implement` reads each wave task's text for deletes
       and renames, searches the other wave tasks for references, and
       splits any pair it finds: the referencing task goes first.
   - **Prompts.**
     - `coder`, `quickfix` and `reviewer` state the FR-10 allowlist.
     - `coder` and `quickfix` alone state FR-18 (Edit/Write tools; a
       script goes to a file and runs from there; no escapes through a
       heredoc, `echo`, `printf` or `sed`). They also state "a gate
       failure in files outside your task is reported, never fixed".
     - All new prompt text is translated as usual. `Reconciliation:`
       joins `translation.py`'s `LITERALS` (ADR 0023, NFR-07).
7. **`/metrics` (`metrics.py`, FR-04, FR-09).**
   - **Gate failures.** A failure is a `gate_run` with a non-zero
     `exit_code`. It is concurrent when `concurrent` > 0, and solo
     otherwise, including when the field is absent.
   - **Rework** = solo failures + `Returned`.
   - **Missing verdicts.** Reviewer dispatches are `subagent_dispatched`
     events whose `role` (or prefix-stripped `subagent_type`) is
     `reviewer`. Verdicts are deduplicated per item 3. When dispatches
     exceed verdicts, the row is flagged `⚠ missing verdicts: N`.
   - **Table.** The table shows `solo/concurrent` failures, and the
     lane table adds the same averages.
   - **`--json`** keeps `gate_failures` and adds `gate_failures_solo`,
     `gate_failures_concurrent`, `reviewer_dispatches` and
     `missing_verdicts`.
   - **Old logs.** A log with no new fields gives the same numbers as
     today (NFR-01). On this repo, 0004 and 0005 newly show the
     missing-verdict flag, which is FR-04's purpose.
8. **Wiring.**
   - **Both settings templates**:
     - `SubagentStart` runs `pipeline_metrics.py`;
     - `SubagentStop` gains a separate `pipeline_metrics.py` group next
       to the gate;
     - PreToolUse gains `Bash|PowerShell` → `subagent_git_guard.py`,
       with no `if`.
   - **Mode C** inherits all of it through the template. A re-run of the
     installer merges the new groups and records them for uninstall.

## Rationale

The log already is the per-checkout shared memory that ADR 0022 made
safe for concurrent appends. Pairing starts and stops by the one id
Claude Code keeps stable answers "who else is editing" without new state.

Reading the verdict where the reviewer actually ends works the same for
foreground and background agents.

`stop_hook_active` is Claude Code's own loop breaker. Blocking once per
stop chain gives the cheap in-context fix, and leaves anything the
subagent can't fix to the coordinator, which sees the whole wave.

The guard is stateless and keyed on a field that only subagent calls
carry, so the main session can't be caught by it.

## Consequences

- **The gate's exit code is no longer the command's.** The log keeps the
  real code in `exit_code`, and `blocked` tells a forced retry from a
  final failure.
- **One in-context retry only.** A subagent whose fix fails ends with a
  red gate. The coordinator's `gates` query is the only place that
  surfaces it.
- **A concurrent failure still blocks** (FR-19). The subagent then
  spends a turn on a sibling's breakage. The header sentence and the
  prompt rule are the mitigation, not a guarantee.
- **The guard costs a Python start on every Bash or PowerShell call**, in
  every session, before its fast path returns. It is fail-open and
  bypassable through shapes it doesn't parse: it guards against
  accidents, not adversaries.
- **Every subagent loses tree-changing git**, user-launched ones
  included, `add`/`commit` among them. The main session must run them.
- **`concurrent` is an approximation**: a time-window over-count, a lost
  stop counted until the feature closes, and siblings mid-gate not
  counted.
- **Two `SubagentStop` handlers run in parallel**, so the gate never
  relies on its own stop being logged.
- **Two new `metrics.py` subcommands, one new event** (`wave_started`)
  and one new helper module.
- **Unverified pieces.** Transcript flush timing, the message shape and
  exit-2 on background agents rest on the captures listed above, which
  are still pending.

## References

`evolution/product/specs/0007-safe-parallel-orchestration/spec.md`,
`evolution/decisions/0004-plan-tasks-implement-rebalance.md`,
`evolution/decisions/0009-per-task-spec-reconciliation.md`,
`evolution/decisions/0011-pipeline-metrics.md`,
`evolution/decisions/0017-user-level-install-mechanics.md`,
`evolution/decisions/0020-proportional-pipeline-cost.md`,
`evolution/decisions/0022-worktree-sessions.md`,
`evolution/decisions/0023-setup-language.md`,
`evolution/decisions/0024-spec-folders.md`,
`.claude/hooks/pipeline_metrics.py`, `.claude/hooks/_pipeline_metrics.py`,
`.claude/hooks/run_build_test.py`, `.claude/scripts/metrics.py`,
`.claude/scripts/install_user_level.py`, `.claude/commands/implement.md`,
`.claude/commands/tasks.md`, `.claude/agents/coder.md`,
`.claude/agents/quickfix.md`, `.claude/agents/reviewer.md`,
`.claude/settings.example.json`,
`.claude/settings.multi-project.json.example`
