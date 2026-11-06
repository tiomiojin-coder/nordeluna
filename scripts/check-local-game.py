"""Check local compiled Essentials/Ruby data and Android preload without opening saves."""
import ctypes
import json
import os
import re
import sys
from pathlib import Path

import updater_core


def main():
    game = Path(sys.argv[1]) if len(sys.argv) > 1 else updater_core.DEFAULT_GAME
    game = game.resolve()
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
    def evaluate(code):
        status = ctypes.c_int()
        value = ctypes.c_size_t(ruby.rb_eval_string_protect(code.encode("utf-8"), ctypes.byref(status)))
        if status.value:
            error_status = ctypes.c_int()
            error = ctypes.c_size_t(ruby.rb_eval_string_protect(b"$!.full_message", ctypes.byref(error_status)))
            raise RuntimeError(ruby.rb_string_value_cstr(ctypes.byref(error)).decode("utf-8", errors="replace"))
        return ruby.rb_string_value_cstr(ctypes.byref(value)).decode("utf-8", errors="replace")

    evaluate('GC.disable; require "zlib"; "ready"')
    online_sources = [p.read_bytes().hex() for p in sorted((game / "Plugins/Nordeluna Online").glob("*.rb"))]
    expected_names = []
    for directory in (game / "Plugins").iterdir():
        metadata = directory / "meta.txt"
        if metadata.is_file():
            found = re.search(r"(?m)^Name\s*=\s*(.+)", metadata.read_text(encoding="utf-8-sig"))
            if found:
                expected_names.append(found[1].strip())
    code = r'''
plugins = Marshal.load([%s].pack("H*"))
sources = %s
expected_names = %s
missing = expected_names - plugins.map(&:first)
raise "Plugins missing from compiled bundle: #{missing.join(', ')}" unless missing.empty?
online = plugins.find { |entry| entry[0] == "Nordeluna Online" }
raise "Nordeluna Online missing from compiled bundle" unless online
compiled_sources = online[2].map { |file, body| Zlib::Inflate.inflate(body).gsub(/\r\n?/, "\n") }
sources.each do |hex|
  source = [hex].pack("H*").gsub(/\r\n?/, "\n")
  raise "Online compiled bundle is stale" unless compiled_sources.include?(source)
end
raise "Duplicate plugins in bundle" unless plugins.map(&:first).uniq.length == plugins.length
"#{plugins.length} compiled plugins; online sources match."
''' % (json.dumps((game / "Data/PluginScripts.rxdata").read_bytes().hex()), json.dumps(online_sources),
       json.dumps(expected_names, ensure_ascii=False))
    print(evaluate(code), flush=True)
    # File I/O doubles avoid mixing Windows Ruby and Python CRT file handles.
    # The live game's native Ruby main loop uses its own CRT normally.
    evaluate(r'''
$diagnostic_data = ""
class DiagnosticSink
  def write(value); $diagnostic_data << value; end
end
class << File
  def open(*args); yield DiagnosticSink.new; end
end
"ready"
''')
    evaluate((updater_core.ROOT / "android/nordeluna-display.rb").read_text(encoding="utf-8") + '\n"preload loaded"')
    checks = r'''
  # Same initializer as Essentials. Its class is reopened after the preload.
  class EventScriptError < Exception
    attr_accessor :event_message
    def initialize(message); super(nil); @event_message = message; end
  end
  detail = "Map 4, Event 9: NameError: missing event function"
  error = EventScriptError.new(detail)
  raise "Original error details hidden" unless error.message == detail
  raise "Original error type changed" unless error.is_a?(Exception) && !error.is_a?(StandardError)
  raise "Missing event diagnostic" unless $diagnostic_data.include?(detail)
  before = $diagnostic_data.bytesize
  error.message
  raise "Diagnostic duplicated" unless $diagnostic_data.bytesize == before
  raise "Normal exceptions changed" unless StandardError.new("normal").message == "normal"
  empty = EventScriptError.new(nil)
  raise "Empty event detail fallback failed" unless empty.message == "EventScriptError"
"Android event diagnostics OK."
'''
    print(evaluate(checks))


if __name__ == "__main__":
    main()
