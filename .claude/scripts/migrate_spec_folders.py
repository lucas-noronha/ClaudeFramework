"""Migrate legacy single-file specs to the spec-folder layout (framework
spec 0006 FR-16, framework ADR 0024 section 8).

    python migrate_spec_folders.py [--specs-dir DIR] [--spec NNNN ...]
                                   [--plan-heading TEXT ...] [--tier-label TEXT]
                                   [--apply]

A dry run by default: it prints a JSON report and writes nothing. `--apply`
migrates. Without `--specs-dir` it uses the session's project specs folder.
Exit 1 when any spec was refused.

A legacy `NNNN-name.md` is split on fixed headings, never on a heuristic:

  - `spec.md`: the frontmatter (status unchanged; `tier:` added from the
    plan's `**Tier:**` line, or `--tier-label`, only when absent) plus every
    section that is not one of the three below;
  - `plan.md`: the section whose heading equals a `--plan-heading` (default
    `Technical plan`); its heading becomes the H1 and its subsections move up
    one level — the one rewrite NFR-05 allows;
  - `tasks.md`: `## Tasks`;  `reconciliation.md`: `## Reconciliation`.

Without the right `--plan-heading` a translated plan stays in `spec.md` and
shows up under `unclassified_sections` in the report. A legacy lite spec
(`lite: true`) moves byte-identical to `NNNN-quick-<short>/spec.md`; its
branch changes from `task/<short>` to `task/quick-<short>` (reported).

Never destroys: the output is staged in `.NNNN-x.migrating/` (the resolver
ignores dot-names), every original line is checked to appear in exactly one
output file, in order, with its exact bytes (EOL, encoding and BOM are the
original's) — only the added frontmatter/tier line and the plan's heading
level may differ — then the folder is renamed into place and only then is the
original deleted. Any failure removes the staging folder and leaves the
original alone. A spec already migrated is skipped; a target that exists, or
a spec present in both layouts, is refused.

Links are never rewritten: references to the old file path and relative links
that stop resolving one level deeper are reported. After an apply the specs
index is rebuilt (hooks don't see script writes).
"""
import argparse
import json
import os
import re
import shutil
import sys

FRAMEWORK_HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(FRAMEWORK_HOME, "hooks"))
import _project_paths  # noqa: E402
import _spec_layout  # noqa: E402

BOM = b"\xef\xbb\xbf"
DEFAULT_PLAN_HEADING = "Technical plan"
KNOWN_SECTIONS = {
    "Feature name", "Business context", "Functional requirements", "Non-functional requirements",
    "Explicitly out of scope", "Roles and permissions involved", "Related specs",
    "Acceptance criteria", "Impact on existing architecture",
}
SUMMARIES = {
    "plan": "The technical plan: approach, scope check, Definition of Done and Test plan.",
    "tasks": "The ordered task list, one checkbox per task.",
    "reconciliation": "Spec-vs-code reconciliation outcomes written by reviewer and /reconcile.",
}
DOC_TYPES = {"plan": "spec-plan", "tasks": "spec-tasks", "reconciliation": "spec-reconciliation"}
FILE_NAMES = {"plan": "plan.md", "tasks": "tasks.md", "reconciliation": "reconciliation.md"}
TIERS = ("trivial", "standard", "structural")
SKIP_DIRS = {".git", "node_modules", "__pycache__"}


class Refused(Exception):
    pass


def split_lines(raw: bytes) -> list:
    """Lines with their exact bytes (terminators kept)."""
    return re.findall(rb"[^\n]*\n|[^\n]+", raw)


def text_of(line: bytes) -> str:
    return line.decode("utf-8", errors="replace").rstrip("\r\n")


def frontmatter_end(lines: list):
    """Index of the closing `---` line of a leading frontmatter block, or None."""
    if not lines or text_of(lines[0]).strip() != "---":
        return None
    for i in range(1, len(lines)):
        if text_of(lines[i]).strip() == "---":
            return i
    return None


def is_fence(line: bytes) -> bool:
    stripped = text_of(line).lstrip()
    return stripped.startswith("```") or stripped.startswith("~~~")


def role_of(title: str, plan_headings: list) -> str:
    if title in plan_headings:
        return "plan"
    if title == "Tasks":
        return "tasks"
    if title == "Reconciliation":
        return "reconciliation"
    return "spec"


def split_sections(lines: list, start: int, plan_headings: list) -> list:
    """Segments `(role, title, [line indexes])` after the frontmatter, split
    at `## ` headings outside code fences. The preamble has title None.
    """
    segments = [["spec", None, []]]
    in_fence = False
    for i in range(start, len(lines)):
        line = lines[i]
        if is_fence(line):
            in_fence = not in_fence
        elif not in_fence and text_of(line).startswith("## "):
            title = text_of(line)[3:].strip()
            segments.append([role_of(title, plan_headings), title, []])
        segments[-1][2].append(i)
    return segments


