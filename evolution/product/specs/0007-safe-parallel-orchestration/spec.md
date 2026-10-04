---
doc_type: spec
id: 0007
status: implemented
tier: structural
area: pipeline-cost
relates_to: [0003, 0006]
summary: How does `/implement` run coder and reviewer subagents in parallel, and in the background, without them undoing each other's work in the shared working tree, losing writes to the spec's reconciliation, or skewing `/metrics`?
notFor: How waves are computed from `Depends on` (framework ADR 0004), what the build/test gate runs (the project's `build_test_cmd`), or whether a spec gets its own worktree (framework ADR 0005). Those stay as they are.
context_budget: ~5300 tokens
---

# Safe parallel orchestration — parallel waves that neither undo each other nor skew the metrics

## Feature name

`/implement`'s orchestration mode runs a wave of `coder`/`quickfix` subagents, and then their
`reviewer` passes, in parallel and often in the background, in one shared working tree. This
spec makes that safe: every reviewer verdict is recorded, a gate failure caused by a sibling's
half-finished edit is told apart from a real one, no subagent changes the tree under its
siblings, only one writer touches the spec's reconciliation, and `/tasks` stops producing tasks
that break each other inside a wave.

## Business context

**Today, before this spec**, implementing specs 0004 and 0005 with `/implement` in parallel
background waves went wrong in six concrete ways:

- **Reviewer verdicts were lost.** `pipeline_metrics.py` reads `Approved`/`Returned` from the
  `Agent` tool's PostToolUse `tool_response`. For a background agent that response is only
  "Async agent launched…", so the verdict never reaches the log. `/metrics` shows **0/0
  verdicts** for both features (0004: 10 subagents; 0005: 30 subagents), although every
  coder-tier task was reviewed. Framework ADR 0011 had named this event as the one with "a real
  reliability gap", and the gap failed silently, as it predicted.
- **Gate failures were inflated.** The build/test gate (`run_build_test.py`, on `SubagentStop`)
  runs the whole suite while sibling tasks are still mid-edit in the same tree. A task's gate
  failed because of another task's half-written work: a deleted template still referenced
  elsewhere, a sibling's syntax error, a placeholder not yet resolved. Spec 0005 logged **7
  gate failures in 15 gate runs**, almost all of this kind, and `/metrics` counts every one as
  rework. The data framework ADR 0020 says `review_policy` should be chosen from is therefore
  wrong for any project that runs parallel waves.
- **A coder ran `git stash` / `git stash pop`** on the shared tree to check a baseline. For about
  two minutes every sibling agent saw all uncommitted changes vanish, its own included.
- **Concurrent writes to the reconciliation.** Several parallel reviewers appending to the same
  `## Reconciliation` section risked lost writes. The coordinator worked around it by hand,
  having reviewers return their lines and writing them itself. Spec 0006 separates
  reconciliation into its own file, but parallel reviewers would still write that one file at
  once.
- **Cross-task gaps inside a wave.** A task deleted a file that another, not-yet-run task was
  supposed to stop referencing, and the suite stayed red for several waves. The coordinator had
  to move scope between tasks mid-sweep (spec 0005, task 10 absorbing part of task 11).
- **Shell escaping broke test files twice.** Agents editing Python through a Git Bash heredoc or
  `sed` had `"\n"` turned into a literal newline.

- **The build/test gate never blocked anything.** `run_build_test.py` returns the test
  command's own exit code. A failing `unittest` run exits 1, and Claude Code treats any non-zero
  code other than 2 from a `SubagentStop` hook as a non-blocking error. The subagent finishes
  anyway, with a broken suite. In specs 0004–0006 the only thing that held tasks back was the
  coordinator re-running the suite by hand. `/setup-framework` nevertheless documents the gate
  as blocking on a failed build.

The problem in one sentence: parallel waves share one working tree, one reconciliation and one
metrics log, and nothing in the framework accounts for that sharing, so agents undo each other's
work and `/metrics` reports numbers that are wrong in both directions.

The fix keeps the sharing and makes it safe. One worktree per spec stays (framework ADR 0005):
tasks do not get worktrees of their own.

## Functional requirements

### Reviewer verdicts

- FR-01: A reviewer's verdict is detected when the reviewer **stops**, not when it is
  dispatched. On `SubagentStop`, when the stopping agent's role is `reviewer` (an install
  prefix such as `cfw-` stripped, framework ADR 0017), the hook reads the reviewer's final
  reply and logs `reviewer_verdict` (`Approved` or `Returned`) under the reviewer's documented
  reply format. The reply comes from the reviewer's transcript (`agent_transcript_path`, its
  last assistant message), or from a final-message field when the hook input carries one. This
  works the same for foreground and background reviewers.
