---
doc_type: adr
id: 0024
status: accepted
date: 2026-10-04
supersedes: null
superseded_by: null
context_budget: ~4200 tokens
---

# ADR 0024 — A spec is a folder of single-owner files, addressed through one shared layout resolver

Like ADR 0001–0023, this documents a decision about *this framework's
own* tooling. It **reverses ADR 0008's rejection** of a change-folder
layout, and it **amends**:

- ADR 0004: the plan and the tasks get their own files, the tier moves to
  `spec.md`'s frontmatter, and `/tasks` copies each task's Test plan lines.
- ADR 0005: the branch's short name comes from the folder name.
- ADR 0009 and 0012: reconciliation lines and sweeps go to
  `reconciliation.md`.
- ADR 0011: the metrics triggers.
- ADR 0020: the lite spec moves into an `NNNN-quick-*` folder.
- ADR 0023: four file names join the invariant English markers.

It supersedes none of them. ADR 0008 in particular is **amended, not
superseded**: its decision (`area`/`relates_to` inferred, never
hand-declared) stands unchanged. What comes back is half of an option it
rejected, the folder, and the other half (a living per-capability spec
with an archive) stays rejected. Marking 0008 `superseded` would retire a
live decision.

## Context

Spec 0006 is approved, and its FR/NFR/AC are fixed: one folder per spec,
one owner per file, `status` and `tier` only in `spec.md`, lite specs as
single-file folders, legacy files working untouched, an optional lossless
migration, and this repository's specs 0001–0006 migrated last.

Facts of the current code shape the answer:

- **One gate, copied.** `spec_status_sync`, `spec_index`,
  `spec_number_guard`, `pipeline_metrics` and `validation_sync_check` each
  rebuild `specs_dir` and accept a path only when its directory *equals*
  it. `session_brief` globs `specs_dir/*.md`. A file one level down is
  invisible to all of them, and each parses frontmatter with its own
  regex.
- **Two hooks on one Edit.** `spec_index` and `spec_status_sync` are
  separate handlers on the same event, and they run concurrently. Today
  the index still shows `approved` after a flip, until the next write.
  FR-10 asks the flip's run to refresh the index. Two processes writing
  it for one edit would add a stale-overwrite race.
- **The flip writes in text mode**, which rewrites every line ending
  wherever `os.linesep` differs from the file's.
- **`reviewer_verdict`'s regex** `(\d{4})-[\w-]+\.md` misses
  `NNNN-x/spec.md`.
- **Only `## Tasks` and `## Reconciliation` are invariant** (ADR 0023).
  In a translated project, `## Technical plan` and the `**Tier:**` label
  are free text. In every legacy spec here the order is: requirements,
  then `## Reconciliation` (written empty by `/spec`), then
  `## Technical plan`, then `## Tasks`.
- **Accepted ADRs cite spec file paths** (0015–0023, under References),
  and they can't be edited.
- **Mode A specs are versioned with the code.** A spec branch in flight
  carries its own copy of the legacy file.
- The installer copies every `hooks/*.py`, so a new helper module reaches
  mode C with no installer change. `if: Write(.claude/skills/**)` is
  already a working `**` filter.

## Options considered

- **Teach each hook the folder shape on its own.** Rejected. Ten call
  sites and four prompts would each re-derive "which spec, which file,
  lite or not". These copies have drifted before (the `docs/` prefix bug
  documented in `_project_paths.py`).
- **Put the resolver in `_project_paths.py`.** Weighed and rejected. That
  module answers *which project*, in about 800 lines of routing. Spec
  layout is a separate question, and the two migration scripts ask it
  about a `--specs-dir` or `--dest` that is no session's project. The
  routing module gains only `specs_dir()`.
- **A per-folder manifest naming each file's role.** Rejected. Spec 0006
  excludes a per-folder index, and the file names already are the roles.
- **Merge `spec_status_sync` into `spec_index`** to remove the race.
  Rejected. It changes the wiring in both settings templates and in mode
  C's recorded merge groups, and adopters keep the old wiring until they
  upgrade.
- **Migrate by moving sections and fixing links and headings freely.**
  Rejected by NFR-05.
