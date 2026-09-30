---
doc_type: adr
id: 0016
status: proposed
date: 2026-09-28
supersedes: null
superseded_by: null
context_budget: ~1300 tokens
---

# ADR 0016 — Per-project disciplines (tests, structural ADRs, security review) as opt-out facts in `CLAUDE.md`

Like ADR 0001–0015, this documents a decision about *this framework's
own* tooling.

## Context

`coder.md`, `plugin-awareness/SKILL.md`, `plan.md` and `reviewer.md`
treat three disciplines as an unconditional floor for every project,
regardless of that project's own reality:

1. Test-first/TDD discipline, plus a mandatory Test plan in `/plan`'s
   output.
2. Automatic `architect` + ADR delegation for any structural-tier task.
3. An automatic `security-review` pass on sensitive diffs.

A project with no test culture (never had a unit test suite, no test
framework chosen yet), or a small team that doesn't want ADR formalism
for every cross-module change, has no way to opt out today.
`/setup-framework`'s Domain 1 only asks for `{{BUILD_TEST_CMD}}` and,
when neither `dotnet test` nor an npm `test` script is detected, falls
back to a bare "ask" with no explicit "this project intentionally has
no automated tests" option. `run_build_test.py` then fails loud (exit 1)
on an empty *or* missing command alike, so there's no clean way to
register that absence deliberately.

Surfaced from a user conversation asking "what if the project never had
a test suite", pushing back that the framework shouldn't assume
disciplines a project doesn't actually have.

## Options considered

1. **New keys in `project-config.json`.** Rejected: that file is
   consumed only by deterministic hooks (`run_build_test.py` via
   `_project_paths.py`) and **does not exist at all in mode A** (classic
   in-repo mode) — only modes B/C (external AI-repo / user-level) create
   it. Making it the home for these flags would mean inventing its
   creation in mode A just for this, breaking an invariant several
   existing docs state plainly.
2. **A dedicated new config file** (e.g. `disciplines.json`). Rejected:
   a fourth project-config surface when two already exist with clear
   owners (`CLAUDE.md` = facts agents read directly,
   `project-config.json` = values hooks read). Contradicts, in spirit,
   `CLAUDE.md.template`'s own convention #2 ("never duplicate
   information across files") by fragmenting where project facts live.
3. **A new "Project disciplines" item inside `CLAUDE.md.template`, as
   resolved Yes/No prose facts read directly by every agent (chosen).**
   `CLAUDE.md` is already read by `coder`, `quickfix`, `reviewer`, and
   `architect` in every adoption mode (A, B, C) — this reuses existing
   plumbing with zero new files and zero new per-mode special-casing.

## Decision

**`CLAUDE.md.template`**

- Add item 7, **Project disciplines**, to "## Conventions for any agent
  working in this repo" (after today's item 6), with three Yes/No facts
  resolved once at setup time:
  - `Tests required: {{TESTS_REQUIRED}}` — when No, `coder`/`quickfix`
    skip test-first discipline and `/plan` generates no Test plan
    section. When Yes (the default), today's behavior is unchanged.
  - `Structural changes require an ADR: {{STRUCTURAL_ADR_REQUIRED}}` —
    when No, `/plan` treats structural-tier classification like
    standard tier (no automatic `architect` delegation). A human can
    still invoke `/adr` or ask for one manually at any time.
  - `Automatic security review pass: {{SECURITY_REVIEW_REQUIRED}}` —
    when No, `coder`/`reviewer` stop auto-invoking the `security-review`
    skill on sensitive diffs (auth, secrets, input handling). This
    disables a **safety net**, not a style preference — the setup-time
    question wording itself must say so, never offer it as a neutral
    toggle.
- `docs/constitution.md` enforcement needs no new flag: the file's own
  presence/absence is already that discipline's toggle. This ADR closes
  that question explicitly rather than leaving it implicit.
