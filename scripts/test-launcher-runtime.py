"""Test the real Ruby launcher contract with memory-only files and save doubles."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from plugin_tools import ROOT,DEFAULT_GAME,Ruby

game=(Path(sys.argv[1]) if len(sys.argv)>1 else DEFAULT_GAME).resolve()
ruby=Ruby(game)
ruby.load_source((ROOT/'scripts/fixtures/content-updates.fixture').read_text(encoding='utf-8'),'memory filesystem')
ruby.load_source((game/'Plugins/Nordeluna Online/002_JSON.rb').read_text(encoding='utf-8'),'actual JSON')
ruby.load_source('''
module NordelunaOnline
  class VersionMismatch<Error;end
  def self.build;'compatible-pc-android';end
  def self.request(*args);raise Error,'As versoes do jogo sao diferentes.';end
  module ContentUpdates
    def self.mkdir(path);$ota_dirs[path]=true;end
    def self.write_json(path,data);File.binwrite(path,NordelunaOnline::JSON.dump(data));end
    def self.atomic_write(path,data);File.binwrite(path,data);end
  end
end
module REInterface
  def self.save_directory;'/legacy';end
end
module SaveData;FILE_PATH='/legacy/Game.rxdata';end
module Game
  def self.save(*args);true;end
  def self.load(*args);true;end
end
class LauncherStats;def play_time;3723;end;end
class LauncherPreferences;attr_accessor :bgmvolume,:sevolume;end
$stats=LauncherStats.new;$PokemonSystem=LauncherPreferences.new
class Dir
  def self.glob(path);[];end
end
''','launcher dependencies')
config={'channel':'stable','save_root':'C:/memory/profiles/stable','volume':35}
source='file=File.join(Dir.pwd,\'.nordeluna-launcher.json\'); $ota_files[file]='+json.dumps(json.dumps(config))
ruby.load_source(source,'local profile settings')
ruby.load_source((ROOT/'game-plugins/Nordeluna Online/031_LauncherExperience.rb').read_text(encoding='utf-8'),'actual launcher contract')
ruby.load_source('''
feature=NordelunaOnline::LauncherExperience
stable=REInterface.save_directory
ota_check(stable.end_with?('/profiles/stable'),'stable profile ignored')
ota_check(SaveData::FILE_PATH==File.join(stable,'Game.rxdata'),'native save path leaked to legacy')
Game.load
ota_check($PokemonSystem.bgmvolume==35 && $PokemonSystem.sevolume==35,'volume not applied on load')
Game.save
metadata=NordelunaOnline::JSON.parse($ota_files.fetch(File.join(stable,'launcher-save-info.json')))
ota_check(metadata['play_seconds']==3723 && metadata['channel']=='stable','backup metadata missing')
ota_check(NordelunaOnline.build=='compatible-pc-android','stable build changed')
feature.instance_variable_set(:@config,{'channel'=>'testers','save_root'=>'C:/memory/profiles/testers'})
ota_check(REInterface.save_directory!=stable,'tester saves share stable directory')
ota_check(NordelunaOnline.build=='compatible-pc-android-testers','tester online isolation missing')
begin
  NordelunaOnline.request(nil,nil)
  raise 'version mismatch accepted'
rescue NordelunaOnline::VersionMismatch=>error
  ota_check(error.message.include?('PC e Android'),'compatibility warning unclear')
end
''','profile/save/options/compatibility assertions')
print('PASS: actual Ruby launcher profiles, native save path, save metadata, volume and PC/Android compatibility warning')
ruby.load_source('''
NordelunaOnline::LauncherExperience.instance_variable_set(:@config,{'settings_only'=>true})
$control_frames=0
module System;def self.show_settings;$settings_requested=true;end;end
module Graphics
  def self.width;512;end
  def self.height;384;end
  def self.update;$control_frames+=1;end
end
module Input
  def self.update;end
  def self.trigger?(key);$control_frames>=3;end
end
class Color;def initialize(*args);end;end
class SettingsFont;attr_accessor :size,:color;end
class Bitmap
  attr_reader :font
  def initialize(*args);@font=SettingsFont.new;end
  def fill_rect(*args);end
  def draw_text(*args);end
  def disposed?;!!@disposed;end
  def dispose;@disposed=true;$control_bitmap_disposed=true;end
end
class Sprite
  attr_accessor :bitmap
  def disposed?;!!@disposed;end
  def dispose;@disposed=true;$control_sprite_disposed=true;end
end
''','asynchronous native settings environment')
ruby.load_source('begin\n'+(ROOT/'windows/PrelaunchControls.rb').read_text(encoding='utf-8')+'\nrescue SystemExit\n$settings_exited=true\nend','actual PC prelaunch settings')
ruby.load_source("ota_check($settings_requested && $control_frames==3 && $settings_exited && $control_bitmap_disposed && $control_sprite_disposed,'settings request exited before the player returned')",'native settings return assertion')
print('PASS: asynchronous PC controls stay alive, return on Back and dispose their resources')