- **Ship plan and tasks templates as new files.** Rejected. That is two
  more translated files to track, and `/plan` and `/tasks` already own
  that content (spec 0006 `notFor`).
- **Chosen:**
  - a path-only layout module, shared by hooks and scripts and exposed
    to prompts through a CLI;
  - one index writer per flip;
  - a staged, verified migration that anchors only on invariant markers.

## Decision

1. **One resolver, `.claude/hooks/_spec_layout.py`.** It is stdlib-only,
   reads files and nothing else, and fails open. Like
   `_pipeline_metrics.py`, it is imported and never wired.
   - **`_project_paths.specs_dir(project)`** replaces every copy of
     `join(resolve_docs_root(p), "product", "specs")`.
   - **`classify(specs_dir, path)`** returns a spec reference or None.
     It uses today's comparison, `normalize`d directory equality:
     - **legacy**: the parent is `specs_dir`, and the name is `NNNN-*.md`,
       not `README.md` or `.validation-*`;
     - **folder**: the grandparent is `specs_dir`, the parent is `NNNN-*`
       and the name is `*.md`. The role comes from the name (`spec`,
       `plan`, `tasks`, `reconciliation`), and any other name is `note`;
     - deeper paths, other folders and dot-names return None.
   - **Reference fields**:
     - `id`: the spec file's frontmatter `id`, else the `NNNN` prefix;
     - `shape`, `role`, `spec_file`;
     - `short_name`: the folder or file name without `NNNN-` and `.md`;
     - `lite`: `lite: true` in the spec file's frontmatter, never the
       `quick-` in the name;
     - the **sources**. A non-lite folder uses `tasks.md`,
       `reconciliation.md` and `plan.md`. Lite and legacy specs use
       sections of the spec file itself.
   - **Shared readers**: `iter_specs()` (one reference per spec, both
     shapes), `numbers_in_use()`, one frontmatter reader and one
     `## <heading>` section reader. They parse CRLF and LF alike.
   - **CLI for prompts**, like `_project_paths.py describe`:
     - `resolve <path | folder | NNNN>` prints the reference as JSON,
       with `tier` and `branch`;
     - `next-number` prints the next free `NNNN` across every shape.

     `/spec`, `/quick`, `/plan`, `/tasks`, `/implement`, `/review`,
     `/reconcile` and `/worktree` call it instead of parsing a path.
   - **A folder without `spec.md`** resolves with no spec file. Hooks
     that need one do nothing, and the index lists it as `unknown`,
     never hides it.
   - **Wiring (FR-19).**
     - Mode A permissions: `Edit(docs/product/specs/*)` plus
       `Edit(docs/product/specs/*/*)`, which is exactly one level down.
     - Mode A `if` filters: `Write|Edit(docs/product/specs/**)`. One
       `if` holds one rule, and `*` doesn't cross `/`. The resolver
       enforces the depth.
     - The multi-project template gains the `*/*` permission. Its hooks
       keep self-gating.
2. **Status across files (`spec_status_sync.py`).**
   - **Trigger**: a reference whose role is `tasks` or `spec` in a
     folder, or a legacy file. In mode A it is wired on Write as well as
     Edit, as modes B/C already are.
   - **Rule**: read `status` from the spec file and the boxes from the
     `## Tasks` section of the tasks source, with today's box regex. Flip
     only from `approved`, with at least one box and every box checked.
   - **Write rule.** This is the only cross-file write a hook makes:
     - it replaces the `status:` line *inside the frontmatter block* of
       the spec file and nothing else;
     - bytes, encoding and line endings stay as they were (binary-safe
       read and write);
     - it writes directly, so it never re-triggers;
     - it never writes plan, tasks or reconciliation files.
   - **Same run**: log `spec_implemented` (id and area from the spec
     file), then rebuild the index in process with
     `spec_index.rebuild(project)`.
   - **One index writer per flip.** `spec_index.py` evaluates the same
     `flip_due(ref)`, and when it is true it writes nothing and leaves
     the rebuild to the flipping process. So there is no stale overwrite
     and no duplicate event.
