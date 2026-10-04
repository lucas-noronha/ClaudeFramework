"""Import an existing documentation base into a project subtree laid out
per ADR 0015, without touching the source (ADR 0017, spec 0001 FR-12).

    python migrate_context.py --source OLD_DOCS --dest SUBTREE \\
        [--map adr=decisions --map notes/arch=architecture ...] \\
        [--rename-key titulo=title ...] [--spec-status implemented] [--apply]

1. **Folders**: each source path is mapped by the longest matching
   `--map OLD=NEW` prefix. Top-level folders with no explicit map use a
   name heuristic (`adr`/`decision` → `decisions`; `arch`/`arq` →
   `architecture`; `spec`/`requirement`/`requisit`/`feature` →
   `product/specs`). Anything else keeps its relative path, and the report
   says so.
2. **Numbering**: specs and ADRs get `NNNN-slug.md` names, numbered per
   project. Existing numbers (`7-x`, `ADR-007-x`, `0007-x`) are kept
   when free; unnumbered files and collisions take the next free number.
   A source `README.md` inside those two folders becomes
   `legacy-index.md`, since the index hooks own `README.md` there.
3. **Frontmatter**: keys are renamed per `--rename-key`, then
   `doc_type`, `status` and `context_budget` are added where missing
   (plus `id` for specs/ADRs and `supersedes`/`superseded_by` for ADRs).
   Existing keys and bodies are never removed or reworded.
4. **Links**: every relative Markdown link and reference definition
   outside fenced code is re-pointed from the doc's new location to its
   target's new location, keeping `#anchors`. A link into code outside
   the source tree is re-pointed to the same file.
5. **Verification**: every relative link in the result is resolved, and
   every doc is checked for the three required keys. Links the migration
   broke are counted apart from links that were already broken in the
   source. The source tree is hashed before and after, so "unchanged"
   is a measurement, not a promise.

Refuses a non-empty `--dest`. Dry run by default. Prints a JSON report.
"""
import argparse
import hashlib
import json
import os
import posixpath
import re
import sys
import urllib.parse

HEURISTICS = [
    (re.compile(r"adr|decis"), "decisions"),
    (re.compile(r"arch|arq"), "architecture"),
    (re.compile(r"spec|requirement|requisit|feature"), "product/specs"),
]
NUMBERED = {"product/specs": "spec", "decisions": "adr"}
DOC_TYPES = {"product/specs": "spec", "decisions": "adr", "architecture": "architecture"}
FENCE = re.compile(r"^(```|~~~)")
INLINE_LINK = re.compile(r"(!?\[[^\]]*\]\()(<[^>]+>|[^)\s]+)((?:\s+\"[^\"]*\")?\))")
REF_DEF = re.compile(r"^(\s{0,3}\[[^\]]+\]:\s*)(<[^>]+>|\S+)(.*)$")
FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


def posix(path: str) -> str:
    return path.replace("\\", "/")


def tree_hash(root: str) -> str:
    digest = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            digest.update(posix(os.path.relpath(full, root)).encode())
            with open(full, "rb") as f:
                digest.update(hashlib.sha256(f.read()).digest())
    return digest.hexdigest()


