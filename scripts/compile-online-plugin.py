"""Compile only Nordeluna Online, preserving all other compiled plugins and saves."""
import argparse
import ctypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import zipfile
import zlib

import updater_core


def compile_plugin(game, install=False):
    game = game.resolve()
    source = game / "Plugins/Nordeluna Online"
    bundle_path = game / "Data/PluginScripts.rxdata"
    original = bundle_path.read_bytes()
    version = re.search(r"(?m)^Version\s*=\s*(.+)", (source / "meta.txt").read_text(encoding="utf-8"))[1].strip()
    dll_directory = os.add_dll_directory(str(game))
    ruby = ctypes.CDLL(str(game / "x64-msvcrt-ruby310.dll"))
    if ruby.ruby_setup() != 0:
        raise RuntimeError("Ruby initialization failed")
    ruby.ruby_options.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_char_p)]
    ruby.ruby_options.restype = ctypes.c_void_p
    ruby.ruby_options(3, (ctypes.c_char_p * 3)(b"ruby", b"-e", b""))
    ruby.rb_eval_string_protect.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]
    ruby.rb_eval_string_protect.restype = ctypes.c_size_t
    ruby.rb_string_value_cstr.argtypes = [ctypes.POINTER(ctypes.c_size_t)]
    ruby.rb_string_value_cstr.restype = ctypes.c_char_p
    status = ctypes.c_int()
    ruby.rb_eval_string_protect(b"GC.disable; $VERBOSE = nil", ctypes.byref(status))
    sources = []
    for path in sorted(source.glob("*.rb")):
        sources.append('[' + json.dumps(path.name) + ',[' + json.dumps(zlib.compress(path.read_bytes()).hex()) + '].pack("H*")]')
    code = '''
bundle = Marshal.load([%s].pack("H*"))
index = bundle.index { |entry| entry[0] == "Nordeluna Online" }
raise "Online missing from source bundle" unless index
unchanged = Marshal.dump(bundle.each_with_index.reject { |entry, i| i == index })
metadata = bundle[index][1].dup
metadata[:version] = %s
bundle[index] = ["Nordeluna Online", metadata, [%s]]
raise "Other plugins changed" unless unchanged == Marshal.dump(bundle.each_with_index.reject { |entry, i| i == index })
Marshal.dump(bundle).unpack1("H*")
''' % (json.dumps(original.hex()), json.dumps(version), ",".join(sources))
    value = ctypes.c_size_t(ruby.rb_eval_string_protect(code.encode(), ctypes.byref(status)))
    if status.value:
        raise RuntimeError("Compiled bundle validation failed")
    compiled = bytes.fromhex(ruby.rb_string_value_cstr(ctypes.byref(value)).decode("ascii"))
    output = updater_core.ROOT / "build/online-update"
    (output / "Data").mkdir(parents=True, exist_ok=True)
    (output / "Data/PluginScripts.rxdata").write_bytes(compiled)
    patch_zip = output / f"Nordeluna-Online-{version}-Windows-patch.zip"
    with zipfile.ZipFile(patch_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Data/PluginScripts.rxdata", compiled)
        for path in [*sorted(source.glob("*.rb")), source / "meta.txt"]:
            archive.write(path, "Plugins/Nordeluna Online/" + path.name)
    if install:
        if bundle_path.read_bytes() != original:
            raise RuntimeError("Game bundle changed during compilation. Close the editor and retry.")
        backup = game / "Plugins/.backups" / ("online-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f"))
        backup.mkdir(parents=True)
        shutil.copy2(bundle_path, backup / "PluginScripts.rxdata")
        temporary = bundle_path.with_suffix(".rxdata.online-tmp")
        temporary.write_bytes(compiled)
        temporary.replace(bundle_path)
        print("Compiled plugin installed; previous bundle backed up:", backup)
    print("Online version:", version, "Scripts:", len(sources), "Bytes:", len(compiled))
    print("Windows patch:", patch_zip)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, default=updater_core.DEFAULT_GAME)
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    compile_plugin(args.game, args.install)