3. **Numbering and index.**
   - **`spec_number_guard.py`.** Any file classified under `NNNN` counts
     as that spec. It denies when another entry already holds the
     number:
     - a folder with another name;
     - a legacy file, including one with the same short name (a
       half-migrated spec).

     Writing into an existing folder that alone holds its number is never
     a new spec. Script writes don't go through the tool, so the
     migration checks numbers itself.
   - **`spec_index.py`.** One row per `iter_specs` entry, both shapes in
     one table, with today's columns and sort.
     - A folder's title comes from `spec.md`'s `#` heading, falling back
       to the folder name, and its row links to `NNNN-x/spec.md`.
     - Legacy rows are unchanged.
     - Any write inside a folder refreshes the index, except when
       `flip_due` holds.
   - **`session_brief.py`** lists pending specs by folder name or by file
     name.
4. **Reconciliation.**
   - **Target.** A non-lite folder uses `reconciliation.md`. Lite and
     legacy specs use the `## Reconciliation` section of the spec file.
   - **`reviewer`.** `/implement` resolves the target and hands
     `reviewer` that path along with `spec.md`'s. `reviewer` appends only
     there, under ADR 0009's rules. Without a path, it runs `resolve`. It
     never guesses.
   - **`/reconcile`** reads `spec.md` and `reconciliation.md`, and appends
     its sweeps to `reconciliation.md`. ADR 0012's rules are unchanged.
   - **`/review`** reads `spec.md`, the Definition of Done in `plan.md`,
     `reconciliation.md` and `tasks.md`.
   - **`pipeline_metrics.py`.**
     - `reconciliation_snapshot`: on any write to the reconciliation
       source, it counts the same three phrases in its
       `## Reconciliation` section, under the reference's id.
     - `spec_created`: on a Write of a folder's `spec.md` with
       `status: draft`, or of a legacy file as today.
     - `reviewer_verdict`: the id regex accepts `NNNN-x.md` and
       `NNNN-x/`.
5. **Tier and frontmatter.**
   - **`tier`.** `/plan` writes `tier: trivial | standard | structural`
     to the spec file's frontmatter, in the same edit as
     `status: approved`.
     - This applies to every tier and to both shapes. A frontmatter key
       keeps a legacy spec single-file.
     - A trivial spec gets no `plan.md`.
     - Readers take frontmatter `tier` first. Only a legacy spec without
       one falls back to its plan's recorded tier.
   - **A lite spec stays single-file in every respect.** When `/plan`
     runs on it on request (ADR 0020), the plan goes into its `spec.md`,
     as in a legacy spec, never into a `plan.md`.
   - **Companion frontmatter.** `frontmatter_check.py` asks every file in
     a folder other than `spec.md` for `doc_type`, `spec`, `summary`
     (with its aliases) and `context_budget`, and never for `status`.
     Spec files and non-spec docs keep today's three keys.
     `context_budget_check.py` needs no change.
