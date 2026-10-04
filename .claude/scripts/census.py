"""Census engine — keeps architecture docs honest against the code (ADR
0019, spec 0002 FR-01..FR-04, FR-08).

Commands (all print JSON; `--project-dir` defaults to CLAUDE_PROJECT_DIR):

    census.py status                    freshness of the integration ref, ledger state
    census.py run [--write]             inventory + drift + doc mentions + probes
    census.py commits                   commits on the ref since the watermark, with pending matches
    census.py ledger init [--watermark SHA]
    census.py ledger add-pending --spec ID --task N --files F... [--docs D...] [--note TEXT]
    census.py ledger document SHA... (--docs D... | --skip REASON) [--pending ID]
    census.py ledger advance            watermark → ref HEAD, only when every commit is handled
    census.py --all run [--write]       every registered project with census enabled

What it reads:

- **Code**: only the project's integration ref (`main_integration_branch`
  from its config, else `origin/HEAD`), preferring `origin/<branch>`, via
  read-only git (`ls-tree`, `cat-file`, `grep`, `log`, `diff-tree`).
  Never the working tree, so a feature branch checked out locally can't
  show up as drift (AC-01). Never `fetch`: `status` reports how old the
  last fetch is, and the caller asks the human (NFR-02).
- **Docs**: the project's docs root (`<subtree>` in modes B/C, `docs/` in
  mode A), for mentions and for inline probes.

What it writes, and only there: `<docs root>/architecture/census/`
(`census.tsv`, `mentions.tsv`, `ledger.json`). Nothing in the code repo.

Configuration (`census` in the project's config):

    "census": {"enabled": true, "extractor": "dotnet-layered",
               "include": ["src/*"], "exclude": ["*/bin/*", "*/obj/*"],
               "docs": ["architecture/*.md"], "fetch_max_age_hours": 24}

`extractor: none` makes the inventory empty; everything else (ledger,
probes, update-docs) still works (AC-03). Extractors live in
`census_extractors/<name>.py` (dashes become underscores) and expose
`extract(ref, settings) -> [(kind, identifier, "path:line"), ...]`. They
must be deterministic (NFR-03): consistently wrong beats inconsistently
right, because the diff is the product.

Probes are inline HTML comments in any scanned doc, next to the rule or
finding they back (FR-06, FR-08):

    <!-- census-probe id=R-01 kind=rule expect=absent paths="src/*.Domain/**/*.cs" pattern="using [A-Za-z.]*\\.Infrastructure" -->
    <!-- census-probe id=F-03 kind=finding pattern="Thread\\.Sleep\\(" paths="src/**/*.cs" -->

`paths` are git glob pathspecs, comma-separated: `*` stays inside one
folder, `**` crosses folders. `pattern` is an extended regex.

A `rule` defaults to `expect=absent` (matches = the code breaks the rule:
drift); `expect=present` checks a rule the code must keep following. A
`finding` defaults to `expect=present` (the defect is still alive); once
it goes silent, the finding should be retired or rewritten.
"""
import argparse
import datetime
import fnmatch
import importlib
import json
import os
import re
import subprocess
import sys

