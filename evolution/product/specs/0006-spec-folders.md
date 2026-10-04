---
doc_type: spec
id: 0006
status: approved
area: pipeline-cost
relates_to: [0003]
summary: How does each spec become a folder of separate files (requirements, plan, tasks, reconciliation) so that every agent loads only the part it needs?
notFor: What a spec's requirements, plan or tasks must contain. Those content rules stay in requirements-template.md and the pipeline commands.
context_budget: ~5000 tokens
---

# Spec folders — one folder per spec, one file per artifact

## Feature name

Each spec becomes a folder named like its file is named today. Inside it, each pipeline artifact
gets its own file: the requirements (`spec.md`), the technical plan (`plan.md`), the task list
(`tasks.md`) and the reconciliation log (`reconciliation.md`), plus any extra file a pipeline
step needs to finish. An agent loads only the file it needs.

## Business context

**Today, before this spec**, a spec is one file, `product/specs/NNNN-short-name.md`, and every
pipeline step appends to it:

- `/spec` writes the requirements and an empty `## Reconciliation`;
- `/plan` appends `## Technical plan` (approach, scope check, Definition of Done, Test plan);
- `/tasks` appends `## Tasks`;
- `reviewer` appends one line per task and claimed FR/AC to `## Reconciliation`, and every
  `/reconcile` sweep appends a block there too.

The file keeps growing after the requirements are validated, and every agent that needs any
part of it reloads all of it. Spec 0004 is the concrete case: 329 lines, ~5,200 tokens. Its
requirements (feature name to impact on architecture) are ~2,100 tokens; the technical plan is
~1,600, the tasks ~1,000 and the reconciliation ~400. A `coder` working on one of its tasks needs
the requirements, its own task and that task's tests. It still loads the plan for every other
task, the other tasks and the review history, which is ~60% of what it reads. Spec 0005 is
~7,000 tokens, with the same proportion. The cost repeats for each task, each `reviewer` pass,
each `/review` and each `/reconcile`.

A second cost comes from parallel waves. `/implement` checks a box and `reviewer` appends a
reconciliation line in the same file, at the same time, for different tasks.

The problem in one sentence: an agent pays, in context, for every artifact of a spec, even
though its step needs only one or two of them.

## Functional requirements

- FR-01: **A spec is a folder.** `/spec` creates `product/specs/NNNN-short-name/`, which is
  today's file name without `.md`. The spec's `#` title stays inside `spec.md`. Numbering stays
  sequential and per project. Every writer of a new spec creates a folder: `/spec`, `/quick`
  (FR-06) and `migrate_context.py` (FR-18).
- FR-02: **One file per artifact**, each with a single owner:

  | File | Created by | Holds |
  | --- | --- | --- |
  | `spec.md` | `/spec` | Frontmatter and the requirement sections, from "Feature name" to "Impact on existing architecture". The stakeholder validates this file alone. |
  | `plan.md` | `/plan` (standard and structural tiers) | Approach, ADR reference, scope check, Definition of Done, Test plan. |
  | `tasks.md` | `/tasks` | `## Tasks`, in today's checkbox format. `/implement` checks its boxes here. |
  | `reconciliation.md` | `/spec`, empty | `## Reconciliation`. `reviewer` writes its per-task lines only here, and `/reconcile` its `### Sweep` blocks. |

  There is no per-folder index or `README.md`. Each file's `summary` and the specs index (title,
  area, status) cover that role. None of these steps appends to `spec.md`: after approval, the
  only lines that change in it are `status` and `tier` (FR-04).
- FR-03: **Frontmatter.** `spec.md` carries today's spec frontmatter (`status` stays there,
  exactly as today) plus `tier` (FR-04). Every other file carries a minimal frontmatter:
  - `doc_type`: `spec-plan`, `spec-tasks`, `spec-reconciliation` or `spec-note`;
  - `spec: NNNN`;
  - `summary`: what this file answers;
  - `context_budget`.

  It never carries `status`. `frontmatter_check.py` requires `status` only on `spec.md` and on
  non-spec docs.
- FR-04: **The tier lives in `spec.md`.** `/plan` records `tier: trivial | standard | structural`
  in the frontmatter of `spec.md`, for every tier, in the same edit as the approval. A trivial
  spec gets no `plan.md`. `/implement`, the hooks and `/metrics` read the tier from there. A lite
  spec already carries `tier: standard` (FR-06).