- FR-02: The verdict's `spec_id` stays best-effort. It is parsed from the reviewer's prompt (the
  transcript's first user message) and accepts both spec shapes: a legacy `NNNN-x.md` path and
  a spec-folder `NNNN-x/...` path (spec 0006). A reply with no verdict (a `/reconcile` sweep, a
  doc-verification pass) logs nothing, as today.
- FR-03: The PostToolUse verdict parse is removed, so a foreground reviewer is counted exactly
  once. `subagent_dispatched` stays on PostToolUse, unchanged.
- FR-04: `/metrics` flags a feature whose `reviewer` dispatches outnumber its recorded verdicts
  ("missing verdicts: N"), so a silent loss like the one in 0004/0005 shows up the first time
  it happens.

### Gate failures under concurrency

- FR-05: The log records each subagent's lifecycle from Claude Code's own hook events:
  `subagent_started` on `SubagentStart` and `subagent_stopped` on `SubagentStop`. Both carry
  `agent_type`, `role` and `agent_id` when the hook input provides one. Like every event, they
  are stamped with `checkout` in a linked worktree (framework ADR 0022). The input fields are
  confirmed before implementation (NFR-06).
- FR-06: Every `gate_run` gains `concurrent`: how many **other** subagents were in flight in the
  **same checkout** at the moment the gate **started**. Rules for the count:
  - Every in-flight subagent counts, a running `reviewer` included, except agents declared
    read-only: built-ins such as Explore, and agent definitions with no write-capable tool, such
    as `triage` and `researcher` (the same read-only rule the gate already applies).
  - The stopping agent never counts itself: its own stop is accounted for before the count.
  - The count uses this checkout's events since its open feature started (a bounded recent
    window when none is open), so a start whose stop was lost stops counting once that window
    closes.
  - When no start signal is available, the field is omitted, meaning "unknown".
- FR-07: The gate runs the same command, once. A pass exits 0; a failure exits as FR-19 says
  (2, blocking). The hook never re-runs the suite. It only records `concurrent`, which tags a
  failure as concurrent and never turns it into a pass.
- FR-08: `/implement`'s coordinator handles a concurrent failure. When a task's gate fails with
  `concurrent` > 0, it waits until the wave's other in-flight tasks have stopped, then runs the
  project's build/test command once more. Only if that re-check still fails does it return the
  failure to the task's subagent, and only then does the failure count toward step 7's "fails
  its gate twice" stop rule.
- FR-09: `/metrics` splits gate failures into **solo** (`concurrent` = 0 or absent) and
  **concurrent** (`concurrent` > 0). Rework becomes solo gate failures plus `Returned`
  verdicts. The `--json` output keeps `gate_failures` as the total and adds
  `gate_failures_solo` and `gate_failures_concurrent`. The per-lane table follows the same
  split.

### Working-tree safety

- FR-10: The `coder`, `quickfix` and `reviewer` prompts allow only **read-only git
  subcommands**: `status`, `diff`, `log`, `show`, `rev-parse`, `ls-files`, `check-ignore`,
  `blame`, `grep`, `cat-file`, `describe`, `worktree list`, `stash list`/`stash show`, and
  `branch`/`tag` used only to list. Every other git command is forbidden to them, `add` and
  `commit` included. To compare against the baseline, an agent reads `git show HEAD:<path>` or
  `git diff -- <paths>`, and never reverts the tree to check. A failure it suspects was already
  there is reported as such, not proven by reverting.
- FR-11: `/implement`'s wave dispatch repeats the FR-10 rule in every task prompt it hands a
  subagent. A subagent whose own prompt lacks the rule (a general-purpose agent, an older
  install) still gets it.
