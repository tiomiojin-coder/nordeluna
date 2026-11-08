"""Compile selected installed plugin sources, preserving all other plugins and saves."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import zipfile
import zlib

from plugin_tools import DEFAULT_GAME, ROOT, Ruby, inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folders", nargs="+", help="Installed plugin folder names to recompile")
    parser.add_argument("--game", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    game = args.game.resolve()
    plugins = {p["folder"]: p for p in inventory(game, overlay=False)}
    missing = set(args.folders) - plugins.keys()
    if missing:
        raise RuntimeError("Unknown plugin folders: " + ", ".join(sorted(missing)))
    selected = [plugins[name] for name in dict.fromkeys(args.folders)]
    bundle = game / "Data/PluginScripts.rxdata"
    original = bundle.read_bytes()
    replacements = []
    ruby = Ruby(game)
    for plugin in selected:
        for name, path in plugin["sources"].items():
            body = path.read_bytes()
            ruby.evaluate('RubyVM::InstructionSequence.compile([%s].pack("H*").force_encoding("UTF-8"), %s); "OK"' %
                          (json.dumps(body.hex()), json.dumps(name)))
        # Build as Ruby expressions: binary compressed sources must not pass through JSON encodings.
        entries = ['[%s,[%s].pack("H*")]' % (json.dumps(name), json.dumps(zlib.compress(path.read_bytes()).hex()))
                   for name, path in plugin["sources"].items()]
        replacements.append('[%s,%s,[%s]]' % (json.dumps(plugin["name"]), json.dumps(plugin["version"]), ",".join(entries)))
    code = '''
bundle = Marshal.load([%s].pack("H*"))
replacements = [%s]
names = replacements.map(&:first)
raise "Duplicate bundle entries" unless bundle.map(&:first).uniq.length == bundle.length
raise "Selected plugin missing" unless (names - bundle.map(&:first)).empty?
untouched = Marshal.dump(bundle.reject { |entry| names.include?(entry[0]) })
replacements.each do |name, version, sources|
  index = bundle.index { |entry| entry[0] == name }
  meta = bundle[index][1].dup
  meta[:version] = version
  bundle[index] = [name, meta, sources]
end
raise "Unselected plugins changed" unless untouched == Marshal.dump(bundle.reject { |entry| names.include?(entry[0]) })
Marshal.dump(bundle).unpack1("H*")
''' % (json.dumps(original.hex()), ",".join(replacements))
    compiled = bytes.fromhex(ruby.evaluate(code))
    output = ROOT / "build/plugin-update"
    (output / "Data").mkdir(parents=True, exist_ok=True)
    (output / "Data/PluginScripts.rxdata").write_bytes(compiled)
    archive_path = output / "Nordeluna-Plugins-Local-patch.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Data/PluginScripts.rxdata", compiled)
        for plugin in selected:
            folder = game / "Plugins" / plugin["folder"]
            archive.write(folder / "meta.txt", f'Plugins/{plugin["folder"]}/meta.txt')
            for name, path in plugin["sources"].items():
                archive.write(path, f'Plugins/{plugin["folder"]}/{name}')
            for path in sorted((folder/'assets').rglob('*.png')):
                archive.write(path, f'Plugins/{plugin["folder"]}/{path.relative_to(folder).as_posix()}')
    if args.install:
        if bundle.read_bytes() != original:
            raise RuntimeError("Bundle changed during compilation; close the editor and retry")
        backup = game / "Plugins/.backups" / ("plugins-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f"))
        backup.mkdir(parents=True)
        shutil.copy2(bundle, backup / bundle.name)
        for plugin in selected:
            destination = backup / plugin["folder"]
            destination.mkdir()
            shutil.copy2(game / "Plugins" / plugin["folder"] / "meta.txt", destination / "meta.txt")
        temporary = bundle.with_suffix(".rxdata.plugins-tmp")
        temporary.write_bytes(compiled)
        temporary.replace(bundle)
        print("Installed with bundle backup:", backup)
    print("Compiled:", ", ".join(p["name"] + " " + p["version"] for p in selected))
    print("Local patch:", archive_path)


if __name__ == "__main__":
    main()