- FR-05: **Extra files.** A pipeline step may add a file the spec needs to finish, for example
  `research.md` (`researcher`'s findings), a data-migration runbook or a diagram. It sits
  directly in the folder, never in a subfolder, and carries the FR-03 frontmatter
  (`doc_type: spec-note`, with a `summary`). An extra file never holds requirement, plan, task or
  reconciliation content: those have a fixed home (FR-02).
- FR-06: **Lite specs are folders with a single file.** `/quick` writes
  `product/specs/NNNN-quick-<short-name>/spec.md`, for example `0012-quick-feature-x/spec.md`.
  That one file keeps today's lite content:
  - frontmatter with `lite: true` and `tier: standard`;
  - context, FRs and ACs;
  - the inline `## Tasks` and an empty `## Reconciliation`.

  There is no `plan.md`, `tasks.md` or `reconciliation.md` in a lite folder. Hooks read a lite
  spec's tasks and reconciliation from its `spec.md`. `lite: true` decides this, not the
  `quick-` in the folder name.
- FR-07: **Each task carries its own context.** `/tasks` copies into each task:
  - the Test plan lines that its `Tests:` field names, with their full text;
  - for a task in a structural spec, a pointer to the part of `plan.md`'s approach that
    applies to it (heading or step number), or a short excerpt of it.

  The copied text sits under the task's checkbox line as indented plain bullets, never as
  checkboxes, so it never changes the box count of FR-10. The checkbox line and its
  `Depends on:`/`Tests:` fields stay as today.
- FR-08: **Each step loads only its files:**

  | Step | Reads | Writes |
  | --- | --- | --- |
  | `/spec` | the specs index | `spec.md`, `reconciliation.md` |
  | `/plan`, `triage`, `architect` | `spec.md` | `plan.md`; `status` and `tier` in `spec.md` |
  | `/tasks` | `plan.md`, plus the FR/AC ids in `spec.md` | `tasks.md` |
  | `/implement` (orchestrator) | `tasks.md`, `tier` in `spec.md` | checkboxes in `tasks.md` |
  | `coder`, `quickfix` (one task) | its full task text, `spec.md` | code and tests |
  | `reviewer` (one task) | the task text, the file list, `spec.md` | `reconciliation.md` |
  | `/review` | `spec.md`, the Definition of Done in `plan.md`, `reconciliation.md`, `tasks.md` | — |
  | `/reconcile` | `spec.md`, `reconciliation.md` | `reconciliation.md` |

  `/implement` passes each subagent its full task text (FR-07) and the path of `spec.md`, which
  gives the overview of the feature. A per-task agent never reads `tasks.md` as a whole or
  `reconciliation.md`. It opens `plan.md` only when its task text is not enough, and says so in
  its report.
- FR-09: **Invariant markers** (spec 0005 FR-08). The file names `spec.md`, `plan.md`,
  `tasks.md` and `reconciliation.md` are English in every setup language. `## Tasks` stays the
  heading of `tasks.md`, and `## Reconciliation` the heading of `reconciliation.md` (or the
  sections of a lite `spec.md`). The checkbox format, the `Depends on:`/`Tests:` fields and the
  reconciliation outcome phrases do not change.
- FR-10: **Status across files.** `status` lives only in `spec.md`. When every box in a folder's
  `tasks.md` is checked (a lite spec: every box in its own `## Tasks`), `spec_status_sync.py`
  flips `spec.md` from `approved` to `implemented`, under the same rules as today (never from
  `draft`). It reacts to edits of `tasks.md` and of `spec.md`. The same run logs
  `spec_implemented` and refreshes the specs index.
- FR-11: **Numbering.** `spec_number_guard.py` denies a new spec whose `NNNN` is already used
  by a folder `NNNN-*/` (lite folders included) or by a legacy file `NNNN-*.md`. Any file in a
  new `NNNN-*` folder counts as creating that spec. `/spec` and `/quick` pick the next number
  across every shape.
- FR-12: **Specs index.** `spec_index.py` lists folders and legacy files in one table. For a
  folder it reads the frontmatter and title from `spec.md`, and it links the row to that
  `spec.md`. Any write inside a folder refreshes the index.
- FR-13: **Metrics and the session brief.**
  - `spec_created` fires on the first write of a folder's `spec.md` with `status: draft`.
  - `reconciliation_snapshot` counts the outcome phrases in `reconciliation.md`, or in a lite
    `spec.md`. The spec id comes from `spec.md`, or from the folder's `NNNN` prefix.
  - `reviewer_verdict` parses the spec id from either path shape (`NNNN-x.md` or `NNNN-x/...`).
  - `session_brief.py` lists pending folder specs by folder name.
  - `metrics.py start` reads `lite` and `tier` from `spec.md`.
- FR-14: **Worktree branch.** The short name is the folder name without its `NNNN-` prefix, so
  a lite spec keeps its `quick-` (`task/quick-feature-x`). `/worktree`, `/implement`'s worktree
  check and `/review`'s PR offer use `task/<short-name>` as today (framework ADR 0005).
- FR-15: **Legacy single-file specs keep working.** Every hook, script and command recognizes
  both shapes. A command acting on a legacy spec writes into that same file, in the legacy
  layout. It never converts or half-migrates a spec on its own.
- FR-16: **Migration script.** An optional, deterministic stdlib script splits a legacy spec
  into a folder:
  - frontmatter and requirement sections go to `spec.md`, which gains `tier` when the legacy
    `## Technical plan` records one;
  - the rest of `## Technical plan` goes to `plan.md`, with its subsections promoted one level;
  - `## Tasks` goes to `tasks.md` and `## Reconciliation` to `reconciliation.md`;
  - an unrecognized section stays in `spec.md` and is reported;
  - a legacy lite spec (`lite: true`) moves whole, unchanged, to `NNNN-quick-<short-name>/spec.md`.

  It is a dry run by default, and `--apply` writes. It refuses when the target folder exists,
  keeps line endings, and removes the original only after checking that every line of it is in
  the new files. It does not copy the Test plan lines into existing tasks (FR-07 applies to new
  `/tasks` runs only). `/setup-framework`'s upgrade path offers it per project, and never
  forces it.
- FR-17: **The framework's own specs.** `evolution/product/specs/` 0001 to 0006 are migrated
  with the FR-16 script as the last step of this spec's implementation. This is the script's
  first real run.
- FR-18: **Imported specs.** `migrate_context.py` always imports a spec as a folder. When the
  source document has a technical plan or a task list, it splits them into `plan.md` and
  `tasks.md`, as FR-16 does. Otherwise it writes `spec.md` and an empty `reconciliation.md`.
- FR-19: **Shipped material.**
  - `requirements-template.md` describes the folder, the role and frontmatter of each file, and
    the lite folder, and keeps the body template of `spec.md`.
  - The commands, agents and workflow docs that name "the spec's own section" name the file
    instead.
  - The permission rule and the mode A `if` filters in `settings.example.json` match files
    inside spec folders. The multi-project settings keep self-gating.

## Non-functional requirements

- NFR-01: **Backward compatibility.** Existing single-file specs, in this repository and in
  adopters' projects, work with no action: indexing, status flip, numbering, metrics, the
  session brief and every pipeline command. Migration is never forced.
- NFR-02: **Hook behaviour.** Hooks stay stdlib-only, file reads only, and fail open. Their
  self-gating accepts a file directly in `specs_dir` (legacy) or exactly one level down, in a
  `NNNN-*` folder. Anything deeper, or in any other folder, is ignored. Hooks that write files
  directly still never re-trigger themselves. In every mode (A, B, C) and in worktrees
  (framework ADR 0022), a file in a folder resolves exactly as a legacy file does today.
- NFR-03: **Context budget.**
  - Each file carries its own `context_budget`.
  - A non-lite `spec.md` does not grow after approval: only its `status` and `tier` lines
    change.
  - A per-task `coder`'s spec context is `spec.md` plus its full task text. On spec 0004
    migrated, that is at most 50% of the legacy file.
- NFR-04: **Language** (spec 0005). Free text in each file follows the setup language. File
  names, headings parsed by hooks, frontmatter keys and enumerated values stay English. The
  template's translation follows spec 0005 FR-05/FR-06.
- NFR-05: **Lossless migration.** The script never drops or rewrites a line of content. The only
  added lines are the companions' frontmatter, their top headings and the `tier` line. A failed
  check leaves the legacy file untouched.
- NFR-06: **Parallel writes are separated** (non-lite specs). During `/implement`, checkboxes are
  written to `tasks.md` and reconciliation lines to `reconciliation.md`. `spec.md` is written
  only by the status hook. A lite spec keeps today's single-file behaviour.

## Explicitly out of scope

- Changing what an artifact contains: FR/NFR/AC numbering, plan, Definition of Done and Test
  plan rules, the reconciliation line format. The task checkbox line keeps its format; FR-07
  only adds sub-lines under it.
- A per-folder index or `README.md`, generated or hand-written. The files' `summary` and the
  specs index already give the overview, and a summary file would duplicate them and drift.
- Splitting a lite spec into several files.
- An OpenSpec-style living per-capability spec, archive or delta model. That is the other half
  of what framework ADR 0008 rejected, and it stays rejected.
- Folders for ADRs or architecture docs.
- One file per task.
- Renaming a spec folder when its title changes.
- Migrating a project's specs without its owner's consent, or converting a legacy spec on first
  touch.

## Roles and permissions involved

- The developer runs the pipeline.
- The stakeholder validates `spec.md` alone.
- The project owner, or the framework maintainer for `evolution/`, decides whether and when to
  migrate legacy specs.

## Related specs

- 0003-proportional-pipeline-cost — modifies FR-01: the lite spec stays a single file, but
  inside its own `NNNN-quick-<short-name>/` folder instead of directly under `product/specs/`.

## Acceptance criteria

- [ ] AC-01: `/spec` creates `NNNN-short-name/` with `spec.md` (`status: draft`, requirement
  sections only) and `reconciliation.md` (empty `## Reconciliation`), and nothing else. The
  specs index lists it and links to its `spec.md`. (FR-01, FR-02, FR-12)
- [ ] AC-02: On a standard or structural spec, `/plan` writes `plan.md` and changes only the
  `status` and `tier` lines of `spec.md`. On a trivial spec, it writes `tier: trivial` and no
  `plan.md`. `/tasks` writes only `tasks.md`. (FR-02, FR-03, FR-04, NFR-03)
- [ ] AC-03: Every task `/tasks` writes carries the full text of its Test plan lines, as
  indented non-checkbox sub-lines. A task in a structural spec also carries its pointer to, or
  excerpt of, `plan.md`'s approach. The sub-lines do not change the box count. (FR-07, FR-10)
- [ ] AC-04: During an `/implement` sweep, each `coder`/`quickfix` prompt holds its full task
  text and the path of `spec.md`, and no other task and no reconciliation entry. `reviewer`
  writes reconciliation lines to `reconciliation.md` only. (FR-08, NFR-06)
- [ ] AC-05: Checking the last box in `tasks.md` flips `spec.md` from `approved` to
  `implemented`, logs `spec_implemented` and refreshes the index. A `draft` spec never flips.
  (FR-10)
- [ ] AC-06: The number guard denies a new spec that collides with an existing folder, lite
  folder or legacy file, in every direction. (FR-11)
- [ ] AC-07: In a project that mixes legacy files, folders and lite folders:
  - the index and the session brief list every shape;
  - the status flip works for every shape;
  - `spec_created`, `reconciliation_snapshot` and `reviewer_verdict` carry the right spec id;
  - `/metrics` reads the tier from `spec.md`.

  (FR-04, FR-12, FR-13, FR-15, NFR-01)
- [ ] AC-08: Running `/plan`, `/tasks` and `/implement` on a legacy spec keeps it a single file
  and creates no folder. (FR-15)
- [ ] AC-09: `/quick` produces `NNNN-quick-<short-name>/spec.md` as its only file, holding
  `lite: true`, `tier: standard`, the FRs, ACs, `## Tasks` and `## Reconciliation`. Checking its
  last box flips it to `implemented`, its reconciliation lines are counted, and `/implement`
  records lane `fast`. (FR-06, FR-10, FR-13)
- [ ] AC-10: The migration script on specs 0001 to 0006:
  - a dry run lists the parts;
  - `--apply` produces folders whose files together contain every line of the originals, with
    `tier` in `spec.md`;
  - it refuses an existing target folder;
  - the hooks and the index then treat the migrated specs as folders.

  A legacy lite fixture moves whole to an `NNNN-quick-*` folder. (FR-16, FR-17, NFR-05)
- [ ] AC-11: `migrate_context.py` imports a document with a plan and a task list as a folder with
  `spec.md`, `plan.md`, `tasks.md` and `reconciliation.md`, and one without them as `spec.md`
  and `reconciliation.md`. (FR-18)
- [ ] AC-12: `/implement` on folder `NNNN-foo` looks for branch `task/foo`, and on
  `NNNN-quick-bar` for `task/quick-bar`. `/worktree foo` matches that folder. (FR-14)
- [ ] AC-13: On spec 0004 migrated, a per-task `coder`'s spec context (`spec.md` plus its task
  text) is at most 50% of the legacy file's size (chars/4 heuristic). No file exceeds twice its
  own `context_budget`. (NFR-03)