def promote(lines: list, indexes: list) -> list:
    """The plan's lines with the heading level lowered by one (`##` to `#`,
    `###` to `##`...), outside code fences. Returns `(index, bytes)` pairs.
    """
    out = []
    in_fence = False
    for i in indexes:
        line = lines[i]
        if is_fence(line):
            in_fence = not in_fence
        elif not in_fence and re.match(r"#{2,6} ", text_of(line)):
            line = line[1:]
        out.append((i, line))
    return out


def find_tier(plan_text: str, label: str):
    match = re.search(r"\*\*" + re.escape(label) + r":?\*\*:?\s*([^\s.,;:*]+)", plan_text)
    value = match.group(1).lower() if match else None
    return value if value in TIERS else None


def companion_budget(chars: int) -> int:
    """`~N tokens`: ceil(chars/4) rounded up to the next 50 (the chars/4
    heuristic of context_budget_check.py)."""
    tokens = -(-chars // 4)
    return max(50, -(-tokens // 50) * 50)


def _companion_header(role: str, number: str, eol: bytes, body: bytes) -> bytes:
    """Frontmatter of a companion file, its context_budget computed from the
    file's own real size (header included)."""
    budget = 50
    while True:
        header = eol.join([
            b"---",
            b"doc_type: " + DOC_TYPES[role].encode(),
            b"spec: " + number.encode(),
            b"summary: " + SUMMARIES[role].encode(),
            b"context_budget: ~" + str(budget).encode() + b" tokens",
            b"---",
            b"",
        ]) + eol
        chars = len((header + body).decode("utf-8", errors="replace"))
        needed = companion_budget(chars)
        if needed <= budget:
            return header
        budget = needed


def build_outputs(raw: bytes, number: str, plan_headings: list, tier_label: str) -> dict:
    """Plan the split in memory. Returns `{files: {name: [entries]}, ...}`
    where an entry is `("orig", index, out_bytes)` or `("add", kind, bytes)`.
    """
    has_bom = raw.startswith(BOM)
    body = raw[len(BOM):] if has_bom else raw
    lines = split_lines(body)
    eol = b"\r\n" if lines and lines[0].endswith(b"\r\n") else b"\n"
    fm_end = frontmatter_end(lines)
    start = 0 if fm_end is None else fm_end + 1
    segments = split_sections(lines, start, plan_headings)

    roles = {"spec": [], "plan": [], "tasks": [], "reconciliation": []}
    unclassified = []
    for role, title, indexes in segments:
        roles[role].extend(indexes)
        if role == "spec" and title is not None and title not in KNOWN_SECTIONS:
            unclassified.append(title)

    files = {}
    # spec.md: frontmatter (+ tier) then the non-companion sections, in order.
    spec_entries = []
    fm = _spec_layout.frontmatter(body.decode("utf-8", errors="replace")) if fm_end is not None else {}
    plan_text = b"".join(lines[i] for i in roles["plan"]).decode("utf-8", errors="replace")
    tier_key = "tier" in fm
    tier = fm.get("tier") or (None if tier_key else find_tier(plan_text, tier_label))
    tier_added = False
    for i in range(0, start):
        if i == fm_end and not tier_key and tier:
            spec_entries.append(("add", "tier", b"tier: " + tier.encode("utf-8") + eol))
            tier_added = True
        spec_entries.append(("orig", i, lines[i]))
    for i in roles["spec"]:
        spec_entries.append(("orig", i, lines[i]))
    files["spec.md"] = spec_entries

    for role in ("plan", "tasks", "reconciliation"):
        if not roles[role]:
            continue
        pairs = promote(lines, roles[role]) if role == "plan" else [(i, lines[i]) for i in roles[role]]
        body = b"".join(b for _, b in pairs)
        header = _companion_header(role, number, eol, body)
        entries = [("add", "header", header)]
        entries.extend(("orig", i, b) for i, b in pairs)
        files[FILE_NAMES[role]] = entries

    return {
        "files": files, "lines": lines, "start": start, "has_bom": has_bom,
        "tier": tier, "tier_added": tier_added, "tier_key": tier_key, "unclassified": unclassified,
        "has_plan": bool(roles["plan"]),
    }


def render(entries: list, has_bom: bool) -> bytes:
    return (BOM if has_bom else b"") + b"".join(e[2] for e in entries)


def verify(plan: dict, actual: dict) -> None:
    """Raise Refused unless `actual` (`{name: bytes}`, as written) accounts
    for every original line exactly once, in order, byte for byte — apart
    from the added header/tier lines and the plan's one-level heading
    promotion.
    """
    lines, has_bom = plan["lines"], plan["has_bom"]
    seen = set()
    for name, entries in plan["files"].items():
        if actual.get(name) != render(entries, has_bom):
            raise Refused("verification: %s differs from the planned content" % name)
        last = -1
        for kind, a, b in entries:
            if kind == "add":
                if a not in ("header", "tier"):
                    raise Refused("verification: unexpected added content in %s" % name)
                continue
            original = lines[a]
            allowed = b == original or (name == "plan.md" and original == b"#" + b)
            if not allowed:
                raise Refused("verification: line %d changed in %s" % (a + 1, name))
            if a <= last or a in seen:
                raise Refused("verification: line %d out of order or duplicated" % (a + 1))
            last = a
            seen.add(a)
    missing = [i + 1 for i in range(len(lines)) if i not in seen and i >= 0]
    # frontmatter lines are in spec.md's entries too (start..), so every index must be seen
    if missing:
        raise Refused("verification: original lines not accounted for: %s" % missing[:5])


def lite_target(name: str) -> str:
    """`NNNN-quick-<short>` for a legacy lite spec file name, never a doubled `quick-`."""
    stem = name[:-3] if name.endswith(".md") else name
    short = _spec_layout.short_name_of(stem)
    if short.startswith("quick-"):
        return stem
    return "%s-quick-%s" % (stem[:4], short)


def scan_links(specs_dir: str, old_name: str, original: str, lines: list) -> dict:
    """Report, never rewrite: references to the old path, and relative links
    in the spec that stop resolving one level deeper.
    """
    docs_root = os.path.dirname(os.path.dirname(os.path.abspath(specs_dir)))
    references = []
    for base, dirs, names in os.walk(docs_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".migrating")]
        for n in names:
            path = os.path.join(base, n)
            if not n.endswith(".md") or os.path.abspath(path) == os.path.abspath(original):
                continue
            for lineno, line in enumerate(_spec_layout.read_text(path).split("\n"), 1):
                if old_name in line:
                    references.append("%s:%d" % (_project_paths.normalize(os.path.relpath(path, docs_root)), lineno))
    deeper = []
    for line in lines:
        for target in re.findall(r"\]\(([^)\s]+)\)", text_of(line)):
            if re.match(r"^([A-Za-z][A-Za-z0-9+.-]*:|#|/)", target):
                continue
            if target not in deeper:
                deeper.append(target)
    return {"references_to_old_path": references, "relative_links_one_level_deeper": deeper}


def migrate_one(ref: dict, specs_dir: str, args, apply: bool) -> dict:
    source = ref["spec_file"]
    name = os.path.basename(source)
    number = ref["number"]
    result = {"spec": number, "source": name, "action": None}

    with open(source, "rb") as f:
        raw = f.read()
    try:
        (raw[len(BOM):] if raw.startswith(BOM) else raw).decode("utf-8")
    except UnicodeDecodeError:
        raise Refused("not valid UTF-8; migrate by hand")

    siblings = [r for r in _spec_layout.iter_specs(specs_dir) if r["number"] == number and r["folder"]]
    if siblings:
        raise Refused("exists in both layouts: %s" % os.path.basename(siblings[0]["folder"]))

    lite = ref["lite"]
    target_name = lite_target(name) if lite else name[:-3]
    target = os.path.join(specs_dir, target_name)
    if os.path.exists(target):
        raise Refused("target exists: %s" % target_name)
    result["target"] = target_name

    if lite:
        plan = {"files": {"spec.md": [("add", "whole", raw)]}, "lines": [], "has_bom": False}
        result["action"] = "migrate-lite"
        result["branch_change"] = "task/%s -> task/%s" % (ref["short_name"], _spec_layout.short_name_of(target_name))
        outputs = {"spec.md": raw}
        link_lines = split_lines(raw)
    else:
        plan = build_outputs(raw, number, args.plan_heading or [DEFAULT_PLAN_HEADING], args.tier_label)
        outputs = {n: render(e, plan["has_bom"]) for n, e in plan["files"].items()}
        verify(plan, outputs)
        result["action"] = "migrate"
        result["files"] = sorted(outputs)
        result["tier"] = plan["tier"]
        result["tier_added"] = plan["tier_added"]
        if not plan["tier"]:
            result["tier_missing"] = True
        if plan["tier_key"] and not plan["tier"]:
            result.setdefault("warnings", []).append("frontmatter has an empty `tier:` key: left as is")
        if plan["unclassified"]:
            result["unclassified_sections"] = plan["unclassified"]
        if not plan["has_plan"]:
            result.setdefault("warnings", []).append(
                "no plan heading matched (%s): any plan stays in spec.md; pass --plan-heading for a translated setup"
                % ", ".join(args.plan_heading or [DEFAULT_PLAN_HEADING]))
        link_lines = plan["lines"]

    result.update(scan_links(specs_dir, name, source, link_lines))
    fm = _spec_layout.frontmatter(raw.decode("utf-8", errors="replace"))
    if fm.get("status") == "approved":
        unchecked = len(re.findall(rb"(?m)^\s*- \[ \]", raw))
        result.setdefault("warnings", []).append(
            "status approved (in flight, %d unchecked box(es)): in mode A a spec branch still editing the "
            "legacy file will hit a modify/delete conflict on merge" % unchecked)

    if apply:
        stage = os.path.join(specs_dir, ".%s.migrating" % target_name)
        try:
            if os.path.isdir(stage):
                shutil.rmtree(stage)
            os.makedirs(stage)
            for fname, data in outputs.items():
                with open(os.path.join(stage, fname), "wb") as f:
                    f.write(data)
            written = {}
            for fname in outputs:
                with open(os.path.join(stage, fname), "rb") as f:
                    written[fname] = f.read()
            if lite:
                if written["spec.md"] != raw:
                    raise Refused("verification: lite spec not byte-identical")
            else:
                verify(plan, written)
            os.rename(stage, target)
        except BaseException:
            shutil.rmtree(stage, ignore_errors=True)
            raise
        result["applied"] = True
        try:
            os.remove(source)
        except OSError:
            result["action"] = "applied_original_kept"
            result["original_kept"] = True
            result.setdefault("warnings", []).append(
                "folder created, original not deleted (locked): remove %s by hand" % name)
    return result


def find_project(specs_dir: str):
    """The project whose `specs_dir` this is (for the index rebuild), or None."""
    want = os.path.normcase(_project_paths.normalize(os.path.abspath(specs_dir)))
    candidates = [os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())]
    candidates.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(specs_dir)))))
    for candidate in candidates:
        got = os.path.normcase(_project_paths.normalize(os.path.abspath(_project_paths.specs_dir(candidate))))
        if got == want:
            return candidate
    return None