6. **Per-task context.**
   - **What `/tasks` copies.** Under each checkbox line it writes
     indented plain bullets:
     - the full text of each Test plan line that the task's `Tests:`
       field names, with any checkbox marker stripped;
     - for a structural spec, one pointer to the approach in `plan.md`
       (heading or step) or a short excerpt of it.

     A sub-line never starts with `[`. The checkbox line and its fields
     are unchanged, so the box count and ADR 0023's checkbox check both
     hold.
   - **A task's text** is its checkbox line plus the lines below it that
     are indented deeper. `/implement` extracts that text from
     `tasks.md` and hands it out:
     - to `coder` or `quickfix`: the text and `spec.md`'s path;
     - to `reviewer`: the text, the file list, `spec.md`'s path and the
       reconciliation path.

     A per-task agent never opens `tasks.md` or `reconciliation.md`. It
     opens `plan.md` only when the text isn't enough, and says so in its
     report.
   - **Re-resolve before each checkbox write.** `/implement` resolves the
     spec again by id before it checks a box. A spec migrated mid-sweep
     (FR-17 is spec 0006's own last task) then gets its box in
     `tasks.md`.
7. **Worktree branch.** `short_name` comes from the resolver: the folder
   name without `NNNN-` (a lite spec keeps its `quick-`), or the legacy
   name as today.
   - `/worktree <short-name>` matches `NNNN-<short-name>/` or
     `NNNN-<short-name>.md`.
   - `/implement` and `/review` take `task/<short_name>` from `resolve`.
   - ADR 0005 is otherwise unchanged.
8. **Migration: `.claude/scripts/migrate_spec_folders.py`.**
   - **Interface.**
     `[--specs-dir DIR] [--spec NNNN ...] [--plan-heading TEXT ...] [--tier-label TEXT] [--apply]`.
     Without `--specs-dir`, it uses the session's project. It is a dry
     run by default, prints a JSON report, and exits 1 if any spec was
     refused.
   - **Split.** It anchors only on invariant or explicitly given
     headings:
     - `spec.md`: the frontmatter, plus everything before the first
       `## Reconciliation`, plan or `## Tasks` heading;
     - `reconciliation.md`: the `## Reconciliation` section;
     - `tasks.md`: the `## Tasks` section;
     - `plan.md`: the section whose heading equals a `--plan-heading`.
       The default is `Technical plan`, and `/setup-framework` passes the
       setup's translated heading. That heading becomes the H1, and its
       subsections are promoted one level;
     - any other section stays in `spec.md` and is reported;
     - `tier`: read from the plan's `**Tier:**` line (or
       `--tier-label`). It is added to `spec.md` only when absent, and
       reported as missing otherwise.
   - **Lite legacy spec** (`lite: true`): moved byte-identical to
     `NNNN-quick-<short>/spec.md`, never with a doubled `quick-`.
   - **Idempotent.** A spec that is already a folder is skipped. One
     whose target exists, or that exists in both shapes, is refused.
   - **Never destroys.**
     1. Write into `.NNNN-x.migrating/`. The resolver ignores dot-names.
     2. Verify that every original line appears, in order, in exactly
        one output file. Lines keep their exact bytes, and the EOL,
        encoding and BOM stay the original's. Only these differences
        are allowed: the added frontmatter, H1s and tier line, and the
        heading level of plan subsections. FR-16's promotion is the one
        rewrite that NFR-05 permits.
     3. Rename the staging folder to the target.
     4. Delete the original.

     Any failure removes the staging folder and leaves the original
     untouched.
   - **Links.** It never rewrites links inside or into a spec. It
     reports relative links that would stop resolving one level deeper,
     and references to the old path that it finds under the docs root.
   - **Index and metrics.** It rebuilds the index itself at the end,
     because hooks don't see script writes. It logs no metrics.
   - **Dry-run warnings.** It warns about any `status: approved` spec
     (in flight), and in mode A about an existing `task/<short>` branch.
   - **Upgrade.** `/setup-framework`'s upgrade path shows the dry run per
     project and offers `--apply`. It never forces it.
   - **FR-17.** The migration is spec 0006's last task:
     `--specs-dir evolution/product/specs`.
   - **`migrate_context.py`** imports the splitter from this script (the
     two scripts sit side by side).
     - Numbered specs become `NNNN-slug/spec.md` and
       `reconciliation.md`, plus `plan.md` and `tasks.md` when the
       source has those headings (`--plan-heading`, `## Tasks`). It
       never splits on a content heuristic.
     - Links are re-pointed to `spec.md`, one level down.
     - `--spec-status` applies to `spec.md` only.
     - The verification accepts companions without `status`.
9. **Language (ADR 0023).**
   - **Project artifacts.** `plan.md`, `tasks.md`, `reconciliation.md`
     and spec notes are written by prompts that already carry the
     language line, so their free text is in the setup language. These
     stay English: the file names, `## Tasks` and `## Reconciliation`,
     `doc_type` values and the `spec` key. The `spec` key isn't on the
     free-text allow-list, so `check` keeps it.
   - **`translation.py check`.** The four file names join `LITERALS`,
     matched as whole names, so a bare mention in a prompt can't be
     translated.
   - **No new template file.** `requirements-template.md` keeps its
     name, because the index, translation records and `CLAUDE.md` rows
     point at it. It gains the folder layout, the companion frontmatter
     and their skeletons in a `markdown` fenced block, which is
     translated and checked recursively. Adopters receive it as a
     changed source, re-translated by hash.