- Item 3 ("Every new architecture decision becomes an ADR...") becomes
  conditional: "...unless the Project disciplines item above sets
  'Structural changes require an ADR' to No."

**`/setup-framework` Domain 1 step 2 (`{{BUILD_TEST_CMD}}`)**

- When a test command **is** detected automatically, set
  `tests_required = Yes` without asking — behavior for a project that
  already has tests is completely unchanged.
- When neither `dotnet test` nor an npm `test` script is detected,
  replace the bare "ask" fallback with a single `AskUserQuestion`
  offering four options:
  - (a) "I have a command, it just wasn't auto-detected" → ask for the
    literal command; `tests_required = Yes`.
  - (b) "No tests yet, but I want to set up a suite now" →
    `tests_required = Yes`; ask for the forward-looking command the
    suite will use once it exists. The close-out notes the gate may fail
    until that suite is actually created — the first task should set it
    up.
  - (c) "This project will have no automated tests" →
    `tests_required = No`, `build_test_cmd = ""` (the gate is
    deliberately disabled, not misconfigured).
  - (d) "Build/compile only, no automated tests" →
    `tests_required = No`; ask for a build-only command.
- Two more questions join the same batch, always asked (nothing to
  detect):
  - "Do structural changes always require an ADR before
    implementation?" (default Yes).
  - "Does a security-sensitive diff always get an automatic
    security-review pass?" (default Yes), with the safety-net framing
    above stated in the question itself.

**Modes B/C**

- `project-registration/SKILL.md` step 3's question batch (resolving
  each newly-registered project's own `CLAUDE.md.template`) and
  `/setup-framework` Domain 5 step 5 (external AI-repo mode's
  per-project `CLAUDE.md` resolution) both gain the same four
  questions. They already duplicate Domain 1's build/test detection for
  their own modes, and must duplicate this too so a project registered
  via B/C gets the same opt-out.

**Agent-side conditionals**