def slug(stem: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    return value or "untitled"


def map_folder(rel_dir: str, maps):
    for old, new in sorted(maps.items(), key=lambda kv: -len(kv[0])):
        if rel_dir == old or rel_dir.startswith(old + "/"):
            return (new + rel_dir[len(old):]).strip("/"), True
    top = rel_dir.split("/", 1)[0]
    if top:
        for pattern, target in HEURISTICS:
            if pattern.search(top.lower()):
                return (target + rel_dir[len(top):]).strip("/"), True
    return rel_dir, False


def numbered_category(new_dir: str):
    for prefix, category in NUMBERED.items():
        if new_dir == prefix:
            return category
    return None


def parse_number(stem: str):
    m = re.match(r"^(?:adr|spec)?[-_ ]?0*(\d{1,4})[-_ ](.+)$", stem, re.IGNORECASE)
    return (int(m.group(1)), m.group(2)) if m else (None, stem)


def plan_moves(source: str, maps):
    files = []
    for dirpath, dirnames, filenames in os.walk(source):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            files.append(posix(os.path.relpath(os.path.join(dirpath, name), source)))

    moves, unmapped, taken = {}, set(), {}
    pending_numbering = []
    for rel in files:
        rel_dir, name = posixpath.split(rel)
        new_dir, mapped = map_folder(rel_dir, maps)
        if not mapped and rel_dir:
            unmapped.add(rel_dir.split("/", 1)[0])
        category = numbered_category(new_dir)
        if category and name.lower().endswith(".md"):
            if name.lower() == "readme.md":
                moves[rel] = posixpath.join(new_dir, "legacy-index.md")
                continue
            number, rest = parse_number(name[:-3])
            pending_numbering.append((new_dir, number, rest, rel))
            continue
        moves[rel] = posixpath.join(new_dir, name) if new_dir else name

    # Keep a source number when it's free, then fill the rest in order.
    for new_dir, number, rest, rel in sorted(pending_numbering, key=lambda t: (t[0], t[1] is None, t[1] or 0, t[3])):
        used = taken.setdefault(new_dir, set())
        if number is None or number in used or number == 0:
            number = max(used | {0}) + 1
        used.add(number)
        moves[rel] = posixpath.join(new_dir, f"{number:04d}-{slug(rest)}.md")
    return moves, sorted(unmapped)


def split_frontmatter(text: str):
    m = FRONTMATTER.match(text.replace("\r\n", "\n"))
    if not m:
        return [], text.replace("\r\n", "\n")
    lines = m.group(1).split("\n")
    return lines, text.replace("\r\n", "\n")[m.end():]


def fix_frontmatter(text: str, new_rel: str, renames, statuses):
    lines, body = split_frontmatter(text)
    renamed = []
    for line in lines:
        m = re.match(r"^([\w-]+)(\s*:.*)$", line)
        if m and m.group(1) in renames:
            line = renames[m.group(1)] + m.group(2)
        renamed.append(line)
    keys = {re.match(r"^([\w-]+)\s*:", line).group(1) for line in renamed if re.match(r"^([\w-]+)\s*:", line)}
    new_dir = posixpath.dirname(new_rel)
    doc_type = next((t for prefix, t in DOC_TYPES.items() if new_dir == prefix or new_dir.startswith(prefix + "/")), "doc")
    added = []
    number = re.match(r"^(\d{4})-", posixpath.basename(new_rel))

    def add(key, value):
        if key not in keys:
            renamed.append(f"{key}: {value}")
            keys.add(key)
            added.append(key)

    add("doc_type", doc_type)
    if doc_type in ("spec", "adr") and number:
        add("id", number.group(1))
    add("status", statuses.get(doc_type, "active"))
    if doc_type == "adr":
        add("supersedes", "null")
        add("superseded_by", "null")
    add("context_budget", f"~{max(50, round(len(body) / 4, -1)):.0f} tokens")
    return "---\n" + "\n".join(renamed) + "\n---\n" + ("" if body.startswith("\n") else "\n") + body, added


def split_target(target: str):
    raw = target[1:-1] if target.startswith("<") else target
    for sep in ("#", "?"):
        if sep in raw:
            path, rest = raw.split(sep, 1)
            return path, sep + rest
    return raw, ""


def is_relative(target: str) -> bool:
    raw = target[1:-1] if target.startswith("<") else target
    return bool(raw) and not raw.startswith(("#", "/", "mailto:")) and not re.match(r"^[a-zA-Z][\w+.-]*:", raw)


def rewrite_links(text: str, old_rel: str, new_rel: str, moves, source: str, dest: str, outside_dirs):
    """Re-point every relative link; returns (text, links_rewritten)."""
    old_dir, new_dir = posixpath.dirname(old_rel), posixpath.dirname(new_rel)
    count = 0

    def repoint(target: str) -> str:
        nonlocal count
        if not is_relative(target):
            return target
        path, suffix = split_target(target)
        decoded = urllib.parse.unquote(path)
        old_target = posixpath.normpath(posixpath.join(old_dir, decoded)) if decoded else old_rel
        if old_target.startswith("../") or old_target == "..":
            # Into code (or anything) outside the source tree: same file, new relative path.
            absolute = os.path.normpath(os.path.join(source, old_target))
            new_path = posix(os.path.relpath(absolute, os.path.join(dest, new_dir)))
        elif old_target in moves:
            new_path = posixpath.relpath(moves[old_target], new_dir or ".")
        elif any(m.startswith(old_target.rstrip("/") + "/") for m in moves):
            mapped_dir, _ = map_folder(old_target.rstrip("/"), outside_dirs)
            new_path = posixpath.relpath(mapped_dir or ".", new_dir or ".") + ("/" if path.endswith("/") else "")
        else:
            return target  # already broken in the source — left as is, reported by verification
        if not decoded:
            return target
        count += 1
        rebuilt = urllib.parse.quote(new_path, safe="/._-~") + suffix
        return f"<{rebuilt}>" if target.startswith("<") else rebuilt

    out, in_fence = [], False
    for line in text.split("\n"):
        if FENCE.match(line.strip()):
            in_fence = not in_fence
            out.append(line)
            continue
        if not in_fence:
            line = INLINE_LINK.sub(lambda m: m.group(1) + repoint(m.group(2)) + m.group(3), line)
            line = REF_DEF.sub(lambda m: m.group(1) + repoint(m.group(2)) + m.group(3), line)
        out.append(line)
    return "\n".join(out), count


def broken_links(files: dict, root: str):
    """`[(doc, target)]` for relative links that resolve to nothing, given
    the final `{rel: text}` set rooted at `root`.
    """
    present = set(files)
    dirs = {posixpath.dirname(p) for p in present}
    broken = []
    for rel, text in files.items():
        if not rel.endswith(".md"):
            continue
        in_fence = False
        for line in text.split("\n"):
            if FENCE.match(line.strip()):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            targets = [m.group(2) for m in INLINE_LINK.finditer(line)] + [m.group(2) for m in REF_DEF.finditer(line)]
            for target in targets:
                if not is_relative(target):
                    continue
                path, _ = split_target(target)
                if not path:
                    continue
                resolved = posixpath.normpath(posixpath.join(posixpath.dirname(rel), urllib.parse.unquote(path)))
                if resolved in present or resolved.rstrip("/") in dirs:
                    continue
                if resolved.startswith("..") and os.path.exists(os.path.join(root, resolved)):
                    continue
                broken.append((rel, target))
    return broken


def has_required_keys(text: str) -> bool:
    frontmatter = "\n".join(split_frontmatter(text)[0])
    return all(re.search(rf"^{k}:\s*\S", frontmatter, re.MULTILINE) for k in ("doc_type", "status", "context_budget"))


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Import an existing doc base into an ADR 0015 project subtree.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--dest", required=True)
    parser.add_argument("--map", action="append", default=[], help="OLD=NEW folder prefix mapping (repeatable)")
    parser.add_argument("--rename-key", action="append", default=[], help="OLD=NEW frontmatter key rename (repeatable)")
    parser.add_argument("--spec-status", default="implemented", help="status for imported specs lacking one")
    parser.add_argument("--adr-status", default="accepted", help="status for imported ADRs lacking one")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    source = os.path.abspath(args.source)
    dest = os.path.abspath(args.dest)
    if not os.path.isdir(source):
        print(json.dumps({"error": f"source {source} is not a directory"}))
        return 2
    if os.path.isdir(dest) and os.listdir(dest):
        print(json.dumps({"error": f"dest {dest} is not empty — refusing to overwrite anything"}))
        return 2
    if os.path.commonpath([source, dest]) in (source, dest):
        print(json.dumps({"error": "source and dest must not contain one another"}))
        return 2

    maps = dict(m.split("=", 1) for m in args.map)
    maps = {posix(k).strip("/"): posix(v).strip("/") for k, v in maps.items()}
    renames = dict(r.split("=", 1) for r in args.rename_key)
    statuses = {"spec": args.spec_status, "adr": args.adr_status, "architecture": "active"}

    before = tree_hash(source)
    moves, unmapped = plan_moves(source, maps)
    outputs, link_count, added_keys = {}, 0, {}
    for old_rel, new_rel in sorted(moves.items()):
        with open(os.path.join(source, old_rel), "rb") as f:
            data = f.read()
        if old_rel.lower().endswith(".md"):
            text = data.decode("utf-8", "replace")
            text, added = fix_frontmatter(text, new_rel, renames, statuses)
            text, n = rewrite_links(text, old_rel, new_rel, moves, source, dest, maps)
            link_count += n
            if added:
                added_keys[new_rel] = added
            outputs[new_rel] = text
        else:
            outputs[new_rel] = data

    texts = {rel: v for rel, v in outputs.items() if isinstance(v, str)}
    after_broken = broken_links({**{k: "" for k in outputs}, **texts}, dest)
    with_source = {rel: open(os.path.join(source, rel), encoding="utf-8", errors="replace").read()
                   for rel in moves if rel.lower().endswith(".md")}
    source_broken = broken_links({**{k: "" for k in moves}, **with_source}, source)
    missing_keys = [rel for rel, text in texts.items() if rel.endswith(".md") and not has_required_keys(text)]

    if args.apply:
        for rel, content in outputs.items():
            target = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if isinstance(content, str):
                with open(target, "w", encoding="utf-8", newline="\n") as f:
                    f.write(content)
            else:
                with open(target, "wb") as f:
                    f.write(content)

    report = {
        "applied": args.apply,
        "source": posix(source),
        "dest": posix(dest),
        "files": len(outputs),
        "moves": {old: new for old, new in sorted(moves.items()) if old != new},
        "unmapped_top_level_folders": unmapped,
        "links_rewritten": link_count,
        "frontmatter_keys_added": added_keys,
        "broken_links_introduced": [f"{doc}: {t}" for doc, t in after_broken if (doc, t) not in set(source_broken)],
        "broken_links_preexisting_in_source": len(source_broken),
        "docs_missing_required_keys": missing_keys,
        "source_unchanged": tree_hash(source) == before,
    }
    print(json.dumps(report, indent=2))
    return 0 if not report["broken_links_introduced"] and not missing_keys and report["source_unchanged"] else 1


if __name__ == "__main__":
    sys.exit(main())