def run(args) -> dict:
    project = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    specs_dir = args.specs_dir or _project_paths.specs_dir(project)
    specs_dir = os.path.abspath(specs_dir)
    report = {"dry_run": not args.apply, "specs_dir": specs_dir, "results": [], "refused": 0}

    refs = _spec_layout.iter_specs(specs_dir)
    wanted = None
    if args.spec:
        wanted = {str(int(s)).zfill(4) for s in args.spec if str(s).isdigit()}
        for s in sorted(wanted):
            if not any(r["number"] == s for r in refs):
                report["results"].append({"spec": s, "action": "refuse", "reason": "no such spec"})
                report["refused"] += 1
    for ref in refs:
        if wanted is not None and ref["number"] not in wanted:
            continue
        if ref["layout"] != "legacy":
            has_legacy = any(r["number"] == ref["number"] and r["layout"] == "legacy" for r in refs)
            if not has_legacy:
                report["results"].append({"spec": ref["number"], "source": os.path.basename(ref["folder"]),
                                          "action": "skip", "reason": "already migrated"})
            continue
        try:
            report["results"].append(migrate_one(ref, specs_dir, args, args.apply))
        except Refused as err:
            report["results"].append({"spec": ref["number"], "source": os.path.basename(ref["spec_file"]),
                                      "action": "refuse", "reason": str(err)})
            report["refused"] += 1
        except OSError as err:
            report["results"].append({"spec": ref["number"], "source": os.path.basename(ref["spec_file"]),
                                      "action": "refuse", "reason": "I/O error: %s" % err})
            report["refused"] += 1

    if args.apply and any(r.get("applied") for r in report["results"]):
        proj = find_project(specs_dir)
        if proj is None:
            report["index"] = "not rebuilt: specs dir does not belong to the session's project"
        else:
            sys.path.insert(0, os.path.join(FRAMEWORK_HOME, "hooks"))
            import spec_index  # noqa: E402
            report["index"] = spec_index.rebuild(proj)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Migrate legacy single-file specs to spec folders.")
    parser.add_argument("--specs-dir")
    parser.add_argument("--spec", action="append", metavar="NNNN")
    parser.add_argument("--plan-heading", action="append", metavar="TEXT")
    parser.add_argument("--tier-label", default="Tier")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    report = run(args)
    print(json.dumps(report, indent=2))
    return 1 if report["refused"] else 0


if __name__ == "__main__":
    sys.exit(main())