- [ ] AC-14: On a Portuguese setup, the file names and the `## Tasks`/`## Reconciliation`
  headings stay English, and every hook behaves as on an English setup. (FR-09, NFR-04)
- [ ] AC-15: In mode A, the settings template's permission and `if` filters match a write inside
  a spec folder. In modes B/C, the self-gating hooks fire for it. A write two levels deep, or
  outside a `NNNN-*` folder, is ignored. (FR-19, NFR-02)
- [ ] AC-16: An extra file such as `research.md`, with `doc_type: spec-note` and a `summary`, is
  accepted by `frontmatter_check.py` and `context_budget_check.py`. Neither hook asks a
  companion file for `status`. (FR-03, FR-05)
- [ ] AC-17: Every existing test about legacy single-file specs passes unchanged. (NFR-01)

## Impact on existing architecture

- **Reverses framework ADR 0008's rejection** of a change-folder model. That ADR kept "one spec
  = one file, readable in isolation". Under this spec, `spec.md` alone is the spec readable in
  isolation. ADR 0008's area/lineage decision itself stands.
- **Amends**:
  - framework ADR 0004: plan and tasks are recorded in their own files, the tier in `spec.md`,
    and `/tasks` copies the Test plan lines into each task;
  - ADR 0009 and ADR 0012: reconciliation and sweeps go to `reconciliation.md`;
  - ADR 0020: the lite spec moves into a `NNNN-quick-*` folder;
  - ADR 0005: the branch name comes from the folder name;
  - ADR 0011: the metrics triggers.

  It also adds the file names to spec 0005's invariant markers (ADR 0023).