- FR-12: A **git guard hook** (PreToolUse on the `Bash` and `PowerShell` tools) enforces FR-10
  for tool calls made **inside a subagent**:
  - It denies a git command outside the FR-10 allowlist, with a reason that names the rule and
    says the main session runs the command if it is really needed. It denies rather than asks,
    because a background agent cannot answer an `ask`.
  - It never blocks a call from the main session, the `/implement` coordinator included.
  - It does not depend on whether a feature or sweep is open: inside a subagent, the allowlist
    always applies.
  - It finds `git` after a `cd`, after `&&`/`;`/`|`, and behind global options (`-C <path>`,
    `-c k=v`).
  - It ships in both settings templates and in the mode C installer's hook set.

  **Prerequisite:** a reliable signal in the PreToolUse input that the call comes from a
  subagent, such as an `agent_id`/`agent_type` field, confirmed by capturing real input
  (NFR-06). **If no reliable signal exists, the guard is not shipped**, and FR-10 and FR-11's
  prompt rules are the whole enforcement.

### Reconciliation writes

- FR-13: In every per-task review that `/implement` runs, in both modes and in a wave of one,
  `reviewer` never writes the reconciliation. It returns its lines in its reply: after the
  verdict and any `Advisory:`/`Rule may be stale:`/`Constitution conflict:` lines, under a line
  reading exactly `Reconciliation:`, one line each, in today's exact format
  (`- [task N] FR-03: matches spec`, `… diverged — <reason>`, `- [task N] out of scope: <file>
  — …`).
- FR-14: The `/implement` coordinator appends those lines verbatim, one reviewer reply at a
  time, append-only:
  - a spec folder (spec 0006) gets them in `reconciliation.md`;
  - a legacy or lite spec gets them in the spec file's `## Reconciliation` section.

  No subagent writes the reconciliation during `/implement`.
- FR-15: Single-writer paths are unchanged: the `/reconcile` sweep's `### Sweep` block and
  `/review`'s entries under `review_policy: final-only` (framework ADR 0020).

### Cross-task gaps

- FR-16: `/tasks` adds a rule for any task that **deletes or renames** something: a file,
  template, symbol, config key, command or agent. Either that task also removes or updates
  every reference to it, found by searching the repository when the tasks are written, or every
  task that removes those references precedes it (it depends on them). This is mechanical
  bookkeeping, not a new technical judgment.
- FR-17: Before dispatching each wave, `/implement` checks the wave (orchestration step 5) and
  never puts in one wave a task that deletes or renames something together with a task that
  still references it. Such a pair runs in sequence, the referencing task first.

### Editing discipline

- FR-18: The `coder` and `quickfix` prompts require editing files with the Edit/Write tools. When
  a transformation needs a script, the agent writes the script to a file and runs it. It never
  passes code containing backslash escapes through a shell heredoc, `echo`, `printf` or a `sed`
  one-liner.

- FR-19: The build/test gate **blocks**. When the project's build/test command fails,
  `run_build_test.py` exits with code 2 and writes the command's failure output (bounded to its
  last lines) to stderr. Where Claude Code honours it, it keeps the subagent running and hands it
  the failure to fix. That hand-off is best-effort: a subagent that ends through a
  `SubagentHandback` tool call is not resumed by exit 2 (captured in task 9). So `/implement`
  never relies on it: it reads each task's gate result with `metrics.py gates` once the
  subagent's completion notification arrives, and returns a failure to that subagent itself.
  A passing run still exits 0. A missing `build_test_cmd` stays a non-blocking nudge.
  A failure the hook tags as concurrent (FR-05) still blocks the subagent; the tag only changes
  how `/metrics` counts it and lets the coordinator re-check it once (FR-07). The
  `/setup-framework` sentences that call the gate blocking become true, and they are checked
  against this behaviour.

## Non-functional requirements

- NFR-01: **Backward-compatible log.** New events and fields are additive. A log with none of
  them reports exactly as today: an event without `concurrent` counts as solo, and old
  `reviewer_verdict` events are read unchanged. On this repository's own log, 0004 and 0005
  keep 1 and 7 gate failures, all of them solo. An older `metrics.py` ignores the new events.
- NFR-02: **Fail-open hooks.** No new hook path raises, and none blocks on input it doesn't
  recognize. The verdict and lifecycle logging skip silently. The guard **allows** whenever it
  cannot parse the command or cannot tell that the call comes from a subagent. The gate's exit
  code stays the command's own (FR-07).
- NFR-03: **No new dependency.** Stdlib only, file reads only, no subprocess in the lifecycle
  logging or in the guard.
