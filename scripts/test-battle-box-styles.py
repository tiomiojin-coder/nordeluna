"""Exercise actual Essentials databox lifecycle and installed presentation, without saves."""
import json
import sys
import zlib
from pathlib import Path

from plugin_tools import DEFAULT_GAME, ROOT, Ruby

sys.path.insert(0, str(ROOT / '.cache/map-render-lib'))
from PIL import Image

dims = {}
for base, prefix in [(DEFAULT_GAME / 'Graphics/UI', 'Graphics/UI'),
                     (ROOT / 'game-plugins/Customizable Battle UI/assets', 'Plugins/Customizable Battle UI/assets')]:
    for path in base.rglob('*.png'):
        dims[f'{prefix}/{path.relative_to(base).as_posix()}'] = list(Image.open(path).size)

ruby = Ruby()
# Optional installation audit: use the exact compressed code in the game's
# active bundle, rather than trusting copied source files or a simulated order.
compiled = {}
if '--installed' in sys.argv:
    packet = json.dumps((DEFAULT_GAME / 'Data/PluginScripts.rxdata').read_bytes().hex())
    records = ruby.evaluate('Marshal.load([%s].pack("H*")).flat_map { |p| p[2].map { |name,body| p[0]+"|"+name+"|"+body.unpack1("H*") } }.join("\\n")' % packet)
    for row in records.splitlines():
        plugin, filename, body = row.split('|', 2)
        compiled[plugin, filename] = zlib.decompress(bytes.fromhex(body)).decode('utf-8-sig')
    for plugin, filename in [('Customizable Battle UI', '004_DataBoxStyles.rb'),
                             ('Nordeluna CBUI Book', '001_Compatibility.rb')]:
        expected = (ROOT / 'game-plugins' / plugin / filename).read_bytes().decode('utf-8-sig')
        assert compiled[plugin, filename] == expected, ('Stale compiled plugin', plugin, filename)

def integration_source(plugin, filename):
    if compiled:
        return compiled[plugin, filename]
    return (ROOT / 'game-plugins' / plugin / filename).read_text(encoding='utf-8')

ruby.load_source('DIMS = {' + ','.join(json.dumps(k) + '=>' + str(v) for k, v in dims.items()) + '}', 'image dimensions')
ruby.load_source('''
Rect = Struct.new(:x, :y, :width, :height)
class Color
  attr_reader :rgba
  def initialize(*args); @rgba=args; end
end
# XP's Font does not expose shadow/shadow=. Keep this surface strict so a
# test cannot accidentally accept APIs absent from the actual game motor.
Font = Struct.new(:size, :color, :bold)
class Bitmap
  attr_reader :width, :height, :font, :ops, :path
  def initialize(w,h=nil)
    if h; @width,@height=w,h; else; @path=w; @width,@height=DIMS.fetch(w); end
    @font=Font.new(20,Color.new(0,0,0),false); @ops=[]; @disposed=false
  end
  def clear; @ops=[]; end
  def blt(x,y,source,rect); raise 'disposed source' if source.disposed?; @ops << [:blt,x,y,source.path,rect.to_a]; end
  def fill_rect(*args); @ops << [:fill,*args]; end
  def draw_text(*args); @ops << [:text,*args,@font.size,@font.color.rgba]; end
  def text_size(text); Rect.new(0,0,text.length*@font.size*0.55,24); end
  def disposed?; @disposed; end
  def dispose; raise 'double bitmap dispose' if @disposed; @disposed=true; end
end
class Sprite
  attr_accessor :x,:y,:z,:opacity,:color,:bitmap,:src_rect
  attr_reader :visible
  def initialize(*); @src_rect=Rect.new(0,0,0,0); @disposed=false; end
  def visible=(v); raise 'not bool' unless v==true || v==false; @visible=v; end
  def disposed?; @disposed; end
  def dispose; raise 'double sprite dispose' if @disposed; @disposed=true; end
  def update; end
  def flash(*); end
end
class BitmapSprite < Sprite
  def initialize(w,h,v=nil); super(v); self.bitmap=Bitmap.new(w,h); end
  def dispose; bitmap.dispose; super; end
end
class AnimatedBitmap
  attr_reader :bitmap
  def initialize(path); @bitmap=Bitmap.new(path+'.png'); end
  def width; @bitmap.width; end
  def height; @bitmap.height; end
  def dispose; @bitmap.dispose; end
end
module Graphics
  def self.width; 512; end
  def self.height; 384; end
  def self.frame_rate; 60; end
end
module System
  class << self; attr_accessor :time; end
  self.time=0.0
  def self.uptime; self.time; end
end
module NordelunaUI
  GOLD=[224,190,100]; CORAL=[220,80,80]; DEEP=[10,20,30]
  PAPER=[240,240,230]; FOREST=[20,40,40]; LINE=[60,90,90]; EDGE=[80,110,110]
  def self.surface(*); end
end
class HandlerHash < Hash
  def add(key,value); self[key]=value; end
  def remove(key); delete(key); end
end
class EnumOption; end
class PokemonSystem; end
class Battle; class Scene; end; end
def _INTL(s,*); s; end
def pbSetSystemFont(*); end
def pbDrawTextPositions(bitmap,rows)
  rows.each { |text,x,y,*rest| bitmap.draw_text(x,y,200,24,text) }
end
def pbResolveBitmap(path); DIMS.key?(path+'.png'); end
def pbDrawImagePositions(bitmap, rows)
  rows.each do |path,x,y,sx=0,sy=0,w=-1,h=-1|
    source=Bitmap.new(path+'.png')
    bitmap.blt(x,y,source,Rect.new(sx,sy,w<0 ? source.width : w,h<0 ? source.height : h))
  end
end
def pbUpdateSpriteHash(hash); hash.each_value(&:update); end
def pbDisposeSpriteHash(hash); hash.each_value(&:dispose); end
def pbSEPlay(*); end
def pbSEStop; end
def lerp(a,b,d,start,now); a+(b-a)*[[((now-start)/d),0].max,1].min; end
''', 'graphics surface doubles')