- **Hooks**: `_project_paths.py` (a shared "is this a spec file, which spec, lite or not"
  helper), `spec_status_sync.py`, `spec_index.py`, `spec_number_guard.py`, `pipeline_metrics.py`,
  `session_brief.py`, `frontmatter_check.py`, `context_budget_check.py`, and
  `validation_sync_check.py` (legacy shim, legacy files only).
- **Scripts**: `metrics.py`, `migrate_context.py`, `translation.py` (literal list), and the new
  migration script. `census.py` takes a spec id and is unaffected.
- **Prompts and docs**: `/spec`, `/plan`, `/tasks`, `/implement`, `/review`, `/reconcile`,
  `/quick`, `/worktree`, `/setup-framework`; `coder`, `quickfix`, `reviewer`, `architect`,
  `triage`; `requirements-template.md`, `CLAUDE.md.template`, the workflow docs, the README and
  both settings templates.

Expected to need a new framework ADR at `/plan`.

## Reconciliation

## Technical plan

**Tier:** structural. **ADR:** framework ADR 0024
(`evolution/decisions/0024-spec-folders.md`, `proposed`). It amends ADRs
0004, 0005, 0008, 0009, 0011, 0012, 0020 and 0023, and supersedes none.
`/tasks` and `/implement` wait until it is accepted. ADR 0024 settles the
mechanics; this plan only orders them.

