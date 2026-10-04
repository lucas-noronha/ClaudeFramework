"""Mode B: mirror the main checkout's framework links into a git worktree
(framework spec 0004 FR-07, framework ADR 0022 section 4).

    python link_worktree.py WORKTREE [--dry-run]
    python link_worktree.py --repair [--dry-run]      # every `git worktree list` entry

In mode B a target repo holds three never-committed links — `.claude`,
`docs` and `CLAUDE.md` — at the root and at every registered monorepo
subpath. A fresh worktree has none of them. This creates the same links at
the same subpaths inside the worktree, then adds root-anchored lines for
them to the repo's shared `info/exclude` (never to a committed file).

- Targets are the main checkout's *resolved* targets, never the raw relative
  link text: the worktree sits at another depth. `CLAUDE.md` points at
  `<subtree>/CLAUDE.md`, verified to be the same file as the main checkout's.
- Symlink first; on a Windows privilege error a junction (directories) or a
  hard link (`CLAUDE.md`, same volume only).
- A no-op when the main checkout has no such links (modes A and C).
- Refuses a worktree that resolves inside the AI-repo (Claude Code's own
  `<repo>/.claude/worktrees/*` in mode B): linking `.claude` there would
  be a directory cycle.
- Idempotent. A missing or stale link is (re)created, a correct one left
  alone, and anything else (real content in the way) is reported, never
  touched.

Applies by default — `/worktree` calls it right after `git worktree add`
and it only ever creates links and exclude lines. `--dry-run` reports
without writing. Prints a JSON report; exit 1 on any conflict or refusal.
"""
import argparse
import filecmp
import json
import os
import subprocess
import sys

FRAMEWORK_HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(FRAMEWORK_HOME, "hooks"))
from _project_paths import PROJECTS_ROOT_KEY, describe, linked_worktree, normalize  # noqa: E402

ITEMS = (".claude", "docs", "CLAUDE.md")
FILE_ITEM = "CLAUDE.md"


def _fold(path: str) -> str:
    path = normalize(os.path.abspath(path))
    return path.lower() if os.name == "nt" else path


def _inside(root: str, path: str) -> bool:
    root, path = _fold(root), _fold(path)
    return path == root or path.startswith(root + "/")


def is_link(path: str) -> bool:
    """Symlink, Windows junction, or (for a file) a hard link."""
    if os.path.islink(path):
        return True
    isjunction = getattr(os.path, "isjunction", None)
    if isjunction is not None and isjunction(path):
        return True
    return os.path.isfile(path) and os.stat(path).st_nlink > 1


def same(a: str, b: str) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def make_link(target: str, dest: str, is_file: bool) -> str:
    """Create `dest` -> `target` and return the mechanism used."""
    try:
        os.symlink(target, dest, target_is_directory=not is_file)
        return "symlink"
    except (OSError, NotImplementedError):
        pass
    if is_file:
        os.link(target, dest)
        return "hardlink"
    if os.name != "nt":
        raise OSError("symlink failed and only Windows has a junction fallback")
    try:
        import _winapi
        _winapi.CreateJunction(target, dest)
    except (ImportError, AttributeError, OSError):
        result = subprocess.run(["cmd", "/c", "mklink", "/J", dest, target], capture_output=True, text=True)
        if result.returncode != 0:
            raise OSError(f"mklink /J failed: {result.stdout.strip()} {result.stderr.strip()}")
    return "junction"


def remove_link(path: str) -> None:
    if os.path.isdir(path) and not os.path.islink(path):
        os.rmdir(path)  # a junction: removes the link, never its target
    else:
        os.unlink(path)


def registered_paths(main: str):
    """`[(subpath, subtree)]` for every registry entry at or inside `main`."""
    registry_path = describe(main).get("registry")
    if not registry_path:
        return []
    try:
        with open(registry_path, encoding="utf-8") as f:
            registry = json.load(f)
    except (OSError, ValueError):
        return []
    found = []
    for key, value in registry.items():
        if key == PROJECTS_ROOT_KEY or not isinstance(value, str) or not value or not _inside(main, key):
            continue
        sub = normalize(os.path.relpath(key, main))
        found.append(("" if sub == "." else sub, value))
    return sorted(found)


def plan_item(main_dir: str, item: str, subtree: str):
    """`(target, None)` when `main_dir/item` is a framework link, `(None, why)`
    to skip it, `(None, None)` when it isn't a link at all (modes A/C).
    """
    path = os.path.join(main_dir, item)
    if not (os.path.lexists(path) and is_link(path)):
        return None, None
    if item == FILE_ITEM:
        target = os.path.join(subtree, FILE_ITEM)
        if not same(path, target):
            return None, f"{path} is not the same file as {target}"
        return target, None
    return os.path.realpath(path), None


