"""Real bundled Ruby 3.1 + actual local Essentials data. Does not open/write saves."""
import ctypes
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import updater_core
GAME = updater_core.DEFAULT_GAME
HERE = GAME / "Plugins/_online_tests"
sys.stdout.reconfigure(encoding="utf-8")
PLUGINS = HERE.parent
GAME = PLUGINS.parent
os.chdir(GAME)
dll_directory = os.add_dll_directory(str(GAME))
ruby = ctypes.CDLL(str(GAME / "x64-msvcrt-ruby310.dll"))
assert ruby.ruby_setup() == 0
ruby.ruby_options.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_char_p)]
ruby.ruby_options.restype = ctypes.c_void_p
ruby.ruby_options(3, (ctypes.c_char_p * 3)(b"ruby", b"-e", b""))
ruby.rb_eval_string_protect.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]
ruby.rb_eval_string_protect.restype = ctypes.c_size_t
ruby.rb_string_value_cstr.argtypes = [ctypes.POINTER(ctypes.c_size_t)]
ruby.rb_string_value_cstr.restype = ctypes.c_char_p

chunks = [("support", (HERE / "support.fixture").read_text(encoding="utf-8"))]
engine = GAME / "_extracted_scripts"
prefixes = ["000_", "001_", "015_", "035_", "100_", "103_", "104_", "105_", "106_", "107_", "108_", "109_", "110_", "111_", "112_", "114_", "116_", "117_", "118_", "119_", "124_", "125_", "126_", "127_", "129_", "130_", "133_", "135_", "273_", "274_", "275_", "276_", "277_"]
for prefix in prefixes:
    p = next(engine.glob(prefix + "*"))
    chunks.append((p.name, p.read_text(encoding="utf-8")))
metrics_script = next(engine.glob("131_*"))
chunks.append(("actual species metrics", metrics_script.read_text(encoding="utf-8")))
data_packets = {f"Data/{p.name}": p.read_bytes().hex() for p in (GAME / "Data").glob("*.dat")}
chunks.append(("packets", "DATA_PACKETS = {" + ",".join(json.dumps(k) + " => " + json.dumps(v) for k, v in data_packets.items()) + "}"))
chunks.append(("data", '[GameData::Species, GameData::Move, GameData::Ability, GameData::Item, GameData::Type, GameData::TrainerType, GameData::Ribbon].each(&:load)'))
chunks.append(("metrics data", 'GameData::SpeciesMetrics.load; "metrics ready"'))
chunks.append(("trainer", 'Object.send(:remove_const, :NPCTrainer)\n' + next(engine.glob("286_*")).read_text(encoding="utf-8")))
for num in list(range(147, 185)) + [195] + list(range(198, 209)) + list(range(222, 228)) + [229, 230, 231, 237, 263]:
    if num in (158, 159, 170, 171):
        continue
    p = next(engine.glob(f"{num:03}_*"))
    chunks.append((p.name, p.read_text(encoding="utf-8")))
gen9 = PLUGINS / "Generation 9 Pack Scripts"
chunks.append(("gen9 settings", (gen9 / "Settings.rb").read_text(encoding="utf-8")))
chunks.append(("gen9 Pokemon", (gen9 / "[000] General/[000] Pokemon.rb").read_text(encoding="utf-8")))
for p in sorted((gen9 / "[001] Battle").glob("*.rb")):
    chunks.append(("gen9 " + p.name, p.read_text(encoding="utf-8")))
for group in ("[003] Moves", "[004] Abilities", "[005] Items"):
    for p in sorted((gen9 / group).glob("*.rb")):
        chunks.append(("gen9 " + group + " " + p.name, p.read_text(encoding="utf-8")))
maintained = Path(__file__).resolve().parents[1] / "game-plugins/Nordeluna Online"
sources = {p.name: p for p in (PLUGINS / "Nordeluna Online").glob("*.rb")}
sources.update({p.name: p for p in maintained.glob("*.rb")})
for p in (sources[name] for name in sorted(sources)):
    chunks.append((p.name, p.read_text(encoding="utf-8")))
