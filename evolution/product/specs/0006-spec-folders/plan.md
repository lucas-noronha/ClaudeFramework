---
doc_type: spec-plan
spec: 0006
summary: The technical plan: approach, scope check, Definition of Done and Test plan.
context_budget: ~2150 tokens
---

# Technical plan

**Tier:** structural. **ADR:** framework ADR 0024
(`evolution/decisions/0024-spec-folders.md`, `proposed`). It amends ADRs
0004, 0005, 0008, 0009, 0011, 0012, 0020 and 0023, and supersedes none.
`/tasks` and `/implement` wait until it is accepted. ADR 0024 settles the
mechanics; this plan only orders them.

This spec is still a legacy single file. It is migrated to a folder by its
own last task (FR-17).

## Approach, in dependency order

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

## Scope check

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

## Definition of Done

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

## Test plan

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