10. **ADR 0022.** No new state.
    - **Modes B/C.** Spec folders are project content. Every worktree
      resolves to the same subtree folder, as a legacy file does today,
      and nothing goes into `.worktree-state/`.
    - **Mode A.** Specs are versioned per branch, so a migration on the
      integration branch, while a spec branch edits the legacy file,
      becomes a modify/delete conflict on merge. That is why item 8 warns
      about specs in flight.
    - Cross-branch numbering stays out of scope, as in ADR 0022.

## Rationale

One resolver makes "what is this file" a single deterministic answer
that hooks, scripts and prompts share, the way `_project_paths` did for
"which project". The flip stays the only hook that writes across files,
and it writes a single frontmatter line, so it can't damage content.

Splitting on invariant markers and caller-given headings keeps the
migration exact in every setup language. When the script can't classify
a section, it leaves it in `spec.md` and reports it, so a spec is never
split wrongly.

Staging, a line-by-line check, then a rename turns "never destroys" into
something verified on every run.

## Consequences

- **Dangling paths.** Accepted ADRs 0015–0023 and `CHANGELOG.md` cite
  spec file paths, and those paths stop existing after FR-17. The index
  maps each id to its folder, and "framework spec NNNN" stays the stable
  reference. New prose cites specs by id. ADR 0008 carries no backlink to
  this amendment, the same as ADR 0023's amendments.
- **Translated legacy specs need `--plan-heading`.** Without it, the plan
  stays in `spec.md` and is reported. The migration is still lossless,
  but the spec isn't split.
- **Two sources for a legacy tier** until migration: frontmatter first,
  then the plan.
- **Lite specs keep their full single-file cost**, which spec 0006
  accepts. A migrated legacy lite spec changes branch, from `task/x` to
  `task/quick-x`.
- **Reconciliation contention.** Parallel `reviewer`s still contend on
  one `reconciliation.md`, and the Edit tool's stale-read refusal plus a
  retry handles it. They no longer contend with checkbox edits.
  `reconciliation.md` grows without bound, but per-task agents no longer
  read it, and `context_budget_check` nudges.
- **Mode A's `**` filters** start a Python process for deeper writes too,
  which then self-gate. Permission rules apply only from session start.
- **Locked files.** OneDrive or an antivirus may lock the staging rename.
  The script fails before deleting anything, and a rerun first needs the
  staging folder removed (reported).
- **AC-13's margin is thin.** On spec 0004, `spec.md` alone is about 40%
  of the legacy file, so the copied task text has about 10% left.
- **Cost of the new components.** `_spec_layout.py` and its CLI,
  `migrate_spec_folders.py`, and one re-translation of
  `requirements-template.md` per adopter.

## References

`evolution/product/specs/0006-spec-folders.md` (after FR-17,
`0006-spec-folders/spec.md`),
`evolution/decisions/0004-plan-tasks-implement-rebalance.md`,
`evolution/decisions/0005-spec-worktree-lifecycle.md`,
`evolution/decisions/0008-spec-area-lineage.md`,
`evolution/decisions/0009-per-task-spec-reconciliation.md`,
`evolution/decisions/0011-pipeline-metrics.md`,
`evolution/decisions/0012-on-demand-reconciliation-sweep.md`,
`evolution/decisions/0020-proportional-pipeline-cost.md`,
`evolution/decisions/0022-worktree-sessions.md`,
`evolution/decisions/0023-setup-language.md`,
`.claude/hooks/_project_paths.py`, `.claude/hooks/spec_status_sync.py`,
`.claude/hooks/spec_index.py`, `.claude/hooks/spec_number_guard.py`,
`.claude/hooks/pipeline_metrics.py`, `.claude/hooks/session_brief.py`,
`.claude/hooks/frontmatter_check.py`, `.claude/scripts/migrate_context.py`,
`.claude/scripts/translation.py`, `.claude/settings.example.json`,
`.claude/settings.multi-project.json.example`,
`docs/product/requirements-template.md`