chunks.append(("checks", (HERE / "checks.fixture").read_text(encoding="utf-8")))
chunks.append(("battle checks", (HERE / "battle.fixture").read_text(encoding="utf-8")))
# Exercise the actual Pokemon extension from the installed MUI plugin.
mui_source = (PLUGINS / "[MUI_001] Enhanced Pokemon UI/[002] Legacy Data.rb").read_text(encoding="utf-8")
mui_start = mui_source.index("class Pokemon", mui_source.index("# Pokemon data."))
chunks.append(("real MUI Pokemon data", mui_source[mui_start:]))
chunks.append(("MUI online regressions", (Path(__file__).resolve().parent / "fixtures/online-mui.fixture").read_text(encoding="utf-8")))
chunks.append(("Aipom/Catitux and immediate-save regression", (Path(__file__).resolve().parent / "fixtures/online-aipom-catitux.fixture").read_text(encoding="utf-8")))
# Exercise the original installed UI methods with lightweight display doubles.
import re
scene_methods = []
for filename, signatures in (("187_Battle_Scene.rb", ("pbChangePokemon",)),
                              ("189_Scene_ChooseCommands.rb", ("pbCommandMenu", "pbFightMenu"))):
    source = (engine / filename).read_text(encoding="utf-8")
    for signature in signatures:
        match = re.search(r"(?ms)^  def " + signature + r"\(.*?(?=^  def )", source)
        if not match:
            raise RuntimeError("Missing actual scene method: " + signature)
        scene_methods.append(match[0])
chunks.append(("actual scene methods", "class Battle::Scene::OnlineViewFixture < Battle::Scene\n" + "\n".join(scene_methods) + "\nend"))
cbui = (PLUGINS / "Customizable Battle UI/001_Script.rb").read_text(encoding="utf-8")
databox = cbui[cbui.index("class Battle::Scene::PokemonDataBox < Sprite"):cbui.index("class Battle::Scene::AbilitySplashBar < Sprite")]
chunks.append(("actual CBUI data box", "class Sprite; end unless defined?(Sprite)\n" + databox))
chunks.append(("local perspective and online UX", (Path(__file__).resolve().parent / "fixtures/online-experience.fixture").read_text(encoding="utf-8")))
chunks.append(("nick, custom rules, doubles and map emotes", (Path(__file__).resolve().parent / "fixtures/online-social.fixture").read_text(encoding="utf-8")))
target_source = (engine / "189_Scene_ChooseCommands.rb").read_text(encoding="utf-8")
target_methods = [re.search(r"(?ms)^  def " + name + r"\(.*?(?=^  def )", target_source)[0]
                  for name in ("pbChooseTarget", "pbFirstTarget", "pbCreateTargetTexts")]
chunks.append(("actual target scene", "class Battle::Scene::RealOnlineTargetFixture < Battle::Scene\n" + "\n".join(target_methods) + "\nend"))
chunks.append(("real target UI, six Noctgeist team and Mega", (Path(__file__).resolve().parent / "fixtures/online-polish.fixture").read_text(encoding="utf-8")))
chunks.append(("Android transport and clipboard", (Path(__file__).resolve().parent / "fixtures/online-transport.fixture").read_text(encoding="utf-8")))
state = ctypes.c_int()
# ctypes embeds Ruby without a native Ruby main stack. Disable conservative GC
# in this short-lived test process, as its stack scanner cannot scan Python's.
ruby.rb_eval_string_protect(b"GC.disable; $VERBOSE = nil", ctypes.byref(state))
for name, code in chunks:
    value = ctypes.c_size_t(ruby.rb_eval_string_protect(("# encoding: UTF-8\n" + code).encode(), ctypes.byref(state)))
    if state.value:
        error_code = b'($!.full_message rescue $!.to_s)'
        err_state = ctypes.c_int()
        err = ctypes.c_size_t(ruby.rb_eval_string_protect(error_code, ctypes.byref(err_state)))
        print(ruby.rb_string_value_cstr(ctypes.byref(err)).decode("utf-8", errors="replace")[:4000])
        raise SystemExit(f"Ruby checks failed in {name}: state {state.value}")
print(ruby.rb_string_value_cstr(ctypes.byref(value)).decode("utf-8"))