- `coder.md`:
  - "Apply `plugin-awareness`'s absorbed discipline (test-first,
    systematic debugging, verification-before-completion) regardless"
    becomes "...unless this project's `CLAUDE.md` marks tests as not
    required (see its 'Project disciplines' item)."
  - The same carve-out applies to the adjacent line invoking
    `superpowers`'s `test-driven-development` skill when enabled — the
    flag overrides even when the plugin is installed, since disabling
    the discipline is a project decision, not a plugin-availability
    question.
  - The `security-review` invocation line ("If this task touched auth,
    secrets/credentials, or input handling, also run the
    `security-review` skill...") gets the same conditional, tied to the
    `Automatic security review pass` flag.
- `plugin-awareness/SKILL.md`: the "Test-first discipline"
  absorbed-discipline bullet gets the identical carve-out (it's the
  non-plugin fallback text for the same rule `coder.md` states).
- `reviewer.md`: "also invoke the `security-review` skill regardless of
  tier" becomes conditional on the `Automatic security review pass`
  flag.
- `reviewer.md`'s Test-plan checklist item ("If there's no Test plan
  (trivial tier), fall back to: tests cover the new behavior...")
  currently assumes the *only* reason a diff has no Test plan is that
  it's trivial tier. With `Tests required: No`, a standard or
  structural task also has no Test plan, so that assumption no longer
  holds. Reword the fallback trigger to "If there's no Test plan
  (trivial tier, or tests not required for this project)" — the
  fallback check itself (tests cover new behavior, not just the happy
  path) stays the same either way.
- `triage.md` states unconditionally that "if structural, the
  `architect` subagent must be invoked before any code is written."
  That's now only true when `Structural changes require an ADR` is
  Yes. Reword so `triage` states the structural classification and
  notes that whether `architect` is actually invoked is `/plan`'s own
  call, per this project's Project disciplines setting — `triage`
  classifies complexity, it doesn't own this policy decision, so it
  shouldn't assert an invocation `/plan` might not make.
- `plan.md`:
  - Step 4 (structural tier): when `Structural changes require an ADR`
    is No, treat structural-tier classification like standard tier
    (step 3's short technical plan) instead of delegating to
    `architect`. A human can still invoke `/adr` manually any time,
    regardless of this setting.
  - Step 6 (Definition of Done + Test plan): when `Tests required` is
    No, skip the Test plan section entirely and drop "tests pass" from
    the Definition of Done checklist.
- `architect.md` and `quickfix.md` need no changes — both work exactly
  as today whenever they're actually invoked; only whether/when they get
  invoked changes.

**`run_build_test.py`**

- Today a missing `build_test_cmd` key and an empty-string value both
  fail loud (exit 1, "re-run /setup-framework"). Change so:
  - an **explicit empty string** (deliberately recorded by the new
    opt-out flow) exits 0 silently — a deliberate configuration, not a
    misconfiguration;
  - a **genuinely missing key** keeps failing exactly as loud as today
    (registration never completed, or the file was hand-edited wrong).
- This distinction only matters for modes B/C. Mode A's gate is literal
  command text baked into `settings.json` by Domain 1; when
  `tests_required = No` in mode A, Domain 1 simply never writes that
  hook entry into `settings.json` — no code change in mode A's path.

**Backward compatibility**

- A `CLAUDE.md` with no "Project disciplines" item at all — every
  project set up before this ADR — means every agent assumes all three
  flags are Yes, identical to today's unconditional behavior. No
  migration step and no `/setup-framework` re-run is required for
  existing projects.

## Rationale

Reuses `CLAUDE.md` as the one surface for project facts that is already
uniform, already read by every agent, and already resolved per adoption
mode, instead of inventing new plumbing. Keeps the change purely
additive and opt-out, so every existing project's behavior is unchanged
unless a human explicitly answers the new questions. Treats the
security-review opt-out differently from the other two by requiring the
setup-time question to name the real risk being accepted rather than
offering a neutral style toggle: unlike TDD-style discipline or ADR
formalism, that one is a safety net, and framing all three identically
would understate it.

## Consequences

- Purely additive: default answers (Yes/Yes/Yes) preserve every current
  behavior exactly; a project must explicitly opt out to change
  anything.
- Files touched by the eventual implementation: `CLAUDE.md.template`,
  `.claude/commands/setup-framework.md` (Domain 1, plus Domain 5 step
  5), `.claude/skills/project-registration/SKILL.md`,
  `.claude/agents/coder.md`, `.claude/skills/plugin-awareness/SKILL.md`,
  `.claude/agents/reviewer.md`, `.claude/agents/triage.md`,
  `.claude/commands/plan.md`, `.claude/hooks/run_build_test.py` —
  roughly nine files, no new files created.
- The `Automatic security review pass` opt-out is a real risk acceptance
  a project takes on, not mere workflow flexibility — the setup-time
  question wording must say so plainly. This ADR states the
  requirement; the actual question copy is an implementation detail of
  `/setup-framework` / `project-registration`.
- `run_build_test.py` now distinguishes "empty" from "missing" — a
  hand-edited `build_test_cmd: ""` silently disables the only hard
  quality gate in modes B/C. That's the accepted cost of letting the
  opt-out be recorded deliberately.
- Setup asks three more questions (one of them only when no test command
  is detected), in every mode.
- `docs/constitution.md` enforcement is unaffected — it was already
  conditional on the file's own presence, and stays that way.

## References

`docs/decisions/0016-project-disciplines-configuration.md`,
`CLAUDE.md.template`, `.claude/commands/setup-framework.md`,
`.claude/skills/project-registration/SKILL.md`,
`.claude/agents/coder.md`, `.claude/skills/plugin-awareness/SKILL.md`,
`.claude/agents/reviewer.md`, `.claude/agents/triage.md`,
`.claude/commands/plan.md`, `.claude/hooks/run_build_test.py`,
`docs/decisions/0010-constitution-technical-enforcement.md`,
`docs/decisions/0014-setup-framework-adoption-modes.md`
