"""Actual Ruby effect methods with graphics/filesystem doubles; no user saves."""
from pathlib import Path
from plugin_tools import Ruby,ROOT,DEFAULT_GAME


def source(folder,name):
    p=ROOT/'game-plugins'/folder/name
    return (p if p.is_file() else DEFAULT_GAME/'Plugins'/folder/name).read_text(encoding='utf-8-sig')


def main():
    ruby=Ruby()
    ruby.load_source('ASSET_DIMS={};','assets')
    ruby.load_source((ROOT/'scripts/fixtures/plugin-display.fixture').read_text(encoding='utf-8'),'graphics doubles')
    ruby.load_source((ROOT/'scripts/fixtures/performance-support.fixture').read_text(encoding='utf-8'),'device/effect environment')
    ruby.load_source(source('00 RE Visual Core','006_Performance.rb'),'real preferences')
    ruby.load_source(source('Nordeluna Atmosphere','003_Renderer.rb'),'real renderer')
    ruby.load_source(source('Nordeluna Atmosphere','005_Performance.rb'),'real atmosphere budgets')
    ruby.load_source(source('Nordeluna Mud Terrain','002_MudEffects.rb'),'real mud effects')
    ruby.load_source(source('Light System','003_PlayerShadows.rb'),'real alias-based light wrapper')
    ruby.load_source(source('Light System','004_Performance.rb'),'real shadow budget')
    ruby.load_source((ROOT/'scripts/fixtures/performance-checks.fixture').read_text(encoding='utf-8'),'performance assertions')
    print(ruby.evaluate('"PASS: #{$quality_checks} actual Ruby preference/effect checks"'))

if __name__=='__main__':main()
