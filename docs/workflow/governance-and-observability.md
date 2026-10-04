---
doc_type: workflow
scope: governance-and-observability
status: active
last_updated: {{DATE}}
related: [../constitution.md, ../product/requirements-template.md]
context_budget: ~950 tokens
---

# Governance and observability

Four additions that sit alongside the core spec → plan → tasks →
implement → review pipeline rather than inside it, added together as
one connected layer. This doc is the "how do these fit together and
what do I actually do" summary — full rationale for each lives in its
own ADR, linked below, not repeated here.

## 1. The constitution — supreme, versioned principles

Non-negotiable principles that `/spec`, `/plan`, `coder`/`quickfix`, and
`reviewer` all check against — see framework ADR 0007.
Since framework ADR 0018 they come in
layers by owner: `../constitution-baseline.md` (the framework's I–V:
secrets, logging, input validation, least privilege, dependency
vetting — replaced on every framework upgrade, never edited in a
project), `../constitution.md` (the organization's or project's own,
from VI, amended under its Governance section), and in modes B/C an
optional project layer.
It's the one exception to this framework shipping no default content:
security hygiene is close to universal, unlike architecture.

It's **checked** by every agent's own judgment, and separately **given
technical teeth** (framework ADR 0010)
so a violation doesn't only depend on an agent remembering to look:

- `secret_leak_guard.py` blocks a write matching a high-confidence
  credential pattern, repo-wide, active by default — works whether or
  not `docs/constitution.md` exists.
- `dependency_audit.py.example` runs your ecosystem's vulnerability
  audit when a dependency manifest changes (needs the real command
  filled in, like `auto_format.py.example`).
- `reviewer`/`coder` invoke the `security-review` skill for a
  security-sensitive diff, mapping a finding to a named Core Principle
  when the file exists.

**Amending it**: edit the file directly, bump `version`/`last_amended`
in the same change (semver — MAJOR removes/redefines a principle,
MINOR adds one, PATCH is wording only). `constitution_amendment_check.py`
nudges, never blocks, if you forget the version bump.

## 2. Spec area and lineage — automatic, never hand-tagged

Every spec now carries `area` and `relates_to` in its own frontmatter,
set by `/spec` itself by reading `docs/product/specs/README.md` before
drafting — never something you declare by hand
(framework ADR 0008). `spec_index.py`'s table is
sorted/grouped by area, so opening it shows you a new spec's siblings
at a glance. If two areas end up meaning the same thing (a naming
drift over time — `/spec` makes a per-run judgment call, not a
controlled vocabulary), fix it by hand: edit both specs' `area`
frontmatter to match.

## 3. Reconciliation — continuous during implementation, on-demand after

Two mechanisms, not one, covering two different moments:

- **Per-task, automatic, inside `/implement`**: after each coder-tier
  task's review, `reviewer` appends a line per `FR-NN`/`AC-NN` the task
  declared to the spec's own "## Reconciliation" section — matches
  spec, or diverged and why (framework ADR 0009).
  `/review`'s final pass checks every requirement has at least one
  entry before approving.
- **On-demand, any time, via `/reconcile <spec path>`**: for a spec
  that's been `implemented` for a while and you want to know if later
  work quietly broke something it used to satisfy
  (framework ADR 0012). Delegates to
  `reviewer`'s **sweep scope** — no diff, no file list, checks current
  code state against the spec's requirements, appends a dated
  `### Sweep — {{DATE}}` block. Run it periodically on a
  long-lived spec, or whenever you suspect drift, through whatever
  scheduling this project already has — nothing here runs it for you.

Both write to the same "## Reconciliation" section; read it top to
bottom for a spec's full fidelity history, per-task entries first, then
any sweeps.

## 4. Pipeline metrics — a raw event log, not a dashboard

`.claude/pipeline-metrics.jsonl` (git-ignored, per-machine) accumulates
four event types as the pipeline runs: `spec_created`,
`spec_implemented` (together give you `draft`→`implemented` elapsed
time per spec), `reconciliation_snapshot` (current matches/diverged/
out-of-scope counts), and `reviewer_verdict` (Approved/Returned).
Since framework ADR 0020 it also gets
`subagent_dispatched`, `gate_run` (with exit code), and the
`feature_started`/`feature_finished` markers `/implement` and `/quick`
write around each feature. `/metrics` turns those into a per-feature
table — subagents, gate runs and failures, reviewer verdicts, rework —
with the fast lane and the full path side by side, so `review_policy`
gets chosen from data. For anything else, read the log with `jq`
(framework ADR 0011).

`reviewer_verdict` has a real, documented gap: it depends on your
Claude Code version's subagent-dispatch tool being named `Task` or
`Agent` (both matched). If you never see one after a few `/review`
runs, check `jq 'select(.event=="reviewer_verdict")' .claude/pipeline-metrics.jsonl`
and adjust the hook's matcher in `settings.json` if your version uses a
different name.

## How these four relate

The constitution is a standing check, always relevant. Area/lineage and
reconciliation both live on the spec file itself, growing over that
spec's life. Metrics are the only one that looks *across* specs —
everything else stays scoped to one spec at a time. None of the four
gate each other: a project can adopt any subset independently, and
none of them require `docs/constitution.md` to exist except the first
one, by definition.
