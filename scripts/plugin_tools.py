"""Read-only plugin inventory and access to the game's bundled Ruby VM."""
import ctypes
import json
import os
from pathlib import Path

from updater_core import ROOT, DEFAULT_GAME

MAINTAINED = ROOT / "game-plugins"
SKIP = {"output", ".backups", ".venv", "__pycache__", "server", "bridge"}


def metadata(path):
    result = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        key, separator, value = line.partition("=")
        if separator and not key.lstrip().startswith("#"):
            result.setdefault(key.strip().lower(), []).append(value.strip())
    return result


def inventory(game=DEFAULT_GAME, overlay=True):
    plugins = []
    for folder in sorted((game / "Plugins").iterdir()):
        if not folder.is_dir() or folder.name.startswith((".", "_")):
            continue
        meta = folder / "meta.txt"
        if not meta.is_file():
            continue
        replacement = MAINTAINED / folder.name
        if overlay and (replacement / "meta.txt").is_file():
            meta = replacement / "meta.txt"
        info = metadata(meta)
        sources = {}
        for root in [folder] + ([replacement] if overlay and replacement.exists() else []):
            for path in sorted(root.rglob("*.rb")):
                relative = path.relative_to(root)
                if any(p in SKIP or p.startswith((".", "_")) for p in relative.parts[:-1]):
                    continue
                sources[relative.as_posix()] = path
        plugins.append({"folder": folder.name, "name": info["name"][0],
                        "version": info["version"][0], "meta": info,
                        "sources": dict(sorted(sources.items()))})
    return plugins


class Ruby:
    """One VM per process. Feed data through memory, avoiding mixed CRT file I/O."""
    def __init__(self, game=DEFAULT_GAME):
        self.directory = os.add_dll_directory(str(game))
        self.dll = ctypes.CDLL(str(game / "x64-msvcrt-ruby310.dll"))
        if self.dll.ruby_setup() != 0:
            raise RuntimeError("Ruby initialization failed")
        self.dll.ruby_options.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_char_p)]
        self.dll.ruby_options.restype = ctypes.c_void_p
        self.dll.ruby_options(3, (ctypes.c_char_p * 3)(b"ruby", b"-e", b""))
        self.dll.rb_eval_string_protect.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]
        self.dll.rb_eval_string_protect.restype = ctypes.c_size_t
        self.dll.rb_string_value_cstr.argtypes = [ctypes.POINTER(ctypes.c_size_t)]
        self.dll.rb_string_value_cstr.restype = ctypes.c_char_p
        # Conservative GC cannot scan Python's stack as a Ruby main stack.
        self.evaluate('GC.disable; $VERBOSE = nil; "ready"')

    def evaluate(self, source):
        state = ctypes.c_int()
        value = ctypes.c_size_t(self.dll.rb_eval_string_protect(source.encode("utf-8"), ctypes.byref(state)))
        if state.value:
            error = self.evaluate('$!.full_message')
            raise RuntimeError(error)
        return self.dll.rb_string_value_cstr(ctypes.byref(value)).decode("utf-8", errors="replace")

    def load_source(self, source, name):
        # Hex preserves source encodings and interpolation literally.
        return self.evaluate('eval([%s].pack("H*").force_encoding("UTF-8"), TOPLEVEL_BINDING, %s); "loaded"' %
                             (json.dumps(source.encode("utf-8").hex()), json.dumps(str(name))))