This spec is still a legacy single file. It is migrated to a folder by its
own last task (FR-17).

### Approach, in dependency order

1. **Layout resolver.** New `.claude/hooks/_spec_layout.py` (stdlib).
   - `classify()` recognizes three layouts, and ignores anything deeper:
     - a legacy file one level down;
     - a folder file two levels down, with a role: spec, plan, tasks,
       reconciliation or note;
     - a lite folder, recognized by `lite: true`.
   - The spec id comes from the frontmatter, else from the `NNNN` prefix.
   - A CLI with `resolve <path|folder|NNNN>` and `next-number`.
   - `_project_paths.specs_dir()` is the only change to that module.
   - Every parser handles CRLF.
2. **Status and index.**
   - `spec_status_sync` reacts to edits of `tasks.md` and `spec.md` (or of
     the single file for lite and legacy specs). It writes only the
     `status:` line in `spec.md`'s frontmatter, keeping every other byte,
     line endings included.
   - `spec_index` exposes `rebuild()`, which the flip calls. `spec_index`
     stays silent when a flip is due.
   - The index has one row per spec, titled from `spec.md`.
3. **Number guard** across folders, lite folders, legacy files and
   half-migrated specs.
4. **The other hooks.**
   - `frontmatter_check`: companion files need `doc_type`, `spec`,
     `summary` and `context_budget`, never `status`. Extra notes are
     allowed. `tier:` is a known key.
   - `context_budget_check`: covers each file in the folder.
   - `pipeline_metrics`: the reconciliation target is `reconciliation.md`
     or the section in a single file. The `reviewer_verdict` spec-id
     regex accepts both path shapes.
   - `session_brief`: lists folders by name.