menu_source = next(p.read_text(encoding='utf-8') for p in (DEFAULT_GAME / '_extracted_scripts').glob('*.rb')
                   if 'module MenuHandlers' in p.read_text(encoding='utf-8'))
ruby.load_source(menu_source[menu_source.index('module MenuHandlers'):], 'actual Essentials MenuHandlers')
ruby.load_source((DEFAULT_GAME / 'Plugins/Customizable Battle UI/000_Settings.rb').read_text(encoding='utf-8'), 'actual original theme option')
options_source = (DEFAULT_GAME / '_extracted_scripts/307_UI_Options.rb').read_text(encoding='utf-8')
ruby.load_source(options_source[options_source.index('module PropertyMixin'):options_source.index('class Window_PokemonOption')], 'native Essentials option classes')
engine = (DEFAULT_GAME / '_extracted_scripts/192_Battle_Scene_Objects.rb').read_text(encoding='utf-8')
start = engine.index('class Battle::Scene::PokemonDataBox')
end = engine.index('\nclass Battle::Scene::AbilitySplashBar', start)
ruby.load_source(engine[start:end], 'actual Essentials PokemonDataBox')
for file in ['001_Theme.rb', '003_DataBoxes.rb']:
    ruby.load_source((DEFAULT_GAME / 'Plugins/Nordeluna Battle Presentation' / file).read_text(encoding='utf-8'), file)
