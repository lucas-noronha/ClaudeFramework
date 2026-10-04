"""Register one or several existing repos with a multi-project install
(mode C, or mode B's AI-repo): the deterministic half of the
`project-registration` skill's step 3 (framework ADR 0014, framework ADR 0017; framework spec 0001
FR-06, FR-09, FR-11).

    python register_project.py --repo PATH --name NAME --build-test-cmd CMD [--apply]
    python register_project.py --plan plan.json [--apply]

Every location — registry, shared docs root, projects root, `CLAUDE.md`
template — comes from `_project_paths.describe()`, i.e. from the install's
`framework.json` when there is one. Nothing is inferred from folder
shape (FR-09).

Per project it creates `<projects_root>/<name>/` with an empty
`product/specs/`, the shared architecture templates (unfilled),
`decisions/0000-adr-template.md`, `project-config.json` and `CLAUDE.md`
(every value this script knows filled in; the rest reported for the
agent to resolve), then adds the routing entry. It refuses — before
writing anything — on a reserved or unsafe name, an existing subtree
(unless `--existing-subtree same`, which writes the routing entry only),
an unparseable registry, or a repo that is already registered.
`--subtree PATH` routes a repo to an existing folder anywhere instead
(routing entry only) — how the framework repository points its own
pipeline at `evolution/`.

Bulk mode (FR-11) takes the shared answers once, in a plan file:

    {"shared": {"build_test_cmd": "optional"},
     "projects": [{"repo": "...", "name": "optional", "build_test_cmd": "optional"}]}

No language is asked for or written: the subtree `project-config.json`
never carries one (framework ADR 0023 section 1); `CLAUDE.md`'s
`{{LANGUAGE}}` is filled from the setup language. The old
`--canonical-lang`, `--stakeholder-lang`, `--stakeholder-lang-code` flags and
`canonical_lang`/`stakeholder_lang`/`stakeholder_lang_code` plan keys are still
accepted but ignored, with a warning on stderr.

Dry run by default. Prints a JSON report.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import sys

FRAMEWORK_HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(FRAMEWORK_HOME, "hooks"))
from _project_paths import describe, detect_main_branch, normalize  # noqa: E402

RESERVED_NAMES = {"workflow", "product", "architecture", "decisions", "glossary"}
NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")
RETIRED_LANGUAGE_KEYS = ("canonical_lang", "stakeholder_lang", "stakeholder_lang_code")


def detect_build_test_cmd(repo: str):
    """Same detection Domain 1 uses: .sln/.csproj → dotnet test; a
    package.json `test` script → npm test; both → chained.
    """
    commands = []
    try:
        names = os.listdir(repo)
    except OSError:
        return None
    if any(n.endswith((".sln", ".csproj")) for n in names):
        commands.append("dotnet test")
    package = os.path.join(repo, "package.json")
    if os.path.isfile(package):
        try:
            with open(package, encoding="utf-8") as f:
                if (json.load(f).get("scripts") or {}).get("test"):
                    commands.append("npm test")
        except (OSError, ValueError):
            pass
    return " && ".join(commands) if commands else None


def plan_project(spec: dict, shared: dict, info: dict, existing: str, today: str):
    """Everything to write for one project, or an error string."""
    repo = normalize(os.path.abspath(spec["repo"]))
    if not os.path.isdir(repo):
        return None, f"{repo}: not a directory"
    name = spec.get("name") or os.path.basename(repo)
    if name.lower() in RESERVED_NAMES:
        return None, f"{repo}: name {name!r} collides with the shared root's own `{name.lower()}` folder (framework ADR 0015) — pick another"
    if not NAME_PATTERN.match(name):
        return None, f"{repo}: name {name!r} isn't a safe folder name"

    repo_info = describe(repo)
    if repo_info["registered"]:
        return None, f"{repo}: already registered → {repo_info['subtree']}"

    projects_root = info["projects_root"]
    if spec.get("subtree"):
        subtree = normalize(os.path.abspath(spec["subtree"]))
        if not os.path.isdir(subtree):
            return None, f"{repo}: --subtree {subtree} is not an existing folder"
        return {
            "repo": repo, "name": name, "subtree": subtree, "routing_only": True,
            "build_test_cmd": None, "main_integration_branch": None,
            "writes": {}, "claude_md_placeholders_left": [],
        }, None
    subtree = normalize(os.path.join(projects_root, name))
    routing_only = False
    if os.path.exists(subtree):
        if existing != "same":
            return None, (f"{repo}: {subtree} already exists. If it is this same project, re-run with "
                          "--existing-subtree same (routing entry only); otherwise choose another --name")
        routing_only = True

    def value(key):
        own = spec.get(key)
        return own if own is not None else shared.get(key)

    build = value("build_test_cmd")
    if build is None:
        build = detect_build_test_cmd(repo)
    if build is None and not routing_only:
        return None, f"{repo}: no build/test command detected — pass one (an empty string records 'no automated tests')"
    branch = value("main_integration_branch") or detect_main_branch(repo)

    writes = {}
    remaining = []
    if not routing_only:
        shared_root = info["shared_docs_root"]
        config = {
            "build_test_cmd": build,
            "main_integration_branch": branch,
            "review_policy": "per-task",
            "census": {"enabled": False, "extractor": value("census_extractor") or "none"},
        }
        writes[f"{subtree}/project-config.json"] = json.dumps(config, indent=2) + "\n"
        writes[f"{subtree}/product/specs/"] = None
        for template in ("module-structure.md.template", "frontend.md.template"):
            src = os.path.join(shared_root, "architecture", template)
            if os.path.isfile(src):
                writes[f"{subtree}/architecture/{template}"] = ("copy", src)
        adr_template = os.path.join(shared_root, "decisions", "0000-adr-template.md")
        if os.path.isfile(adr_template):
            writes[f"{subtree}/decisions/0000-adr-template.md"] = ("copy", adr_template)
        template_path = info.get("claude_md_template")
        if template_path and os.path.isfile(template_path):
            with open(template_path, encoding="utf-8") as f:
                text = f.read()
            known = {
                "PROJECT_NAME": name, "LANGUAGE": (info.get("language") or {}).get("name") or "English",
                "BUILD_TEST_CMD": build or "(none — no automated tests)", "DATE": today,
            }
            if branch:
                known["MAIN_INTEGRATION_BRANCH"] = branch
            text = PLACEHOLDER.sub(lambda m: known.get(m.group(1), m.group(0)), text)
            remaining = sorted(set(PLACEHOLDER.findall(text)))
            writes[f"{subtree}/CLAUDE.md"] = text
        else:
            return None, f"{repo}: no CLAUDE.md template found ({template_path!r}) — ask the user for its path"

    return {
        "repo": repo, "name": name, "subtree": subtree, "routing_only": routing_only,
        "build_test_cmd": build, "main_integration_branch": branch,
        "writes": writes, "claude_md_placeholders_left": remaining,
    }, None


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Register existing repos with a multi-project install.")
    parser.add_argument("--repo")
    parser.add_argument("--name")
    parser.add_argument("--build-test-cmd")
    for flag in ("--canonical-lang", "--stakeholder-lang", "--stakeholder-lang-code"):
        parser.add_argument(flag, help=argparse.SUPPRESS)  # retired (ADR 0023): accepted, ignored, warned about
    parser.add_argument("--main-branch")
    parser.add_argument("--census-extractor")
    parser.add_argument("--plan", help="bulk plan file (see module docstring)")
    parser.add_argument("--existing-subtree", choices=["abort", "same"], default="abort")
    parser.add_argument("--subtree", help="route --repo to this existing folder (routing entry only)")
    parser.add_argument("--today", help=argparse.SUPPRESS)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    today = args.today or datetime.date.today().isoformat()

    ignored = [flag for flag, given in (("--canonical-lang", args.canonical_lang), ("--stakeholder-lang", args.stakeholder_lang),
                                        ("--stakeholder-lang-code", args.stakeholder_lang_code)) if given is not None]
    if args.plan:
        with open(args.plan, encoding="utf-8") as f:
            plan = json.load(f)
        shared, projects = plan.get("shared", {}), plan.get("projects", [])
        ignored += sorted({key for entry in [shared, *projects] for key in RETIRED_LANGUAGE_KEYS if key in entry})
    elif args.repo:
        shared = {}
        projects = [{
            "repo": args.repo, "name": args.name, "subtree": args.subtree, "build_test_cmd": args.build_test_cmd,
            "main_integration_branch": args.main_branch,
            "census_extractor": args.census_extractor,
        }]
    else:
        parser.error("pass --repo or --plan")

    if ignored:
        print(f"warning: {', '.join(ignored)} ignored — the language is the setup language, never a per-project value "
              "(framework ADR 0023); the subtree project-config.json carries none", file=sys.stderr)

    info = describe(projects[0]["repo"] if projects else ".")
    if not info.get("projects_root") or not info.get("registry"):
        print(json.dumps({"error": "no projects root or registry configured — run /setup-framework (Domain 6) first"}))
        return 2
    registry_path = info["registry"]
    try:
        with open(registry_path, encoding="utf-8") as f:
            registry = json.load(f)
    except FileNotFoundError:
        registry = {}
    except ValueError:
        print(json.dumps({"error": f"{registry_path} doesn't parse — refusing to rewrite it"}))
        return 2

    planned, errors, names = [], [], set()
    for spec in projects:
        result, error = plan_project(spec, shared, info, args.existing_subtree, today)
        if error:
            errors.append(error)
        elif result["name"].lower() in names:
            errors.append(f"{result['repo']}: name {result['name']!r} used twice in this plan")
        else:
            names.add(result["name"].lower())
            planned.append(result)

    report = {
        "applied": bool(args.apply and not errors),
        "registry": registry_path,
        "projects": [{k: v for k, v in p.items() if k != "writes"} | {"creates": sorted(p["writes"])} for p in planned],
        "errors": errors,
    }
    if errors or not args.apply:
        print(json.dumps(report, indent=2))
        return 1 if errors else 0

    for project in planned:
        for dest, content in project["writes"].items():
            if dest.endswith("/"):
                os.makedirs(dest, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if isinstance(content, tuple):
                shutil.copyfile(content[1], dest)
            else:
                with open(dest, "w", encoding="utf-8", newline="\n") as f:
                    f.write(content)
        registry[project["repo"]] = project["subtree"]

    os.makedirs(os.path.dirname(registry_path), exist_ok=True)
    with open(registry_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(registry, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