5. **Commands** (FR-01, FR-02, FR-04, FR-06, FR-07, FR-08, FR-14):
   - `/spec` creates the folder.
   - `/plan` writes `plan.md` and `tier:` (a trivial spec gets no
     `plan.md`; a lite spec stays a single file).
   - `/tasks` adds indented plain sub-bullets under each task: its Test
     plan lines, plus the approach excerpt for a structural task.
   - `/implement` hands each `coder`/`quickfix` its task text and the
     `spec.md` path, and gives `reviewer` the file list and the
     reconciliation target. It looks the spec up again by id before each
     checkbox write, and takes the branch name from the folder.
   - `/review`, `/reconcile` and `/worktree` resolve both layouts.
   - `/quick` writes `NNNN-quick-<short-name>/spec.md`.
6. **Agents.** `coder`, `quickfix`, `reviewer` and `architect` state what
   they load (FR-08).
7. **`migrate_spec_folders.py`** (ADR 0024 §8):
   - dry run by default;
   - splits on the fixed English headings, or on `--plan-heading`;
   - moves plan subsections up one heading level;
   - stages the result, verifies every line made it across, renames, and
     only then deletes the original;
   - refuses an existing target or a spec that exists in both layouts;
   - skips specs already migrated;
   - reports links that would break and never rewrites them;
   - rebuilds the index;
   - warns about specs in flight on a mode A branch.
8. **`migrate_context.py`** reuses the splitter, so imported specs land as
   folders (FR-18).
9. **Shipped material** (FR-09, FR-19):
   - `requirements-template.md` gains the file skeletons;
   - the settings templates get a `*/*` permission and `**` `if`
     filters;
   - the translation check gets the four file names as fixed English
     words;
   - `.claude/README.md`, the workflow docs and the CHANGELOG are
     updated.
10. **Migrate `evolution/` 0001–0006** with the script (FR-17), then
    rebuild the index and run the suite.

### Scope check

Each item below is flagged, not folded in silently:

- **AC-13's margin is thin.** On spec 0004, `spec.md` alone is already
  about 40% of the legacy file. The context measurement test (S16)
  reports the real figure, and a miss is raised, never hidden.
- **Accepted ADRs and the CHANGELOG will cite stale paths.** ADRs
  0015–0023 and the CHANGELOG cite spec file paths that will stop
  existing. They can't be edited; this is accepted.
- **Parallel reviewers write one `reconciliation.md`.** The Edit tool's
  stale-read refusal and a retry cover it (NFR-06). The coordinator may
  also batch the lines, as it did in specs 0004 and 0005.
- **The permission and filter globs need an empirical check.** The `**`
  filter and the `*/*` permission must be tried against the current
  Claude Code version (Definition of Done).

Constitution: no conflict. Everything is stdlib, with no new dependency,
and the migration is lossless and never destructive.

### Definition of Done

