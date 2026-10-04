"""Per-feature pipeline cost, from the raw event log (framework ADR 0011, extended
by framework ADR 0020, framework spec 0003 FR-05).

    metrics.py start --feature ID --lane full|fast [--tier T]
    metrics.py finish --feature ID
    metrics.py report [--json]
    metrics.py wave-start --feature ID
    metrics.py gates

`/implement` and `/quick` call `start`/`finish` around a feature, which
appends `feature_started`/`feature_finished` to the same
`pipeline-metrics.jsonl` the hooks write. No new state file. `report`
attributes every event between a feature's start and finish to it:

- subagents: `subagent_dispatched` (pipeline_metrics.py)
- gate runs and gate failures: `gate_run` (run_build_test.py)
- reviewer verdicts: `reviewer_verdict` (pipeline_metrics.py)
- rework: solo gate failures plus reviewer `Returned` verdicts. A failure is
  concurrent when `gate_run.concurrent` > 0 (other subagents were editing),
  solo otherwise (framework ADR 0025 item 7)
- missing verdicts: reviewer dispatches beyond the verdicts logged, flagged
  per feature; verdicts are deduplicated per `agent_id` (last one wins)

`wave-start` logs `wave_started`; `gates` prints, as a JSON list, the latest
`gate_run` per `agent_id` in this checkout since the last `wave_started`
(`/implement` orchestration steps 3 and 6); `pending` lists the `coder`/`quickfix`
subagents since then whose stop has no `gate_run` yet (gate still running,
or lost), with how long each has waited.

It then shows each feature, and the two lanes side by side, so a project
chooses its `review_policy` and its lane from data (AC-05). Features
overlapping in time (parallel sessions on one project) can't be told
apart from one log; events are attributed to the most recently started
open feature, and the report says when that happened. Features open in
different checkouts (linked worktrees, framework ADR 0022 section 3) are
told apart by the events' `checkout` stamp; an event without one is the
main checkout's.
"""
import argparse
import json
import os
import sys
import time

FRAMEWORK_HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(FRAMEWORK_HOME, "hooks"))
from _pipeline_metrics import LOG_FILENAME, log_event  # noqa: E402
from _project_paths import linked_worktree, state_file_path  # noqa: E402
from _subagents import role_of  # noqa: E402

LANES = ("full", "fast")


def read_events(project: str):
    events = []
    try:
        with open(state_file_path(project, LOG_FILENAME, "project"), encoding="utf-8") as f:
            for line in f:
                try:
                    events.append(json.loads(line))
                except ValueError:
                    continue
    except FileNotFoundError:
        pass
    return sorted(events, key=lambda e: e.get("ts", 0))


def summarize(events):
    features, stacks, overlapped = {}, {}, set()
    for event in events:
        kind = event.get("event")
        checkout = event.get("checkout") or "main"
        open_stack = stacks.setdefault(checkout, [])
        if kind == "feature_started":
            fid = event.get("feature")
            key = (checkout, fid)
            if open_stack:
                overlapped.add(key)
                overlapped.add((checkout, open_stack[-1]))
            features[key] = {"feature": fid, "checkout": checkout, "lane": event.get("lane"), "tier": event.get("tier"),
                             "subagents": 0, "gate_runs": 0, "gate_failures": 0,
                             "gate_failures_solo": 0, "gate_failures_concurrent": 0,
                             "reviewer_dispatches": 0, "_verdicts": {}, "_anon_verdicts": [],
                             "approved": 0, "returned": 0, "finished": False}
            open_stack.append(fid)
            continue
        if kind == "feature_finished":
            fid = event.get("feature")
            if (checkout, fid) in features:
                features[(checkout, fid)]["finished"] = True
            if fid in open_stack:
                open_stack.remove(fid)
            continue
        if not open_stack:
            continue
        current = features[(checkout, open_stack[-1])]
        if kind == "subagent_dispatched":
            current["subagents"] += 1
            if (event.get("role") or role_of(str(event.get("subagent_type") or ""))) == "reviewer":
                current["reviewer_dispatches"] += 1
        elif kind == "gate_run":
            current["gate_runs"] += 1
            if event.get("exit_code"):
                current["gate_failures"] += 1
                current["gate_failures_concurrent" if (event.get("concurrent") or 0) > 0
                        else "gate_failures_solo"] += 1
        elif kind == "reviewer_verdict":
            if event.get("agent_id"):
                current["_verdicts"][event["agent_id"]] = event.get("verdict")
            else:
                current["_anon_verdicts"].append(event.get("verdict"))

    rows = []
    for feature in features.values():
        verdicts = list(feature.pop("_verdicts").values()) + feature.pop("_anon_verdicts")
        feature["approved"] = sum(1 for v in verdicts if v == "Approved")
        feature["returned"] = len(verdicts) - feature["approved"]
        feature["missing_verdicts"] = max(0, feature["reviewer_dispatches"] - len(verdicts))
        feature["rework"] = feature["gate_failures_solo"] + feature["returned"]
        feature["overlapped"] = (feature["checkout"], feature["feature"]) in overlapped
        rows.append(feature)

    lanes = {}
    for lane in LANES:
        members = [r for r in rows if r["lane"] == lane]
        if not members:
            continue
        n = len(members)
        lanes[lane] = {"features": n, **{
            f"avg_{key}": round(sum(r[key] for r in members) / n, 2)
            for key in ("subagents", "gate_runs", "gate_failures_solo", "gate_failures_concurrent",
                        "returned", "rework")
        }}
    return rows, lanes


