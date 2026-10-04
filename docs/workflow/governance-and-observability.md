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
  task's review, `reviewer` returns a line per `FR-NN`/`AC-NN` the task
  declared under a `Reconciliation:` heading, and `/implement` appends
  them to the spec's own "## Reconciliation" section — matches spec, or
  diverged and why (framework ADR 0009, 0024 and 0025). Under
  `final-only`, `/review` writes its own.
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

Both end up in the same "## Reconciliation" section; read it top to
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
write around each feature. Since framework ADR 0025 it also gets
`subagent_started`/`subagent_stopped` (from the `SubagentStart` and
`SubagentStop` hooks, carrying `agent_id`), and `gate_run` carries the
`agent_id`, whether it `blocked` the agent (a failure exits 2 with a
bounded tail of the output, which Claude Code hands back where it resumes
the agent; it doesn't for one ending through `SubagentHandback`, so
`/implement` reads the result with `metrics.py gates` and returns the
failure itself),
and `concurrent`, the number of code-capable siblings that overlapped
it. `/implement` marks each parallel batch with `metrics.py wave-start`.
`/metrics` turns those into a per-feature
table — subagents, gate runs and failures (split into solo and
concurrent), reviewer verdicts, rework — with the fast lane and the full
path side by side, so `review_policy` gets chosen from data;
`metrics.py gates` lists the individual gate runs. For anything else,
read the log with `jq` (framework ADR 0011).

`reviewer_verdict` is read from the reviewer's own transcript when it
stops (`SubagentStop`), so it no longer depends on the name of the
dispatch tool, and a background reviewer is counted. The `Task`/`Agent`
PostToolUse entries only feed `subagent_dispatched`. A reviewer whose
verdict can't be read is flagged by `/metrics` as a missing verdict; to
inspect, `jq 'select(.event=="reviewer_verdict")' .claude/pipeline-metrics.jsonl`.

## How these four relate

The constitution is a standing check, always relevant. Area/lineage live in the spec's `spec.md` and
reconciliation in its `reconciliation.md` (a lite or legacy spec keeps both in
its one file), growing over that spec's life. Metrics are the only one that looks *across* specs —
everything else stays scoped to one spec at a time. None of the four
gate each other: a project can adopt any subset independently, and
none of them require `docs/constitution.md` to exist except the first
one, by definition.