- [ ] `python -m unittest discover -s tests -t tests` passes, with the
  Test plan below. Every existing legacy test passes unchanged (AC-17).
- [ ] `reviewer` approved every coder-tier task.
- [ ] AC-03 and AC-05 through AC-17 are covered by tests.
- [ ] AC-01, AC-02, AC-04 and AC-09 (command behaviour) are checked by
  `reviewer` against the prose, and by one real `/spec` → `/plan` →
  `/tasks` run on a throwaway spec.
- [ ] The `*/*` permission and `**` filter are verified empirically in a
  session (AC-15).
- [ ] `evolution/` specs 0001–0006 are migrated, the index is rebuilt and
  the suite is green afterwards (FR-17, AC-10).
- [ ] Framework ADR 0024 is `accepted` before implementation starts.

### Test plan

- S01: `classify()` identifies a legacy file, folder files with their
  roles, a lite folder (`lite: true`), and the id from the frontmatter
  or the prefix; deeper paths are ignored — FR-01, FR-03, FR-06, FR-15
- S02: the CLI `resolve` (by path, folder or NNNN) and `next-number`
  work across mixed layouts — FR-11, FR-15
- S03: checking the last box in `tasks.md` flips only the `status:`
  line in `spec.md`, with CRLF bytes preserved — FR-10, AC-05
- S04: the flip on lite and legacy single files behaves exactly as
  today — FR-15, AC-08, AC-17
- S05: indented plain sub-bullets under a task never count as task
  boxes — FR-07, AC-03
- S06: the number guard denies a collision with a folder, a lite
  folder, a legacy file or a half-migrated spec — FR-11, AC-06
- S07: the index has one row per spec, titled from `spec.md`, across
  mixed layouts; `spec_index` stays silent when a flip is due — FR-12,
  AC-07
- S08: `frontmatter_check` asks companion files for `doc_type`, `spec`,
  `summary` and `context_budget` but not `status`; an extra
  `spec-note` with a `summary` is accepted; `tier:` is known — FR-03,
  FR-04, FR-05, AC-16
- S09: `pipeline_metrics` reads the reconciliation target in both
  layouts, and the verdict spec-id regex matches both path shapes; the
  session brief lists folders — FR-13
- S10: the branch name is the folder name without `NNNN-`, keeping
  `quick-` — FR-14, AC-12
- S11: the migration script defaults to a dry run; splits on the
  English headings and on `--plan-heading`; is lossless (every line
  accounted for); refuses an existing target or both layouts; skips
  migrated specs; reports breaking links; rebuilds the index — FR-16,
  NFR-05, AC-10
- S12: a translated legacy spec migrated without `--plan-heading` keeps
  its plan in `spec.md`, and this is reported — FR-16, NFR-04
- S13: `migrate_context.py` imports a document with a plan and tasks as
  a folder — FR-18, AC-11
- S14: on a Portuguese setup, the file names and `## Tasks` /
  `## Reconciliation` stay English, and the translation check enforces
  the file names — FR-09, NFR-04, AC-14
- S15: the settings template's permission and `if` patterns match a
  write inside a spec folder (pattern level) — FR-19, AC-15
- S16: on migrated spec 0004, a per-task `coder`'s spec context is
  measured against the legacy file and reported against the 50%
  target — NFR-03, AC-13

## Tasks

Layers are framework layers: **hooks/scripts** (Python, tested) and **commands/docs** (prose read
by agents). No task touches sensitive data or a new table. `_spec_layout.py` is written only by
task 1; every other task imports it read-only. Every task follows framework ADR 0024.