ruby.load_source('module NordelunaBattle; def self.text(*); end; end', 'unchanged Nordeluna font renderer double')
custom = (DEFAULT_GAME / 'Plugins/Customizable Battle UI/001_Script.rb').read_text(encoding='utf-8')
start = custom.index('class Battle::Scene::PokemonDataBox')
end = custom.index('\nclass Battle::Scene::AbilitySplashBar', start)
ruby.load_source(custom[start:end], 'actual existing Customizable Battle UI databox loader')
# Existing settings supply battle_ui=1. The new selectors do not change it.
ruby.load_source('$PokemonSystem=PokemonSystem.new', 'existing settings')
ruby.load_source(integration_source('Customizable Battle UI', '004_DataBoxStyles.rb'), 'new selectors and renderer')
ruby.load_source('''
class Battle::Scene
  def pbInitSprites; end
  def pbCommandMenuEx; end
  def pbFightMenu; end
  class FightMenu; end
end
module NordelunaBattle::Scene
  def pbInitSprites; super; end
  def pbCommandMenuEx; super; end
  def pbFightMenu; super; end
end
Battle::Scene.prepend(NordelunaBattle::Scene)
''', 'unrelated scene menu hooks')
ruby.load_source(integration_source('Nordeluna CBUI Book', '001_Compatibility.rb'), 'actual final compatibility layer')
ruby.load_source('''
def check(condition,message); raise message unless condition; end
Pkmn=Struct.new(:exp_fraction)
class BoxBattler
  attr_reader :index
  attr_accessor :hp
  def initialize(index); @index=index; @hp=100; end
  def name; "NoctgeistMuitoLongo"; end
  def level; 100; end
  def displayGender; @index%2; end
  def pokemon; Pkmn.new(0.5); end
  def status; :NONE; end
  def shiny?; true; end
  def owned?; true; end
  def mega?; true; end
  def primal?; false; end
  def opposes?(*); @index.odd?; end
  def totalhp; 100; end
end
check($PokemonSystem.battle_box_style=='nordeluna','old save default')
legacy=PokemonSystem.new
legacy.instance_variable_set(:@nordeluna_player_box,'emerald')
legacy.instance_variable_set(:@nordeluna_foe_box,'swsh')
check(legacy.battle_box_style=='emerald','legacy choice migrates deterministically')
legacy.foe_box_style='swsh'
check(legacy.player_box_style=='swsh' && legacy.foe_box_style=='swsh','compatibility setters update both')
choices=[]
MenuHandlers.each_available(:options_menu) { |key,hash,name| choices << [key,hash,name] }
check(choices.length==1,'old parallel options still registered')
key,hash,name=choices.first
check(key==:battle_ui && name=='Caixa de batalha','original option not replaced')
option=hash['type'].new(name,hash['parameters'],hash['get_proc'],hash['set_proc'])
3.times { option.set(option.next(option.get),nil) }
check($PokemonSystem.battle_box_style=='emerald','native right-arrow option callback did not apply')
check(NordelunaDataBoxes.selected(0)=='emerald' && NordelunaDataBoxes.selected(1)=='emerald','both sides must change together')
copy=Marshal.load(Marshal.dump($PokemonSystem))
check(copy.battle_box_style=='emerald','preference persists in system save')
option.set(999,nil)
check($PokemonSystem.battle_box_style=='nordeluna','bad enum value')
samples=[]; count=0
NordelunaDataBoxes::STYLES.each do |label,style|
  check(NordelunaDataBoxes.available?(style),'assets incomplete '+style)
  choice=NordelunaDataBoxes::STYLES.index { |row| row[1]==style }
  option.set(choice,nil)
  check($PokemonSystem.player_box_style==style && $PokemonSystem.foe_box_style==style,'unified preference')
  [1,2,3].each do |size|
    (size*2).times do |index|
      battler=BoxBattler.new(index)
      box=Battle::Scene::PokemonDataBox.new(battler,size)
      if style!='nordeluna'
        backgrounds=box.bitmap.ops.select { |op| op[0]==:blt && op[3].to_s.include?('databox_') }
        check(backgrounds.length==1,'selected renderer bypassed by compatibility layer')
        check(backgrounds[0][3].start_with?(NordelunaDataBoxes.path(style,'')),'wrong background theme')
        stars=box.bitmap.ops.select { |op| op[0]==:blt && op[3]=='Graphics/UI/shiny.png' }
        check(stars[0][1]==box.instance_variable_get(:@spriteBaseX)+(index.odd? ? 206 : -6),'shiny covers HP label')
      end
      box.update
      hp=box.instance_variable_get(:@hpBar)
      exp=box.instance_variable_get(:@expBar)
      check(hp.src_rect.width==96,'full hp '+style)
      check(hp.src_rect.height==(style=='emerald' ? 4 : 6),'hp height '+style)
      check(exp.visible==false,'hidden initially')
      box.visible=true
      check(exp.visible==(index.even? && size==1),'exp visibility')
      [50,25,0].each do |amount|
        battler.hp=amount;box.refresh_hp
        check(hp.src_rect.width==((96*amount/100.0/2).round*2),'hp width')
        check(hp.src_rect.y==(amount<=25 ? 2 : 1)*hp.src_rect.height,'hp color')
      end
      battler.hp=20;System.time=0;box.animate_hp(100,20);System.time=1.1;box.update
      check(!box.animating_hp? && box.hp==20,'native hp animation')
      if index.even? && size==1
        box.animate_exp(0,100,200);System.time=3;box.update
        check(!box.animating_exp?,'native exp animation')
      end
      if size==1 && style!='nordeluna'
        samples << [style,index,box.bitmap.ops,hp.x-box.x,hp.y-box.y]
      end
      box.dispose
      count+=1
    end
  end
end
# Missing asset falls back as a complete style, rather than mixing broken bars.
removed=DIMS.delete(NordelunaDataBoxes.path('emerald','overlay_hp')+'.png')
$PokemonSystem.battle_box_style='emerald'
check(NordelunaDataBoxes.selected(0)=='nordeluna','missing asset fallback')
BOX_TEST_COUNT=count
BOX_SAMPLES=samples
''', 'lifecycle and persistence checks')
print('PASS:', ruby.evaluate('BOX_TEST_COUNT.to_s'), 'actual databox instances across five styles and single/double/triple battles')
print('PASS: native option classes, unified selector on both sides, old-save migration, persistence, missing assets, HP/EXP animations, disposal')

# Use a tiny Ruby serializer for primitive preview records, avoiding native JSON extensions.
serialized = ruby.evaluate('BOX_SAMPLES.inspect')
(ROOT / '.cache/battle-styles/runtime-samples.txt').write_text(serialized, encoding='utf-8')
