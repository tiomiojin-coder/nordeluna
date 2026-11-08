"""Exercise official VPM components, menu dispatch and lifecycle without game saves."""
import json
import sys
import zlib
from pathlib import Path
from plugin_tools import DEFAULT_GAME, ROOT, Ruby

sys.path.insert(0, str(ROOT / '.cache/map-render-lib'))
from PIL import Image

root = ROOT / 'assets/vpm'
dims = {p.relative_to(root).as_posix(): list(Image.open(p).size) for p in root.rglob('*.png')}
ruby = Ruby()
compiled = {}
if '--installed' in sys.argv:
    packet = json.dumps((DEFAULT_GAME / 'Data/PluginScripts.rxdata').read_bytes().hex())
    records = ruby.evaluate('Marshal.load([%s].pack("H*")).find { |p|p[0]=="Voltseon\'s Pause Menu" }[2].map { |name,body| name+"|"+body.unpack1("H*") }.join("\\n")' % packet)
    for row in records.splitlines():
        name, body = row.split('|', 1)
        compiled[name] = zlib.decompress(bytes.fromhex(body))
    for path in (ROOT / "game-plugins/Voltseon's Pause Menu").glob('*.rb'):
        assert compiled[path.name] == path.read_bytes(), ('Stale compiled VPM source', path.name)
    for path in root.rglob('*.png'):
        assert (DEFAULT_GAME / path.relative_to(root)).read_bytes() == path.read_bytes(), ('Missing or stale graphic', path.name)
ruby.load_source('DIMS = {' + ','.join(json.dumps(k) + '=>' + str(v) for k,v in dims.items()) + '}', 'VPM image dimensions')
ruby.load_source((ROOT / 'scripts/fixtures/vpm-support.fixture').read_text(encoding='utf-8'), 'strict XP graphics and input')
for p in sorted((ROOT / "game-plugins/Voltseon's Pause Menu").glob('*.rb')):
    source = compiled[p.name].decode('utf-8-sig') if compiled else p.read_text(encoding='utf-8-sig')
    ruby.load_source(source, p.name)
ruby.load_source('''
check(!Font.new.respond_to?(:shadow),'test must not support non-XP font shadow')
[:nordeluna_online,:missions,:nordeluna_performance,:controls,:crafting,:arquivos,:unknown_future_plugin].each do |key|
  path=$PokemonSystem.from_current_menu_theme('menu_'+key.to_s)
  check(pbResolveBitmap(MENU_FILE_PATH+path),'missing fallback icon '+key.to_s)
end
$PokemonSystem.current_menu_theme=999
check($PokemonSystem.current_menu_theme==8,'theme upper bound')
$PokemonSystem.current_menu_theme=nil
check($PokemonSystem.current_menu_theme==0,'invalid saved theme')
check(MenuHandlers::HANDLERS[:options_menu][:menu_theme]['type']==EnumOption,'theme options compatibility')
$actions=[]
15.times do |i|
  MenuHandlers.add(:pause_menu,('entry_'+i.to_s).to_sym,{
    'name'=>i==7 ? proc { 'Online (2)' } : 'Entry '+i.to_s,'order'=>i,
    'condition'=>proc {true},'effect'=>proc { |menu|
      $actions << i
      menu.pbHideMenu
      menu.pbShowMenu
      next false
    }
  })
end
9.times do |theme|
  $PokemonSystem.current_menu_theme=theme
  $game_temp.menu_last_choice=999
  scene=VoltseonsPauseMenu_Scene.new
  scene.pbStartScene
  menu=scene.instance_variable_get(:@pause_menu)
  check(menu.instance_variable_get(:@current_selection)==14,'stale selection not clamped')
  check(menu.instance_variable_get(:@entries).length==15,'plugin entries lost')
  # LEFT and RIGHT use the same Input constants sent by Android virtual buttons.
  Input.queue=[[:RIGHT],[:LEFT],[:USE],[:BACK]]
  scene.update
  check($actions.last==14,'directional selection or custom callback failed')
  check(scene.terminated?,'menu did not terminate')
  scene.pbEndScene # End must be idempotent for existing handlers and ensure.
end
# Save/travel handlers may dispose the menu and return false. No component can
# be updated, redrawn or disposed twice after that effect.
MenuHandlers::HANDLERS[:pause_menu].clear
MenuHandlers.add(:pause_menu,:save,{'name'=>'Salvar','order'=>0,'effect'=>proc { |menu|menu.pbEndScene;next false }})
scene=VoltseonsPauseMenu_Scene.new
scene.pbStartScene
Input.queue=[[:USE]]
scene.update
check(scene.terminated?,'early callback termination')
scene.pbEndScene
# Classic scene callers are redirected to VPM, including scripts/events.
screen=PokemonPauseMenu.new(PokemonPauseMenu_Scene.new)
check(screen.instance_variable_get(:@scene).is_a?(VoltseonsPauseMenu_Scene),'old menu still opens')
Input.queue=[[:BACK]]
screen.pbStartPokemonMenu
check($player.opened==1 && $player.closed==1,'MUI party-time integration lost')
check($game_temp.in_menu==false,'in_menu leaked')
# Six members, egg, fainted member, max level and a custom species-like object.
$player.party=Array.new(6) {Pokemon.new}
$player.party[1].egg=true;$player.party[2].hp=0;$player.party[3].fraction=Float::NAN
scene=VoltseonsPauseMenu_Scene.new
scene.pbStartScene
Input.queue=[[:BACK]]
scene.update
VPM_TEST_RESULT='PASS: all 9 themes, 15 entries, directional selection, fallback icons, save/early disposal, old-scene redirect, six-member/egg/max-level party, MUI timing'
''', 'VPM regression checks')
print(ruby.evaluate('VPM_TEST_RESULT'))
