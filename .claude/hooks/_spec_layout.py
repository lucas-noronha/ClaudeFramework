"""Shared layout resolver for a project's specs (framework ADR 0024
section 1). Not a hook entry point and not wired in settings.json —
imported by the hooks and called by the pipeline commands, the same pattern
`_project_paths.py` and `_pipeline_metrics.py` establish.

A spec lives in one of three layouts, and every consumer asks this module
instead of parsing a path:

  - `legacy`: one file, `<specs>/NNNN-name.md`;
  - `folder`: `<specs>/NNNN-name/` holding `spec.md`, `plan.md`,
    `tasks.md`, `reconciliation.md` and any other `.md` as a note;
  - `lite`: a folder whose `spec.md` has `lite: true` in its frontmatter
    (usually `NNNN-quick-name/`, but the name never decides it). A lite
    spec keeps plan, tasks and reconciliation as sections of `spec.md`.

Stdlib only, file reads only, and it fails open: an unreadable file, a
missing folder or a malformed frontmatter yields "not a spec" or an empty
value, never an exception inside a hook. Frontmatter and sections parse CRLF
and LF alike, with or without a BOM. Dot-names, `README.md` and anything
deeper than one folder level are ignored.

Run as a script it prints the resolution as JSON, for prompts:

  python _spec_layout.py resolve <path | folder | NNNN> [--specs-dir DIR]
  python _spec_layout.py next-number [--specs-dir DIR]
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _project_paths  # noqa: E402

NUMBER_RE = re.compile(r"^(\d{4})-")
ROLES = {"spec.md": "spec", "plan.md": "plan", "tasks.md": "tasks", "reconciliation.md": "reconciliation"}


def _norm(path: str) -> str:
    return os.path.normcase(_project_paths.normalize(os.path.abspath(path)))


def read_text(path: str) -> str:
    """The file as text with BOM stripped and CRLF folded to LF; `""` when
    it can't be read.
    """
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError:
        return ""
    return raw.decode("utf-8-sig", errors="replace").replace("\r\n", "\n").replace("\r", "\n")


def frontmatter(text: str) -> dict:
    """The `key: value` pairs of a leading `---` block (values as stripped,
    unquoted strings); `{}` when there is none.
    """
    lines = text.lstrip("﻿").replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return {}
    data = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return data
        match = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", line)
        if match:
            value = match.group(2).strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            data[match.group(1)] = value
    return {}  # never closed: not a frontmatter block


def section(text: str, heading: str):
    """The body under `## <heading>` up to the next `## ` heading, or None
    when the heading is absent.
    """
    lines = text.replace("\r\n", "\n").split("\n")
    body = None
    for line in lines:
        if line.rstrip() == "## " + heading:
            body = []
        elif body is not None and line.startswith("## "):
            break
        elif body is not None:
            body.append(line)
    return None if body is None else "\n".join(body)


def _is_lite(spec_file) -> bool:
    return bool(spec_file) and frontmatter(read_text(spec_file)).get("lite", "").lower() == "true"


def short_name_of(name: str) -> str:
    """A folder or file name without its `NNNN-` prefix and `.md`: the
    branch short name (ADR 0024 section 7). `0012-quick-foo` is
    `quick-foo`.
    """
    stem = name[:-3] if name.endswith(".md") else name
    return NUMBER_RE.sub("", stem, count=1)


def _ref(specs: str, entry: str, role=None, path=None) -> dict:
    """The reference for one spec entry: `entry` is the folder (layout
    folder/lite) or the single file (legacy).
    """
    is_folder = os.path.isdir(entry)
    name = os.path.basename(entry)
    if is_folder:
        spec_file = os.path.join(entry, "spec.md")
        spec_file = spec_file if os.path.isfile(spec_file) else None
        lite = _is_lite(spec_file)
        try:
            files = sorted(f for f in os.listdir(entry) if f.endswith(".md") and not f.startswith("."))
        except OSError:
            files = []
        single = None
    else:
        spec_file = entry
        lite = _is_lite(entry)
        files = [name]
        single = entry

    fm = frontmatter(read_text(spec_file)) if spec_file else {}
    spec_id = fm.get("id") or (NUMBER_RE.match(name).group(1) if NUMBER_RE.match(name) else None)
    in_spec_file = single or (spec_file if lite else None)
    folder_join = (lambda f: os.path.join(entry, f)) if is_folder else None
    return {
        "layout": "legacy" if not is_folder else ("lite" if lite else "folder"),
        "id": spec_id,
        "number": NUMBER_RE.match(name).group(1) if NUMBER_RE.match(name) else None,
        "folder": entry if is_folder else None,
        "file": path,
        "spec_file": spec_file,
        "role": role,
        "files": files,
        "lite": lite,
        "short_name": short_name_of(name),
        "status_file": spec_file,
        "tasks": {"file": in_spec_file, "section": "Tasks"} if in_spec_file
        else {"file": folder_join("tasks.md"), "section": "Tasks"},
        "reconciliation": {"file": in_spec_file, "section": "Reconciliation"} if in_spec_file
        else {"file": folder_join("reconciliation.md"), "section": None},
    }


def classify(specs_dir: str, path: str):
    """The spec reference for a file under `specs_dir`, or None.

    A legacy file sits directly in `specs_dir` (`NNNN-*.md`, not `README.md`
    or a dot-name). A folder file sits in `specs_dir/NNNN-*/` and is a
    `.md`; its `role` is `spec`, `plan`, `tasks`, `reconciliation`, or
    `note` for any other name. Deeper paths, other folders and dot-names
    are None. Never raises.
    """
    try:
        if not path or not specs_dir:
            return None
        name = os.path.basename(path)
        if not name.endswith(".md") or name.startswith("."):
            return None
        parent = os.path.dirname(os.path.abspath(path))
        root = _norm(specs_dir)
        if _norm(parent) == root:
            if name == "README.md" or not NUMBER_RE.match(name):
                return None
            return _ref(specs_dir, os.path.abspath(path), role="spec", path=os.path.abspath(path))
        if _norm(os.path.dirname(parent)) == root:
            folder = os.path.basename(parent)
            if folder.startswith(".") or not NUMBER_RE.match(folder):
                return None
            folder_path = os.path.join(os.path.abspath(specs_dir), folder)
            return _ref(specs_dir, folder_path, role=ROLES.get(name, "note"), path=os.path.abspath(path))
    except (OSError, ValueError):
        return None
    return None


def iter_specs(specs_dir: str):
    """One reference per spec, legacy files and folders alike, ordered by
    name. A folder without `spec.md` is still listed (`spec_file` None).
    """
    try:
        names = sorted(os.listdir(specs_dir))
    except OSError:
        return []
    refs = []
    for name in names:
        full = os.path.join(specs_dir, name)
        if name.startswith(".") or not NUMBER_RE.match(name):
            continue
        if os.path.isdir(full):
            refs.append(_ref(specs_dir, full))
        elif name.endswith(".md") and os.path.isfile(full):
            refs.append(_ref(specs_dir, full, role="spec", path=full))
    return refs


def numbers_in_use(specs_dir: str) -> set:
    """Every `NNNN` already held, by name prefix or frontmatter `id`."""
    used = set()
    for ref in iter_specs(specs_dir):
        for value in (ref["number"], ref["id"]):
            if value and str(value).isdigit():
                used.add(int(value))
    return used


def next_number(specs_dir: str) -> str:
    """The next free four-digit number across every layout."""
    used = numbers_in_use(specs_dir)
    return "%04d" % ((max(used) if used else 0) + 1)


def find(specs_dir: str, target: str):
    """A spec reference from a path (any file of the spec), a folder or
    file name, or a bare `NNNN`; None when nothing matches.
    """
    if not target:
        return None
    target = target.strip()
    if os.path.sep in target or "/" in target or os.path.exists(target):
        abs_target = os.path.abspath(target)
        found = classify(specs_dir, abs_target)
        if found is not None:
            return found
        if os.path.isdir(abs_target) and _norm(os.path.dirname(abs_target)) == _norm(specs_dir):
            base = os.path.basename(abs_target)
            if NUMBER_RE.match(base) and not base.startswith("."):
                return _ref(specs_dir, abs_target)
        target = os.path.basename(abs_target)
    bare = target[:-3] if target.endswith(".md") else target
    refs = iter_specs(specs_dir)
    if re.fullmatch(r"\d{1,4}", bare):
        number = int(bare)
        for ref in refs:
            if any(v and str(v).isdigit() and int(v) == number for v in (ref["number"], ref["id"])):
                return ref
        return None
    for ref in refs:
        entry = ref["folder"] or ref["spec_file"]
        stem = os.path.basename(entry)
        if (stem[:-3] if stem.endswith(".md") else stem) == bare:
            return ref
    return None


def branch_short_name(ref: dict) -> str:
    return ref["short_name"]


def resolve(specs_dir: str, target: str):
    """`find` plus the derived `branch`; the CLI's JSON shape."""
    ref = find(specs_dir, target)
    if ref is None:
        return None
    out = dict(ref)
    out["branch"] = "task/" + branch_short_name(ref)
    return out


def _main(argv) -> int:
    args = list(argv)
    specs = None
    if "--specs-dir" in args:
        i = args.index("--specs-dir")
        if i + 1 >= len(args):
            return _usage()
        specs = args[i + 1]
        del args[i:i + 2]
    if specs is None:
        specs = _project_paths.specs_dir(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    if args[:1] == ["next-number"] and len(args) == 1:
        print(next_number(specs))
        return 0
    if args[:1] == ["resolve"] and len(args) == 2:
        result = resolve(specs, args[1])
        print(json.dumps(result, indent=2))
        return 0 if result is not None else 1
    return _usage()


def _usage() -> int:
    print("usage: python _spec_layout.py resolve <path | folder | NNNN> [--specs-dir DIR]\n"
          "       python _spec_layout.py next-number [--specs-dir DIR]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