FRAMEWORK_HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(FRAMEWORK_HOME, "hooks"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _project_paths import (  # noqa: E402
    describe,
    load_project_config,
    main_integration_branch,
    normalize,
    resolve_docs_root,
)

CENSUS_DIRNAME = os.path.join("architecture", "census")
DEFAULT_DOC_GLOBS = ["architecture/*.md"]
PROBE = re.compile(r"<!--\s*census-probe\s+(.*?)-->", re.DOTALL)
PROBE_ATTR = re.compile(r'(\w+)=("([^"]*)"|\S+)')


class CensusError(Exception):
    pass


# ---------------------------------------------------------------- git, read-only


class GitRef:
    """Read-only view of one ref. Every method shells out to a git command
    that cannot modify the repository.
    """

    def __init__(self, repo: str, ref: str):
        self.repo, self.ref = repo, ref
        self._files = None

    def _git(self, *args, input_bytes=None) -> bytes:
        result = subprocess.run(["git", *args], cwd=self.repo, input=input_bytes, capture_output=True, timeout=300)
        if result.returncode not in (0, 1):  # grep exits 1 on "no match"
            raise CensusError(f"git {' '.join(args[:3])} failed: {result.stderr.decode('utf-8', 'replace').strip()}")
        return result.stdout

    def head(self) -> str:
        return self._git("rev-parse", self.ref).decode().strip()

    def files(self, include=None, exclude=None):
        if self._files is None:
            out = self._git("ls-tree", "-r", "--name-only", "-z", self.ref)
            self._files = sorted(p for p in out.decode("utf-8").split("\0") if p)
        selected = self._files
        if include:
            selected = [p for p in selected if any(fnmatch.fnmatch(p, g) for g in include)]
        if exclude:
            selected = [p for p in selected if not any(fnmatch.fnmatch(p, g) for g in exclude)]
        return selected

    def read_many(self, paths):
        """`{path: text}` through one `git cat-file --batch` process."""
        if not paths:
            return {}
        request = "".join(f"{self.ref}:{p}\n" for p in paths).encode("utf-8")
        out = self._git("cat-file", "--batch", input_bytes=request)
        contents, pos = {}, 0
        for path in paths:
            newline = out.index(b"\n", pos)
            header = out[pos:newline].decode("utf-8", "replace").split()
            pos = newline + 1
            if len(header) < 3 or header[1] == "missing":
                continue
            size = int(header[2])
            contents[path] = out[pos:pos + size].decode("utf-8", "replace").replace("\r\n", "\n")
            pos += size + 1
        return contents

    def grep(self, pattern: str, globs):
        """`[(path, line, text)]` for an extended regex at the ref."""
        specs = [f":(glob){g}" for g in (globs or ["**"])]
        out = self._git("grep", "-z", "-n", "-I", "-E", "-e", pattern, self.ref, "--", *specs)
        hits = []
        for record in out.decode("utf-8", "replace").split("\n"):
            parts = record.split("\0")
            if len(parts) < 3:
                continue
            path = parts[0][len(self.ref) + 1:] if parts[0].startswith(self.ref + ":") else parts[0]
            hits.append((path, int(parts[1]), parts[2].strip()))
        return hits

    def commits_since(self, watermark):
        rng = f"{watermark}..{self.ref}" if watermark else self.ref
        out = self._git("log", "--reverse", "--format=%H%x09%s", rng).decode("utf-8", "replace")
        commits = []
        for line in out.splitlines():
            sha, _, subject = line.partition("\t")
            files = self._git("diff-tree", "--no-commit-id", "--name-only", "-r", "--root", sha).decode("utf-8", "replace").split()
            commits.append({"commit": sha, "subject": subject, "files": sorted(files)})
        return commits

    def is_ancestor(self, sha: str) -> bool:
        return subprocess.run(["git", "merge-base", "--is-ancestor", sha, self.ref], cwd=self.repo,
                              capture_output=True, timeout=60).returncode == 0


def resolve_ref(project: str):
    branch = main_integration_branch(project)
    if not branch:
        raise CensusError("no integration branch: set main_integration_branch in the project config")
    for candidate in (f"origin/{branch}", branch):
        if subprocess.run(["git", "rev-parse", "--verify", "--quiet", candidate + "^{commit}"], cwd=project,
                          capture_output=True, timeout=30).returncode == 0:
            return candidate
    raise CensusError(f"integration branch {branch!r} not found locally (neither origin/{branch} nor {branch})")


def fetch_age_hours(project: str):
    try:
        path = subprocess.run(["git", "rev-parse", "--git-path", "FETCH_HEAD"], cwd=project,
                              capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    full = path if os.path.isabs(path) else os.path.join(project, path)
    if not os.path.isfile(full):
        return None
    return round((datetime.datetime.now().timestamp() - os.path.getmtime(full)) / 3600, 1)


# ---------------------------------------------------------------- project context


class Project:
    def __init__(self, project_dir: str):
        self.dir = normalize(os.path.abspath(project_dir))
        config = load_project_config(self.dir)
        self.settings = config.get("census") if isinstance(config.get("census"), dict) else {}
        self.docs_root = resolve_docs_root(self.dir)
        self.census_dir = os.path.join(self.docs_root, CENSUS_DIRNAME)

    @property
    def extractor_name(self) -> str:
        return str(self.settings.get("extractor") or "none")

    def ref(self) -> GitRef:
        return GitRef(self.dir, resolve_ref(self.dir))

    def path(self, name: str) -> str:
        return os.path.join(self.census_dir, name)

    def docs(self):
        """Scanned docs as `{relative path: text}`."""
        globs = self.settings.get("docs") or DEFAULT_DOC_GLOBS
        found = {}
        for dirpath, dirnames, filenames in os.walk(self.docs_root):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
            for name in sorted(filenames):
                if not name.endswith(".md"):
                    continue
                full = os.path.join(dirpath, name)
                rel = normalize(os.path.relpath(full, self.docs_root))
                if rel.startswith("architecture/census/") or not any(fnmatch.fnmatch(rel, g) for g in globs):
                    continue
                with open(full, encoding="utf-8") as f:
                    found[rel] = f.read()
        return found


def load_extractor(name: str):
    if name == "none":
        return None
    module = name.replace("-", "_")
    try:
        return importlib.import_module(f"census_extractors.{module}")
    except ImportError as exc:
        raise CensusError(f"unknown census extractor {name!r} (no census_extractors/{module}.py)") from exc


# ---------------------------------------------------------------- inventory, drift, mentions, probes


def read_tsv(path: str):
    rows = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("#") or not line.strip():
                    continue
                rows.append(line.rstrip("\n").split("\t"))
    except FileNotFoundError:
        return None
    return rows


def write_tsv(path: str, header: str, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(header + "\n")
        for row in rows:
            f.write("\t".join(row) + "\n")


def mention_needle(kind: str, identifier: str) -> str:
    """The text a doc would actually contain for an identifier."""
    if kind == "handler":
        return identifier.rsplit(".", 1)[-1]
    if kind == "endpoint":
        return identifier.split(" ", 1)[-1]
    return identifier


def mentions(inventory, docs):
    cited = {}
    for kind, identifier, _ in inventory:
        needle = mention_needle(kind, identifier)
        if not needle:
            continue
        pattern = re.compile(r"(?<![\w./:-])" + re.escape(needle) + r"(?![\w-])")
        where = sorted(rel for rel, text in docs.items() if pattern.search(text))
        if where:
            cited[(kind, identifier)] = where
    return cited


def parse_probes(docs):
    probes = []
    for rel, text in sorted(docs.items()):
        for match in PROBE.finditer(text):
            attrs = {m.group(1): (m.group(3) if m.group(3) is not None else m.group(2)) for m in PROBE_ATTR.finditer(match.group(1))}
            if not attrs.get("id") or not attrs.get("pattern"):
                continue
            kind = attrs.get("kind", "finding")
            expect = attrs.get("expect", "absent" if kind == "rule" else "present")
            globs = [g.strip() for g in attrs.get("paths", "**").split(",") if g.strip()]
            probes.append({"id": attrs["id"], "kind": kind, "expect": expect, "pattern": attrs["pattern"],
                           "paths": globs, "doc": rel})
    return probes


def run_probes(ref: GitRef, probes):
    results = []
    for probe in probes:
        hits = ref.grep(probe["pattern"], probe["paths"])
        present = bool(hits)
        if probe["kind"] == "finding":
            state = "alive" if present else "silent"
        elif probe["expect"] == "absent":
            state = "violated" if present else "holds"
        else:
            state = "holds" if present else "violated"
        results.append(dict(probe, matches=len(hits), sample=[f"{p}:{n}" for p, n, _ in hits[:5]], state=state))
    return results


def run_census(project: Project, write: bool):
    ref = project.ref()
    extractor = load_extractor(project.extractor_name)
    inventory = []
    if extractor:
        rows = extractor.extract(ref, project.settings)
        inventory = sorted({(k, i): (k, i, loc) for k, i, loc in sorted(rows)}.values())

    previous = read_tsv(project.path("census.tsv"))
    previous_ids = {(r[0], r[1]) for r in previous or [] if len(r) >= 2}
    current_ids = {(k, i) for k, i, _ in inventory}
    old_mentions = {(r[0], r[1]): r[2].split(",") for r in read_tsv(project.path("mentions.tsv")) or [] if len(r) >= 3}

    docs = project.docs()
    cited = mentions(inventory, docs)
    probes = run_probes(ref, parse_probes(docs))

    removed = sorted(previous_ids - current_ids) if previous is not None else []
    report = {
        "project": project.dir,
        "ref": ref.ref,
        "commit": ref.head(),
        "extractor": project.extractor_name,
        "baseline": previous is not None,
        "inventory_size": len(inventory),
        "added": [f"{k}\t{i}" for k, i in sorted(current_ids - previous_ids)] if previous is not None else [],
        "removed": [{"item": f"{k}\t{i}", "still_cited_by": old_mentions.get((k, i), [])} for k, i in removed],
        "undocumented": sum(1 for key in current_ids if key not in cited),
        "probes": probes,
        "drift": bool(removed or (previous is not None and current_ids - previous_ids)
                      or any(p["state"] == "violated" for p in probes)),
        "written": False,
    }
    if write:
        write_tsv(project.path("census.tsv"), f"# kind\tidentifier\tlocation  (census of {ref.ref} @ {report['commit'][:12]})",
                  [list(row) for row in inventory])
        write_tsv(project.path("mentions.tsv"), "# kind\tidentifier\tdocs citing it",
                  [[k, i, ",".join(where)] for (k, i), where in sorted(cited.items())])
        report["written"] = True
    return report


# ---------------------------------------------------------------- ledger


def load_ledger(project: Project):
    try:
        with open(project.path("ledger.json"), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def save_ledger(project: Project, ledger: dict):
    os.makedirs(project.census_dir, exist_ok=True)
    with open(project.path("ledger.json"), "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(ledger, indent=2) + "\n")


def require_ledger(project: Project):
    ledger = load_ledger(project)
    if ledger is None:
        raise CensusError("no ledger yet — run `census.py ledger init` once to set the starting watermark")
    return ledger


def ledger_status(project: Project, ref: GitRef):
    ledger = require_ledger(project)
    commits = ref.commits_since(ledger.get("watermark"))
    documented = {d["commit"] for d in ledger.get("documented", [])}
    out = []
    for commit in commits:
        entry = dict(commit, handled=commit["commit"] in documented)
        if not entry["handled"]:
            touched = set(commit["files"])
            entry["pending_matches"] = [p["id"] for p in ledger.get("pending", []) if touched & set(p.get("files", []))]
        out.append(entry)
    return ledger, out


def cmd_ledger(project: Project, args):
    today = datetime.date.today().isoformat()
    if args.ledger_cmd == "init":
        if load_ledger(project) is not None:
            raise CensusError("ledger already exists — refusing to reset its watermark")
        ref = project.ref()
        ledger = {"ref": ref.ref, "watermark": args.watermark or ref.head(), "pending": [], "documented": []}
        save_ledger(project, ledger)
        return {"initialized": True, "watermark": ledger["watermark"]}

    ledger = require_ledger(project)
    if args.ledger_cmd == "add-pending":
        # /implement and /quick write this; it never touches the watermark (FR-04).
        next_id = 1 + max([int(p["id"].split("-")[1]) for p in ledger["pending"]] + [0])
        entry = {"id": f"p-{next_id:04d}", "created": today, "spec": args.spec, "task": args.task,
                 "files": sorted({normalize(f) for f in args.files}), "docs": sorted(set(args.docs or [])),
                 "note": args.note or ""}
        ledger["pending"].append(entry)
        save_ledger(project, ledger)
        return {"added": entry}

    if args.ledger_cmd == "document":
        if not args.docs and not args.skip:
            raise CensusError("document needs --docs (what was updated) or --skip REASON (nothing to document)")
        ref = project.ref()
        known = {d["commit"] for d in ledger["documented"]}
        added = []
        for sha in args.commits:
            full = ref._git("rev-parse", sha).decode().strip()
            if not ref.is_ancestor(full):
                raise CensusError(f"{sha} is not on {ref.ref}")
            if full in known:
                continue
            added.append({"commit": full, "documented": today, "docs": sorted(set(args.docs or [])),
                          "pending_id": args.pending, "skipped": bool(args.skip), "reason": args.skip or ""})
        ledger["documented"].extend(added)
        if args.pending:
            ledger["pending"] = [p for p in ledger["pending"] if p["id"] != args.pending]
        save_ledger(project, ledger)
        return {"documented": [a["commit"] for a in added]}

    if args.ledger_cmd == "advance":
        # AC-04: either the watermark reaches the ref's HEAD, or the
        # unhandled commits are listed and it stays put. Never both.
        ref = project.ref()
        ledger, commits = ledger_status(project, ref)
        unhandled = [c for c in commits if not c["handled"]]
        if unhandled:
            return {"advanced": False, "watermark": ledger["watermark"],
                    "unhandled": [{"commit": c["commit"], "subject": c["subject"]} for c in unhandled]}
        head = ref.head()
        handled = {c["commit"] for c in commits}
        ledger["watermark"] = head
        ledger["documented"] = [d for d in ledger["documented"] if d["commit"] not in handled]
        save_ledger(project, ledger)
        return {"advanced": True, "watermark": head, "unhandled": []}
    raise CensusError(f"unknown ledger command {args.ledger_cmd}")


# ---------------------------------------------------------------- CLI


def projects_for(args):
    if not args.all:
        return [args.project_dir or os.environ.get("CLAUDE_PROJECT_DIR", ".")]
    info = describe(args.project_dir or os.environ.get("CLAUDE_PROJECT_DIR", "."))
    try:
        with open(info["registry"], encoding="utf-8") as f:
            registry = json.load(f)
    except (OSError, TypeError, ValueError) as exc:
        raise CensusError(f"--all needs a readable registry ({info.get('registry')})") from exc
    repos = []
    for repo in sorted(k for k in registry if k != "projects_root"):
        census = load_project_config(repo).get("census") or {}
        if isinstance(census, dict) and census.get("enabled"):
            repos.append(repo)
    return repos


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Census engine (ADR 0019).")
    parser.add_argument("--project-dir")
    parser.add_argument("--all", action="store_true", help="every registered project with census enabled")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    run = sub.add_parser("run")
    run.add_argument("--write", action="store_true")
    sub.add_parser("commits")
    ledger = sub.add_parser("ledger")
    lsub = ledger.add_subparsers(dest="ledger_cmd", required=True)
    init = lsub.add_parser("init")
    init.add_argument("--watermark")
    pending = lsub.add_parser("add-pending")
    pending.add_argument("--spec", required=True)
    pending.add_argument("--task", required=True)
    pending.add_argument("--files", nargs="+", required=True)
    pending.add_argument("--docs", nargs="*")
    pending.add_argument("--note")
    document = lsub.add_parser("document")
    document.add_argument("commits", nargs="+")
    document.add_argument("--docs", nargs="*")
    document.add_argument("--skip")
    document.add_argument("--pending")
    lsub.add_parser("advance")
    args = parser.parse_args(argv)

    results, status = [], 0
    try:
        for project_dir in projects_for(args):
            project = Project(project_dir)
            if args.cmd == "status":
                ref = project.ref()
                age = fetch_age_hours(project.dir)
                limit = project.settings.get("fetch_max_age_hours", 24)
                ledger = load_ledger(project)
                result = {"project": project.dir, "ref": ref.ref, "commit": ref.head(), "fetch_age_hours": age,
                          "fresh": age is not None and age <= limit, "extractor": project.extractor_name,
                          "enabled": bool(project.settings.get("enabled")),
                          "watermark": ledger.get("watermark") if ledger else None,
                          "pending": len(ledger.get("pending", [])) if ledger else 0}
            elif args.cmd == "run":
                result = run_census(project, args.write)
            elif args.cmd == "commits":
                ledger, commits = ledger_status(project, project.ref())
                result = {"project": project.dir, "watermark": ledger["watermark"], "commits": commits,
                          "pending": ledger.get("pending", [])}
            else:
                result = cmd_ledger(project, args)
                if args.ledger_cmd == "advance" and not result["advanced"]:
                    status = 1
            results.append(result)
    except CensusError as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    print(json.dumps(results if args.all else results[0], indent=2))
    return status


if __name__ == "__main__":
    sys.exit(main())
