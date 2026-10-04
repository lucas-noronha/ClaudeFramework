"""Remove a user-level install of this framework — exactly what its
`manifest.json` says it created, nothing else (framework ADR 0017, framework spec 0001 FR-02).

    python <namespace>/scripts/uninstall.py                    # dry run
    python <namespace>/scripts/uninstall.py --apply            # remove
    python <namespace>/scripts/uninstall.py --apply --restore-retired

- **Files**: each file the install wrote is removed if it is still
  byte-identical to what was written. A file edited since (an amended
  `constitution.md`, a hand-patched agent) is kept and reported, unless
  `--force` is given.
- **settings.json**: the hook groups and permissions the install added
  are removed. When the result equals the file as it was before the
  first install, the saved original is written back **byte for byte**
  (AC-03). When something else changed since, only this install's
  entries are removed and the difference is reported. A settings file
  the install created from nothing is deleted once empty.
- **Never touched**: the project subtrees under the projects root (your
  specs, ADRs and architecture docs), and the registry once it routes any
  project. Both are reported so you can delete them by hand if you mean
  to.
- **Retired files**: anything moved aside at install time (`--retire`)
  is listed with its backup path; `--restore-retired` moves it back.

Stdlib only; locates the install from its own path, so it works after
the framework repository is gone.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys

NAMESPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def posix(path: str) -> str:
    return path.replace("\\", "/").rstrip("/")


def sha256_file(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def strip_settings(settings: dict, record: dict) -> list:
    """Remove this install's additions in place; return what couldn't be
    found (changed or removed by hand since install).
    """
    missing = []
    hooks = settings.get("hooks") if isinstance(settings.get("hooks"), dict) else {}
    for item in record.get("added_groups", []):
        groups = hooks.get(item["event"], [])
        for index in range(len(groups) - 1, -1, -1):
            if groups[index] == item["group"]:
                del groups[index]
                break
        else:
            missing.append(f"hooks.{item['event']}: {json.dumps(item['group'])[:100]}")
    allow = (settings.get("permissions") or {}).get("allow")
    for rule in record.get("added_permissions", []):
        if isinstance(allow, list) and rule in allow:
            allow.remove(rule)
        else:
            missing.append(f"permissions.allow: {rule}")
    for key in sorted(record.get("created_keys", []), key=lambda k: -k.count(".")):
        parts = key.split(".")
        parent = settings
        for part in parts[:-1]:
            parent = parent.get(part, {}) if isinstance(parent, dict) else {}
        if isinstance(parent, dict) and parts[-1] in parent and parent[parts[-1]] in ([], {}):
            del parent[parts[-1]]
    return missing


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Uninstall the user-level framework install.")
    parser.add_argument("--apply", action="store_true", help="remove; without it this is a dry run")
    parser.add_argument("--force", action="store_true", help="also remove installed files edited since install")
    parser.add_argument("--restore-retired", action="store_true", help="move files retired at install back")
    parser.add_argument("--namespace", default=NAMESPACE, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    namespace = posix(os.path.abspath(args.namespace))
    manifest_path = f"{namespace}/manifest.json"
    try:
        manifest = load_json(manifest_path)
    except (OSError, ValueError):
        print(f"No readable manifest at {manifest_path} — nothing this tool can safely remove.", file=sys.stderr)
        return 2

    remove, keep = [], []
    for path, meta in manifest.get("files", {}).items():
        if not os.path.isfile(path):
            continue
        unchanged = meta.get("kind") == "generated" or sha256_file(path) == meta.get("sha256")
        if unchanged or args.force:
            remove.append(path)
        else:
            keep.append(path)

    # settings.json
    settings_record = manifest.get("settings", {})
    settings_path = settings_record.get("path")
    settings_plan, settings_note = None, "untouched"
    if settings_path and os.path.isfile(settings_path):
        try:
            settings = load_json(settings_path)
        except ValueError:
            settings = None
            settings_note = "doesn't parse — left alone, remove the framework's entries by hand"
        if settings is not None:
            missing = strip_settings(settings, settings_record)
            backup = settings_record.get("backup")
            if settings_record.get("preexisted") and backup and os.path.isfile(backup) and load_json(backup) == settings:
                settings_plan, settings_note = ("restore", backup), "restored byte-for-byte from the pre-install copy"
            elif not settings_record.get("preexisted") and settings in ({}, {"hooks": {}}, {"permissions": {}}):
                settings_plan, settings_note = ("delete", None), "deleted (the install created it, nothing else is left)"
            else:
                settings_plan = ("write", settings)
                settings_note = "framework entries removed; NOT byte-identical to the original (it changed since install)"
            if missing:
                settings_note += f"; {len(missing)} entr{'y' if len(missing) == 1 else 'ies'} already gone: " + "; ".join(missing)

    registry = manifest.get("registry", {})
    registry_path = registry.get("path")
    routed = {}
    if registry_path and os.path.isfile(registry_path):
        try:
            routed = {k: v for k, v in load_json(registry_path).items() if k != "projects_root"}
        except ValueError:
            routed = {"(unparseable)": ""}
    remove_registry = bool(registry.get("created")) and registry_path and os.path.isfile(registry_path) and not routed

    print(f"{'Uninstalling' if args.apply else 'Dry run'}: {manifest.get('prefix')} from {manifest.get('config_dir')}")
    print(f"  remove {len(remove)} file(s)" + (f", keep {len(keep)} edited since install" if keep else ""))
    for path in keep:
        print(f"    keep (edited): {path}")
    print(f"  settings.json: {settings_note}")
    if routed:
        print(f"  registry kept — it routes {len(routed)} project(s); their subtrees are untouched:")
        for repo, subtree in routed.items():
            print(f"    {repo} -> {subtree}")
    for item in manifest.get("retired", []):
        state = "restorable" if os.path.exists(item["backup"]) else "backup missing"
        print(f"  retired at install: {item['original']} (backup: {item['backup']}, {state})")
    if not args.apply:
        print("Nothing removed. Re-run with --apply.")
        return 0

    for path in remove:
        os.remove(path)
    if settings_plan:
        action, payload = settings_plan
        if action == "restore":
            shutil.copyfile(payload, settings_path)
        elif action == "delete":
            os.remove(settings_path)
        else:
            with open(settings_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(payload, indent=2) + "\n")
        backup = settings_record.get("backup")
        if action == "restore" and backup and os.path.isfile(backup):
            os.remove(backup)
    if remove_registry:
        os.remove(registry_path)
    if args.restore_retired:
        for item in manifest.get("retired", []):
            if os.path.exists(item["backup"]) and not os.path.exists(item["original"]):
                os.makedirs(os.path.dirname(item["original"]), exist_ok=True)
                shutil.move(item["backup"], item["original"])
                print(f"  restored {item['original']}")
    os.remove(manifest_path)

    # Folders this install created, deepest first — only once empty, so a
    # project subtree (or anything else someone added) keeps its parents.
    for directory in sorted(manifest.get("dirs_created", []), key=lambda d: -d.count("/")):
        for dirpath, dirnames, filenames in os.walk(directory, topdown=False):
            if dirpath.replace("\\", "/").rstrip("/").endswith("__pycache__"):
                shutil.rmtree(dirpath, ignore_errors=True)
        try:
            os.rmdir(directory)
        except OSError:
            pass  # not empty, or already gone
    print("Uninstalled." + (" Some files were kept — see above." if keep or routed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
