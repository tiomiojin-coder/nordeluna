"""Run modified plugins in the game's Ruby VM with display/audio test doubles."""
import json
import re
import struct

from plugin_tools import DEFAULT_GAME, MAINTAINED, ROOT, Ruby


def source(folder, name):
    path = MAINTAINED / folder / name
    if not path.is_file():
        path = DEFAULT_GAME / "Plugins" / folder / name
    return path.read_text(encoding="utf-8-sig")


def main():
    ruby = Ruby()
    assets = {}
    for folder in [DEFAULT_GAME / "Graphics/UI/Battle", DEFAULT_GAME / "Plugins/00 RE Visual Core/assets"]:
        for path in folder.rglob("*.png"):
            assets[path.relative_to(DEFAULT_GAME).as_posix()] = list(struct.unpack(">II", path.read_bytes()[16:24]))
    ruby.load_source("ASSET_DIMS = " + json.dumps(assets).replace(": [", " => ["), "asset inventory")
    ruby.load_source((ROOT / "scripts/fixtures/plugin-display.fixture").read_text(encoding="utf-8"), "display doubles")
    engine = (DEFAULT_GAME / "_extracted_scripts/192_Battle_Scene_Objects.rb").read_text(encoding="utf-8-sig")
    start = engine.index("class Battle::Scene::AbilitySplashBar")
    end = engine.index("class Battle::Scene::BattlerSprite", start)
    ruby.load_source(engine[start:end], "actual engine ability bar")
    cbui = source("Customizable Battle UI", "001_Script.rb")
    ruby.load_source(cbui[cbui.index("class Battle::Scene::AbilitySplashBar"):], "actual compact CBUI initialization")
    print(ruby.evaluate('''
$PokemonSystem.battle_ui = 0
bar = Battle::Scene::AbilitySplashBar.new(0)
bar.battler = Struct.new(:name, :abilityName).new("Aipom", "Pickup")
raise "Original clipping not reproduced" unless bar.bitmap.height == 32 && bar.bitmap.draws.any? { |d| d[:y] == 38 }
bar.dispose
"PASS: reproduced original ability-name clipping in real engine + CBUI methods"
'''), flush=True)
    ruby.load_source(source("Customizable Battle UI", "003_AbilitySplashLayout.rb"), "ability layout fix")
    ruby.load_source(source("00 RE Visual Core", "001_REVisualCore.rb"), "visual base")
    pixel = source("00 RE Visual Core", "002_REPixelUI.rb")
    widths = (DEFAULT_GAME / "Plugins/00 RE Visual Core/assets/python/font_widths.txt").read_text().strip()
    pixel = pixel.replace('File.read("#{ROOT}/font_widths.txt").split(",").map(&:to_i)', "[" + widths + "]")
    ruby.load_source(pixel, "pixel UI (real font widths supplied in memory)")
    for name in ("003_JournalTheme.rb", "004_AgedBookTheme.rb", "005_SurfaceLifecycle.rb"):
        ruby.load_source(source("00 RE Visual Core", name), name)
    ruby.load_source(source("Nordeluna Mud Terrain", "002_MudEffects.rb"), "mud effects")
    ruby.load_source(source("Nordeluna Atmosphere", "003_Renderer.rb"), "atmosphere renderer")
    emotion = source("Overworld Pokemon Battles", "001_OverworldPokemonBattles.rb")
    ruby.load_source(emotion[:emotion.index("module OverworldPokemonBattles")], "actual emotion sprite")
    voice = source("Dublagem Nordeluna", "004_CinematicPlayback.rb")
    clock = re.search(r"(?m)^    def clock\n.*?^    end", voice, re.S)[0]
    ruby.load_source("module NordelunaVoice; class << self\n" + clock + "\nend; end", "actual voice clock")
    ruby.load_source((ROOT / "scripts/fixtures/plugin-regressions.fixture").read_text(encoding="utf-8"), "plugin regression checks")
    print(ruby.evaluate('"PASS: #{$assertions} plugin regression assertions (ability UI, menus, cache lifecycle, clocks and effects)"'), flush=True)


if __name__ == "__main__":
    main()
