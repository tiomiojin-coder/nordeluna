"""Replace the active pause menu with VPM; preserve all other compiled plugins and game data."""
import hashlib
import json
import shutil
import zlib
from datetime import datetime, timezone
from pathlib import Path

from plugin_tools import DEFAULT_GAME, ROOT, Ruby

game = DEFAULT_GAME.resolve()
plugins = (game / 'Plugins').resolve()
bundle = game / 'Data/PluginScripts.rxdata'
original = bundle.read_bytes()
ruby = Ruby(game)
names = ["RE Menu", "Voltseon's Pause Menu"]
packets = []
for folder in names:
    entries = []
    for path in sorted((ROOT / 'game-plugins' / folder).glob('*.rb')):
        source = path.read_bytes()
        ruby.evaluate('RubyVM::InstructionSequence.compile([%s].pack("H*").force_encoding("UTF-8")); "OK"' % json.dumps(source.hex()))
        entries.append('[%s,[%s].pack("H*")]' % (json.dumps(path.name), json.dumps(zlib.compress(source).hex())))
    packets.append('[' + ','.join(entries) + ']')
code = '''
bundle=Marshal.load([%s].pack("H*"))
old_name="v21.1 Oliveira's Menu"
vpm_name="Voltseon's Pause Menu"
before=Marshal.dump(bundle.reject { |p| [old_name,vpm_name].include?(p[0]) })
index=bundle.index { |p|p[0]==old_name }
raise "Missing menu dependency marker" unless index
meta=bundle[index][1].merge(:version=>"2.1.0")
bundle[index]=[old_name,meta,%s]
vpm=[vpm_name,{:name=>vpm_name,:version=>"2.2.1",:essentials=>["21.1"],
 :dependencies=>[["Nordeluna Phone","1.7.0"]],
 :credits=>["Voltseon","Golisopod User","ENLS","Yankas","Cony","Nordeluna"],
 :link=>"https://eeveeexpo.com/resources/692/"},%s]
bundle.reject! { |p|p[0]==vpm_name }
bundle.push(vpm)
raise "Unrelated plugin changed" unless before==Marshal.dump(bundle.reject { |p|[old_name,vpm_name].include?(p[0]) })
raise "Duplicate plugins" unless bundle.map(&:first).uniq.length==bundle.length
Marshal.dump(bundle).unpack1("H*")
''' % (json.dumps(original.hex()), packets[0], packets[1])
compiled = bytes.fromhex(ruby.evaluate(code))
stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
backup = plugins / '.backups' / ('vpm-' + stamp)
backup.mkdir(parents=True)
shutil.copy2(bundle, backup / bundle.name)
sources = []
for folder in names:
    for path in (ROOT / 'game-plugins' / folder).iterdir():
        if path.is_file():
            sources.append((path, plugins / folder / path.name))
for path in (ROOT / 'assets/vpm').rglob('*'):
    if path.is_file():
        sources.append((path, game / path.relative_to(ROOT / 'assets/vpm')))
obsolete = [plugins / 'RE Menu/001_REMenuConfig.rb', plugins / 'RE Menu/002_REMenuScene.rb']
hash_data = lambda: {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (game / 'Data').iterdir()
                     if p.is_file() and p.name != 'PluginScripts.rxdata'}
before_data = hash_data()
written = []
try:
    if bundle.read_bytes() != original:
        raise RuntimeError('Compiled plugins changed; retry with game closed')
    for source, target in sources:
        target = target.resolve()
        if not target.is_relative_to(game):
            raise RuntimeError('Target outside the named game folder')
        saved = backup / target.relative_to(game)
        exists = target.is_file()
        if exists:
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(target.name + '.vpm-tmp')
        temp.write_bytes(source.read_bytes())
        temp.replace(target)
        written.append((target, saved if exists else None))
    for target in obsolete:
        if target.is_file():
            saved = backup / target.relative_to(game)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
            target.unlink()
            written.append((target, saved))
    if hash_data() != before_data:
        raise RuntimeError('Game data changed during installation')
    if bundle.read_bytes() != original:
        raise RuntimeError('Compiled plugins changed during installation')
    temp = bundle.with_name(bundle.name + '.vpm-tmp')
    temp.write_bytes(compiled)
    temp.replace(bundle)
except Exception:
    for target, saved in reversed(written):
        if saved:
            shutil.copy2(saved, target)
        else:
            target.unlink(missing_ok=True)
    raise
(backup / 'manifest.json').write_text(json.dumps({'files': [str(p.relative_to(game)) for p,_ in written],
    'data_sha256': before_data}, indent=2), encoding='utf-8')
print('Installed VPM 2.2.1; removed retired RE renderer; unrelated plugins and game data preserved.')
print('Backup:', backup)