def sync_item(target: str, dest: str, item: str, dry_run: bool) -> dict:
    is_file = item == FILE_ITEM
    if os.path.lexists(dest):
        if same(dest, target):
            return {"item": item, "status": "already linked"}
        stale = os.path.islink(dest) or not os.path.exists(dest)  # a symlink to elsewhere, or dangling
        if is_file:
            # A detached copy (an editor replaced the hard link): same bytes, safe to relink.
            stale = stale or filecmp.cmp(dest, target, shallow=False)
        else:
            stale = stale or is_link(dest)  # a junction to the wrong place
        if not stale:
            return {"item": item, "status": "conflict", "detail": f"{dest} exists and is not a link to {target}"}
        if not dry_run:
            remove_link(dest)
    if dry_run:
        return {"item": item, "status": "would link", "target": normalize(target)}
    mechanism = make_link(target, dest, is_file)
    return {"item": item, "status": "linked", "mechanism": mechanism, "target": normalize(target)}


def add_excludes(common_dir: str, patterns, dry_run: bool):
    """Append the missing root-anchored patterns to `info/exclude`; returns
    the ones added.
    """
    path = os.path.join(common_dir, "info", "exclude")
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        text = ""
    have = {line.strip() for line in text.splitlines()}
    missing = [p for p in patterns if p not in have]
    if missing and not dry_run:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        lead = "" if not text or text.endswith("\n") else "\n"
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(lead + "".join(p + "\n" for p in missing))
    return missing


def link_worktree(worktree: str, dry_run: bool = False) -> dict:
    worktree = os.path.abspath(worktree)
    report = {"worktree": normalize(worktree), "links": [], "excludes": [], "errors": []}
    wt = linked_worktree(worktree)
    if wt is None:
        report["errors"].append("not a linked git worktree")
        return report
    sub = wt["subpath"]
    root = os.path.abspath(worktree)
    for _ in range(len([p for p in sub.split("/") if p])):
        root = os.path.dirname(root)
    main = wt["main"]
    report["main"] = main

    plans = []  # (subpath, item, target)
    ai_roots = set()
    for subpath, subtree in registered_paths(main):
        main_dir = os.path.join(main, subpath) if subpath else main
        for item in ITEMS:
            target, why = plan_item(main_dir, item, subtree)
            if why:
                report["errors"].append(why)
            elif target:
                plans.append((subpath, item, target))
                if item != FILE_ITEM:
                    ai_roots.add(os.path.dirname(target))
    report["noop"] = not plans
    if not plans:
        return report

    real_root = os.path.realpath(root)
    for ai_root in sorted(ai_roots):
        if _inside(ai_root, real_root) or _inside(ai_root, root):
            report["errors"].append(f"refusing: {report['worktree']} resolves inside the AI-repo {normalize(ai_root)}")
            report["refused"] = True
            return report

    patterns = []
    for subpath, item, target in plans:
        parent = os.path.join(root, subpath) if subpath else root
        if not os.path.isdir(parent):
            report["errors"].append(f"{parent} does not exist in the worktree")
            continue
        try:
            result = sync_item(target, os.path.join(parent, item), item, dry_run)
        except OSError as exc:
            result = {"item": item, "status": "error", "detail": str(exc)}
        result["path"] = normalize(os.path.join(subpath, item)) if subpath else item
        report["links"].append(result)
        if result["status"] in ("conflict", "error"):
            report["errors"].append(result.get("detail", result["status"]))
        else:
            patterns.append("/" + result["path"])

    common = os.path.join(main, ".git")
    try:
        report["excludes"] = add_excludes(common, patterns, dry_run)
    except OSError as exc:
        report["errors"].append(f"info/exclude: {exc}")
    return report


def other_worktrees(start: str):
    """Every linked worktree path from `git worktree list --porcelain`."""
    result = subprocess.run(["git", "-C", start, "worktree", "list", "--porcelain"], capture_output=True,
                            text=True, encoding="utf-8", timeout=30)
    if result.returncode != 0:
        return None, result.stderr.strip()
    paths = [line[len("worktree "):].strip() for line in result.stdout.splitlines() if line.startswith("worktree ")]
    return paths[1:], None  # the first entry is the main checkout


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Mirror mode B's framework links into a git worktree.")
    parser.add_argument("worktree", nargs="?")
    parser.add_argument("--repair", action="store_true", help="relink every worktree of the current repo")
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    args = parser.parse_args(argv)
    if bool(args.worktree) == args.repair:
        parser.error("pass a worktree path or --repair, not both")

    if args.repair:
        start = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        paths, error = other_worktrees(start)
        if paths is None:
            print(json.dumps({"error": f"git worktree list failed: {error}"}))
            return 2
        reports = [link_worktree(p, args.dry_run) for p in paths]
    else:
        reports = [link_worktree(args.worktree, args.dry_run)]

    print(json.dumps({"dry_run": args.dry_run, "worktrees": reports}, indent=2))
    return 1 if any(r["errors"] for r in reports) else 0


if __name__ == "__main__":
    sys.exit(main())
