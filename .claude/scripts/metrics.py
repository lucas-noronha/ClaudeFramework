"""Per-feature pipeline cost, from the raw event log (framework ADR 0011, extended
by framework ADR 0020, framework spec 0003 FR-05).

    metrics.py start --feature ID --lane full|fast [--tier T]
    metrics.py finish --feature ID
    metrics.py report [--json]

`/implement` and `/quick` call `start`/`finish` around a feature, which
appends `feature_started`/`feature_finished` to the same
`pipeline-metrics.jsonl` the hooks write. No new state file. `report`
attributes every event between a feature's start and finish to it:

- subagents: `subagent_dispatched` (pipeline_metrics.py)
- gate runs and gate failures: `gate_run` (run_build_test.py)
- reviewer verdicts: `reviewer_verdict` (pipeline_metrics.py)
- rework: gate failures plus reviewer `Returned` verdicts

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

FRAMEWORK_HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(FRAMEWORK_HOME, "hooks"))
from _pipeline_metrics import LOG_FILENAME, log_event  # noqa: E402
from _project_paths import state_file_path  # noqa: E402

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
        elif kind == "gate_run":
            current["gate_runs"] += 1
            if event.get("exit_code"):
                current["gate_failures"] += 1
        elif kind == "reviewer_verdict":
            current["approved" if event.get("verdict") == "Approved" else "returned"] += 1

    rows = []
    for feature in features.values():
        feature["rework"] = feature["gate_failures"] + feature["returned"]
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
            for key in ("subagents", "gate_runs", "returned", "rework")
        }}
    return rows, lanes


def render(rows, lanes) -> str:
    if not rows:
        return "No feature has been recorded yet (`/implement` and `/quick` record them)."
    head = "| Feature | Lane | Tier | Subagents | Gate runs | Gate failures | Reviewer ✓/✗ | Rework |"
    lines = [head, "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        flag = " ⚠ overlapped" if r["overlapped"] else ""
        where = f" ({r['checkout']})" if r["checkout"] != "main" else ""
        lines.append(f"| {r['feature']}{where}{flag} | {r['lane']} | {r['tier'] or '—'} | {r['subagents']} | {r['gate_runs']} | "
                     f"{r['gate_failures']} | {r['approved']}/{r['returned']} | {r['rework']} |")
    if lanes:
        lines += ["", "| Lane | Features | Avg subagents | Avg gate runs | Avg reviewer returns | Avg rework |",
                  "|---|---|---|---|---|---|"]
        for lane, s in lanes.items():
            lines.append(f"| {lane} | {s['features']} | {s['avg_subagents']} | {s['avg_gate_runs']} | "
                         f"{s['avg_returned']} | {s['avg_rework']} |")
    return "\n".join(lines)


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
    report = sub.add_parser("report")
    report.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.cmd == "start":
        log_event(args.project_dir, "feature_started", feature=args.feature, lane=args.lane, tier=args.tier)
    elif args.cmd == "finish":
        log_event(args.project_dir, "feature_finished", feature=args.feature)
    else:
        rows, lanes = summarize(read_events(args.project_dir))
        print(json.dumps({"features": rows, "lanes": lanes}, indent=2) if args.json else render(rows, lanes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