- NFR-04: **Bounded per-hook cost.** The guard reads no file. It returns at once when the
  command has no `git` token. Lifecycle counting reads only the tail of the log (the current
  feature's window), never the whole file.
- NFR-05: **Every mode, every checkout.** This holds in modes A, B and C and for prefixed role
  names. Concurrency is scoped to the checkout (framework ADR 0022): subagents running in
  another worktree never count as concurrent here. The guard depends only on whether the call
  comes from a subagent, never on the checkout.
- NFR-06: **Prerequisite — hook input verified, not assumed.** Before implementation, real hook
  input is captured, as framework ADR 0020 did for `SubagentStop`, to confirm:
  - `SubagentStart`'s `agent_id`/`agent_type`;
  - `SubagentStop`'s `agent_id`;
  - the shape of the reviewer transcript's final assistant message;
  - the PreToolUse field that marks a call made inside a subagent.

  What is found is recorded in the framework ADR. Each field has a fallback:
  - no start signal → `concurrent` is omitted;
  - no subagent marker in PreToolUse → no guard, prompt rule only (FR-12).
- NFR-07: **Language** (spec 0005 FR-08). Event names, field names, `Approved`/`Returned`, the
  `Reconciliation:` label and the outcome phrases stay English in every setup language. The new
  prompt rules are translated like the rest of their prompts.

## Explicitly out of scope

- A worktree per task or per wave. One shared worktree per spec stays (framework ADR 0005).
- Serializing gates, replacing per-task gates with one gate per wave, or having the gate hook
  re-run the suite.
- Reclassifying 0004/0005's past gate failures. The log holds no concurrency data for them.
- Restricting git in the main session, the coordinator included, or in the human's own
  terminal. A subagent that needs a tree-changing git command reports it, and the main session
  runs it.
- Guarding destructive non-git commands (`rm -rf`, file moves).
- The editing rule (FR-18) in `reviewer` or any agent other than `coder` and `quickfix`, or a
  hook that enforces it.
- Changing how waves are computed, `review_policy`, or the reviewer's checklist and verdict
  rules.

## Roles and permissions involved

- The developer running `/implement` and reading `/metrics`.
- The `/implement` coordinator session. It becomes the only writer of per-task reconciliation
  lines and re-checks concurrent gate failures. Its git commands are never restricted.
- The `coder`, `quickfix` and `reviewer` subagents. They lose every git command outside the
  read-only allowlist, and `reviewer` loses its per-task reconciliation write.
- The framework maintainer, who chooses `review_policy` from `/metrics`.

## Related specs

- 0003-proportional-pipeline-cost — extends FR-05 (verdicts actually recorded; gate failures
  split, so rework means rework) and FR-02 (the gate gains `concurrent`; when it runs is
  unchanged).
- 0006-spec-folders — compatible with its FR-02/FR-08 (per-task lines land in
  `reconciliation.md` for a folder, in the section for a legacy or lite spec) and its FR-13 (the
  verdict's spec id is parsed from both path shapes); complements its NFR-06, whose separate
  files still leave `reconciliation.md` with concurrent writers.

## Acceptance criteria

- [ ] AC-01: A background reviewer replying `Approved`, another replying `Returned`, and a
  foreground reviewer each log exactly one `reviewer_verdict` with the right verdict. `/metrics`
  counts all three. (FR-01, FR-03)
- [ ] AC-02: The verdict's `spec_id` is parsed from a legacy path and from a folder path. A
  prefixed `cfw-reviewer` is recognized. A sweep or doc-verification reply logs nothing.
  (FR-01, FR-02, NFR-05)
- [ ] AC-03: A feature with more reviewer dispatches than verdicts is flagged by `/metrics`
  ("missing verdicts: N"), and one with equal counts is not. (FR-04)
- [ ] AC-04: `concurrent` is counted correctly. (FR-05, FR-06, NFR-05)
  - With two code-writing subagents in flight in one checkout, the first gate to start records
    `concurrent: 1`.
  - A lone subagent's gate records `concurrent: 0`.
  - A running `reviewer` is counted.
  - A subagent declared read-only (Explore, `triage`, `researcher`) is not counted.
  - A subagent in flight in another worktree is not counted.
- [ ] AC-05: A failing gate with `concurrent` > 0 still fails (exit 2 per FR-19, never a pass),
  and the hook runs the command only once. With no start signal, `concurrent` is omitted.
  (FR-05, FR-06, FR-07, NFR-02)
- [ ] AC-06: Given a log with solo and concurrent failures, `/metrics` shows the split, and
  rework counts only solo failures plus `Returned` verdicts. `--json` has `gate_failures`,
  `gate_failures_solo` and `gate_failures_concurrent`. A log with no new fields reports exactly
  as today. (FR-09, NFR-01)
- [ ] AC-07: `/implement` says that a concurrent gate failure is re-checked once, after the
  wave's other tasks stop. The failure is returned and counted toward the stop rule only if the
  re-check fails. (FR-08)
- [ ] AC-08: The guard behaves as follows, through both `Bash` and `PowerShell`. (FR-10, FR-12,
  NFR-02)
  - Inside a subagent, it denies `git stash`, `git -C . reset --hard`,
    `cd x && git checkout -- f`, `git clean -fd`, `git rm --cached f`, `git add f` and
    `git commit -m x`.
  - Inside a subagent, it allows `git status`, `git diff -- f`, `git log`, `git show HEAD:f`,
    `git ls-files`, `git worktree list` and `git stash list`.
  - The same denied commands are allowed from the main session.
  - It allows everything when the input is unparsable or carries no subagent marker.
- [ ] AC-09: A command with no `git` token makes the guard return at once, reading no file.
  (NFR-04)
- [ ] AC-10: The shipped prompts and settings carry the new rules. (FR-10, FR-11, FR-12, FR-18)
  - The `coder`, `quickfix` and `reviewer` prompts and `/implement`'s wave dispatch state the
    FR-10 allowlist.
  - The `coder` and `quickfix` prompts, and no other agent, state the FR-18 editing rule.
  - When the guard ships, both settings templates and the mode C installer wire it.
- [ ] AC-11: Reconciliation lines have one writer. (FR-13, FR-14, FR-15)
  - The `reviewer` prompt returns per-task lines under `Reconciliation:` in every `/implement`
    review, a wave of one included, and never edits the reconciliation in per-task scope.
  - `/implement` appends them to `reconciliation.md` for a folder spec and to
    `## Reconciliation` for a legacy or lite spec.
  - `reconciliation_snapshot` is still logged after the coordinator's write.
- [ ] AC-12: `/tasks` states the delete/rename rule, and `/implement` states the pre-wave check
  that runs a deleting task after the tasks still referencing what it deletes. (FR-16, FR-17)
- [ ] AC-13: No new dependency, and the existing test suite passes unchanged. (NFR-01, NFR-03)
- [ ] AC-14: The framework ADR records the captured hook input for every NFR-06 field. Where a
  field is missing, what ships is the documented fallback: `concurrent` omitted, or no guard and
  the prompt rule only. (NFR-06, FR-05, FR-12)

- [ ] AC-15: A `coder` stop with a failing suite gets exit code 2 and the failure tail on stderr,
  and the failure reaches the subagent either way: through exit 2 where Claude Code resumes it,
  otherwise through `/implement` returning it after reading `metrics.py gates`. A passing suite
  exits 0; a missing `build_test_cmd` does not block. Verified with the hook run against a temp
  project, and once against a real Claude Code session (the exit-2 semantics are captured like
  the other NFR-06 fields). (FR-19)

## Impact on existing architecture

- **Framework ADR 0011:** `reviewer_verdict` moves from PostToolUse to `SubagentStop`, which
  closes the reliability gap that ADR names. New events: `subagent_started` and
  `subagent_stopped`. `gate_run` gains `concurrent`.
- **Framework ADR 0020:** rework is redefined (solo gate failures only), with new `/metrics`
  columns and the missing-verdict flag. The gate's log entry changes, its behaviour does not.
- **Framework ADR 0004:** orchestration mode gains:
  - the coordinator as sole reconciliation writer;
  - the read-only git rule for subagents;
  - the concurrent-failure re-check;
  - the delete/rename pre-wave check.

  `/tasks` gains the delete/rename rule.
- **Framework ADR 0009:** reviewer returns its per-task lines instead of appending them. Its
  `Edit` tool stays, because `/reconcile` sweeps still need it.
- **Framework ADR 0005 and 0022:** unchanged. One worktree per spec stays, and per-checkout
  scoping is reused as is.
- **New hook:** the subagent git guard, in both settings templates and the mode C installer,
  subject to FR-12's prerequisite.

Structural tier expected: a new framework ADR at `/plan`, amending 0004, 0009, 0011 and 0020.
It also records the NFR-06 captures.