def render(rows, lanes) -> str:
    if not rows:
        return "No feature has been recorded yet (`/implement` and `/quick` record them)."
    head = "| Feature | Lane | Tier | Subagents | Gate runs | Gate failures (solo/concurrent) | Reviewer ✓/✗ | Rework |"
    lines = [head, "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        flag = " ⚠ overlapped" if r["overlapped"] else ""
        if r["missing_verdicts"]:
            flag += f" ⚠ missing verdicts: {r['missing_verdicts']}"
        where = f" ({r['checkout']})" if r["checkout"] != "main" else ""
        lines.append(f"| {r['feature']}{where}{flag} | {r['lane']} | {r['tier'] or '—'} | {r['subagents']} | {r['gate_runs']} | "
                     f"{r['gate_failures_solo']}/{r['gate_failures_concurrent']} | {r['approved']}/{r['returned']} | {r['rework']} |")
    if lanes:
        lines += ["", "| Lane | Features | Avg subagents | Avg gate runs | Avg solo failures | Avg concurrent failures | Avg reviewer returns | Avg rework |",
                  "|---|---|---|---|---|---|---|---|"]
        for lane, s in lanes.items():
            lines.append(f"| {lane} | {s['features']} | {s['avg_subagents']} | {s['avg_gate_runs']} | "
                         f"{s['avg_gate_failures_solo']} | {s['avg_gate_failures_concurrent']} | {s['avg_returned']} | {s['avg_rework']} |")
    return "\n".join(lines)


def latest_gates(events, checkout: str):
    """Latest `gate_run` per `agent_id` in `checkout` since its last
    `wave_started` (every gate when none was logged). Events without an
    `agent_id` share one slot.
    """
    mine = [e for e in events if (e.get("checkout") or "main") == checkout]
    start = max((i for i, e in enumerate(mine) if e.get("event") == "wave_started"), default=-1)
    latest = {}
    for e in mine[start + 1:]:
        if e.get("event") == "gate_run":
            latest[e.get("agent_id")] = e
    return list(latest.values())


GATED_ROLES = {"coder", "quickfix"}  # the roles run_build_test.py always gates


def pending_gates(events, checkout: str, now: float):
    """`coder`/`quickfix` subagents in `checkout`, since its last
    `wave_started`, whose latest lifecycle event is a stop with no `gate_run`
    after it: the hand-back arrived but the gate is still running (or was
    lost — killed, or past the hook's timeout, when `waiting_s` keeps
    growing). Other agents are gated only when they edited code, which the
    log doesn't show, so they aren't listed.
    """
    mine = [e for e in events if (e.get("checkout") or "main") == checkout]
    start = max((i for i, e in enumerate(mine) if e.get("event") == "wave_started"), default=-1)
    latest = {}
    for e in mine[start + 1:]:
        if e.get("event") in ("subagent_started", "subagent_stopped", "gate_run") and e.get("agent_id"):
            latest[e["agent_id"]] = e
    return [
        {"agent_id": agent_id, "agent_type": e.get("agent_type"),
         "waiting_s": round(now - e.get("ts", now))}
        for agent_id, e in latest.items()
        if e.get("event") == "subagent_stopped" and role_of(e.get("agent_type") or "") in GATED_ROLES
    ]


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Per-feature pipeline metrics (framework ADR 0020).")
    parser.add_argument("--project-dir", default=os.environ.get("CLAUDE_PROJECT_DIR", "."))
    sub = parser.add_subparsers(dest="cmd", required=True)
    start = sub.add_parser("start")
    start.add_argument("--feature", required=True)
    start.add_argument("--lane", choices=LANES, required=True)
    start.add_argument("--tier")
    finish = sub.add_parser("finish")
    finish.add_argument("--feature", required=True)
    wave = sub.add_parser("wave-start")
    wave.add_argument("--feature", required=True)
    sub.add_parser("gates")
    sub.add_parser("pending")
    report = sub.add_parser("report")
    report.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.cmd == "start":
        log_event(args.project_dir, "feature_started", feature=args.feature, lane=args.lane, tier=args.tier)
    elif args.cmd == "finish":
        log_event(args.project_dir, "feature_finished", feature=args.feature)
    elif args.cmd == "wave-start":
        log_event(args.project_dir, "wave_started", feature=args.feature)
    elif args.cmd == "gates":
        wt = linked_worktree(args.project_dir)
        print(json.dumps(latest_gates(read_events(args.project_dir), wt["admin"] if wt else "main"), indent=2))
    elif args.cmd == "pending":
        wt = linked_worktree(args.project_dir)
        print(json.dumps(pending_gates(read_events(args.project_dir), wt["admin"] if wt else "main",
                                       time.time()), indent=2))
    else:
        rows, lanes = summarize(read_events(args.project_dir))
        print(json.dumps({"features": rows, "lanes": lanes}, indent=2) if args.json else render(rows, lanes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