- [ ] 1. **Layout resolver** — hooks/scripts: new `.claude/hooks/_spec_layout.py` (`classify()` for legacy file / folder file with role / lite folder via `lite: true`, deeper paths ignored, id from frontmatter or `NNNN` prefix, CRLF-safe parsing; the branch short name from a folder or legacy name, keeping `quick-`; CLI `resolve <path|folder|NNNN>` and `next-number`); `_project_paths.specs_dir()`. New test file. — Depends on: none — Tests: S01, S02, S10
- [ ] 2. **Status flip and index** — hooks/scripts: `spec_status_sync.py` reacts to `tasks.md`/`spec.md` (or the single file for lite/legacy), writes only the `status:` line of `spec.md`'s frontmatter, byte-preserving; indented plain sub-bullets never count as boxes; `spec_index.py` gains `rebuild()` (called by the flip), one row per spec titled from `spec.md`, silent when a flip is due. — Depends on: 1 — Tests: S03, S04, S05, S07
- [ ] 3. **Number guard** — hooks/scripts: `spec_number_guard.py` denies a collision with a folder, lite folder, legacy file or half-migrated spec. — Depends on: 1 — Tests: S06
- [ ] 4. **Frontmatter and budget hooks** — hooks/scripts: `frontmatter_check.py` (companion files need `doc_type`, `spec`, `summary`, `context_budget`, never `status`; `spec-note` extras with `summary` accepted; `tier:` known) and `context_budget_check.py` (every file in a folder). — Depends on: 1 — Tests: S08
- [ ] 5. **Metrics and session brief** — hooks/scripts: `pipeline_metrics.py` reads the reconciliation target in both layouts and the verdict spec-id regex matches both path shapes; `session_brief.py` lists folders by name. — Depends on: 1 — Tests: S09
- [ ] 6. **Authoring commands** — commands/docs: `/spec` creates the folder (`spec.md` + empty `reconciliation.md`); `/plan` writes `plan.md` and `tier:` in `spec.md` (trivial: no `plan.md`; lite stays single-file); `/tasks` writes `tasks.md` with indented plain sub-bullets (its Test plan lines, plus the approach excerpt for structural tasks); `/quick` writes `NNNN-quick-<short-name>/spec.md` with `lite: true`; legacy specs keep their layout; `docs/product/requirements-template.md` gains the file skeletons. — Depends on: 1 — Tests: none (prose; checked by `reviewer`)
- [ ] 7. **Execution commands** — commands/docs: `/implement` (each `coder`/`quickfix` gets its task text + the `spec.md` path; `reviewer` gets the file list + the reconciliation target; look the spec up by id before each checkbox write; branch from the folder name), `/review`, `/reconcile`, `/worktree` resolve both layouts via `_spec_layout.py resolve`. — Depends on: 1 — Tests: none (prose; checked by `reviewer`)
- [ ] 8. **Agents** — commands/docs: `coder`, `quickfix`, `reviewer`, `architect` state what they load per FR-08 (task text + `spec.md`; `plan.md` only when the task text is insufficient; never `tasks.md` whole or `reconciliation.md` for coder/quickfix; reviewer writes only the reconciliation target). — Depends on: 6, 7 — Tests: none (prose; checked by `reviewer`)
- [ ] 9. **Migration script** — hooks/scripts: new `.claude/scripts/migrate_spec_folders.py` per ADR 0024 §8 (dry run default; split on English headings or `--plan-heading`; plan subsections up one level; staged, lossless line check, rename, then delete; refuses existing target / both layouts; skips migrated; reports breaking links; rebuilds the index; warns about mode A specs in flight). — Depends on: 1, 2 — Tests: S11, S12
- [ ] 10. **Imported specs as folders** — hooks/scripts: `migrate_context.py` reuses the splitter so imported specs land as folders. — Depends on: 9 — Tests: S13
- [ ] 11. **Shipped config and translation names** — hooks/scripts plus settings templates: `*/*` permission and `**` `if` filters in both settings templates; the translation check treats `spec.md`/`plan.md`/`tasks.md`/`reconciliation.md` as fixed English words. — Depends on: 1 — Tests: S14, S15
- [ ] 12. **Docs** — commands/docs: `.claude/README.md` (resolver, migration script, hook behaviour), the workflow docs that describe the spec file (feature-development-guide, parallel-work, ai-first-development as relevant), `CHANGELOG.md` entry citing framework spec 0006 / framework ADR 0024 with an upgrade note (both layouts supported; optional migration). — Depends on: 8, 10, 11 — Tests: none
- [ ] 13. **Migrate the framework's own specs** — hooks/scripts plus `evolution/`: run `migrate_spec_folders.py` on `evolution/product/specs/` 0001–0006 (dry run, review, apply), rebuild the index, run the suite; add the context-budget measurement test on migrated spec 0004. This spec's own last checkbox then lives in its new `tasks.md`. — Depends on: 2, 3, 4, 5, 9, 12 — Tests: S16
