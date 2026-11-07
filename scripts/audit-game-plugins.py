"""Audit every runtime plugin's syntax and dependency versions without executing it."""
import argparse
import json
import re
from pathlib import Path

from plugin_tools import DEFAULT_GAME, ROOT, Ruby, inventory


def version(value):
    numbers = [int(v) for v in re.findall(r"\d+", value)]
    return tuple((numbers + [0] * 6)[:6])


def dependencies(plugins):
    errors = []
    names = {p["name"]: p for p in plugins}
    if len(names) != len(plugins):
        errors.append("Duplicate plugin names")
    edges = {}
    for plugin in plugins:
        edges[plugin["name"]] = []
        for kind in ("requires", "optional", "conflicts"):
            for entry in plugin["meta"].get(kind, []):
                fields = [v.strip() for v in entry.split(",")]
                name = fields[0]
                target = names.get(name)
                if kind == "conflicts":
                    if target and (len(fields) < 2 or version(target["version"]) == version(fields[1])):
                        errors.append(f'{plugin["name"]}: conflict with {name}')
                    continue
                if not target:
                    if kind == "requires":
                        errors.append(f'{plugin["name"]}: missing dependency {name}')
                    continue
                if len(fields) > 1 and version(target["version"]) < version(fields[1]):
                    errors.append(f'{plugin["name"]}: {name} {target["version"]} < {fields[1]}')
                if kind == "requires":
                    edges[plugin["name"]].append(name)
    visited, active = set(), set()
    def walk(name):
        if name in active:
            errors.append("Required dependency cycle: " + name)
            return
        if name in visited:
            return
        active.add(name)
        for other in edges.get(name, []):
            walk(other)
        active.remove(name)
        visited.add(name)
    for name in edges:
        walk(name)
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--installed", action="store_true", help="Audit installed files without source overlays")
    args = parser.parse_args()
    plugins = inventory(args.game, overlay=not args.installed)
    errors = dependencies(plugins)
    ruby = Ruby(args.game)
    rows = []
    for plugin in plugins:
        count = lines = 0
        for name, path in plugin["sources"].items():
            source = path.read_text(encoding="utf-8-sig")
            try:
                ruby.evaluate('RubyVM::InstructionSequence.compile([%s].pack("H*").force_encoding("UTF-8"), %s); "OK"' %
                              (json.dumps(source.encode().hex()), json.dumps(plugin["folder"] + "/" + name)))
            except RuntimeError as exc:
                errors.append(str(exc))
            count += 1
            lines += len(source.splitlines())
        rows.append({"name": plugin["name"], "version": plugin["version"], "files": count, "lines": lines})
    output = ROOT / "build/plugin-audit"
    output.mkdir(parents=True, exist_ok=True)
    report = {"plugins": rows, "errors": errors, "scope": "Syntax and dependencies; not device gameplay validation"}
    (output / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f'{len(rows)} plugins; {sum(r["files"] for r in rows)} Ruby files; {len(errors)} audit errors')
    for error in errors:
        print(error)
    print("Report:", output / "audit.json")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
