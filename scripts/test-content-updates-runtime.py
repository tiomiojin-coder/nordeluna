"""Actual Ruby updater crypto/staging/atomic-apply against an in-memory filesystem."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import zlib

sys.path.insert(0,str(Path(__file__).resolve().parent))
from plugin_tools import Ruby,ROOT,DEFAULT_GAME
sys.path.insert(0,str(ROOT))
from server.updates import DIGEST_INFO

key=json.loads((ROOT/'.cache/content-updates/private-key.json').read_text())
public=json.loads((ROOT/'server/content-key.json').read_text())
old={'Data/Map039.rxdata':b'old-map','Graphics/UI/test.png':b'old-image'}
new={'Data/Map039.rxdata':b'new-map'*300,'Graphics/UI/test.png':b'new-image'*50,'Data/Map042.rxdata':b'new-area'*20}
files=[];packed={}
for name,body in new.items():
    blob=zlib.compress(body);digest=hashlib.sha256(blob).hexdigest();packed[digest]=blob
    files.append(dict(path=name,size=len(body),sha256=hashlib.sha256(body).hexdigest(),blob=digest,packed_size=len(blob),base_sha256=hashlib.sha256(old[name]).hexdigest() if name in old else None))
data=dict(version=1,base=public['base'],title='Teste',notes='Novos mapas',files=files)
raw=json.dumps(data,separators=(',',':'))
digest=DIGEST_INFO+hashlib.sha256(raw.encode()).digest();block=b'\0\1'+b'\xff'*(256-len(digest)-3)+b'\0'+digest
signature=f'{pow(int.from_bytes(block,"big"),int(key["d"],16),int(key["n"],16)):0512x}'
ruby=Ruby()
ruby.load_source((ROOT/'scripts/fixtures/content-updates.fixture').read_text(encoding='utf-8'),'in-memory updater environment')
ruby.load_source((DEFAULT_GAME/'Plugins/Nordeluna Online/002_JSON.rb').read_text(encoding='utf-8'),'actual JSON codec')
source=(ROOT/'game-plugins/Nordeluna Online/028_ContentUpdates.rb').read_text(encoding='utf-8')
if '--pc' in sys.argv:
    spec=importlib.util.spec_from_file_location('pc_builder',ROOT/'scripts/build-pc-installer.py')
    pc=importlib.util.module_from_spec(spec);spec.loader.exec_module(pc)
    source=pc.pc_update_source(source)
ruby.load_source(source,'actual signed updater')
if '--pc' in sys.argv:
    factory={'base':public['base'],'files':{name:hashlib.sha256(body).hexdigest() for name,body in old.items()}}
    ruby.load_source("$ota_files['Data/PCContentBase.json']=["+json.dumps(json.dumps(factory).encode().hex())+"].pack('H*')",'PC factory baseline')
packet=dict(manifest=raw,signature=signature)
setup=json.dumps(dict(reply=packet,old={k:v.hex() for k,v in old.items()},packed={k:v.hex() for k,v in packed.items()},plain={zlib.compress(v).hex():v.hex() for v in new.values()})).encode().hex()
ruby.load_source('''
$ota=NordelunaOnline::JSON.parse(['''+json.dumps(setup)+'''].pack('H*'))
$ota_plain=$ota['plain'].to_h { |k,v| [[k].pack('H*'),[v].pack('H*')] }
$ota['old'].each { |k,v| $ota_files[k]=[v].pack('H*') }
module NordelunaOnline::ContentUpdates
  def self.api(request)
    body=[$ota['packed'].fetch(request['blob'])].pack('H*')
    {'part'=>request['part'],'data'=>body.byteslice(request['part']*CHUNK,CHUNK).unpack1('H*')}
  end
end
''','signed test data')
for vector in [b'',b'abc',b'a'*1000,bytes(range(256))*5]:
    actual=ruby.evaluate(f'NordelunaOnline::ContentUpdates::SHA256.new.update([{json.dumps(vector.hex())}].pack("H*")).hexdigest')
    assert actual==hashlib.sha256(vector).hexdigest(),(actual,vector[:5])
ruby.load_source('''
updater=NordelunaOnline::ContentUpdates
reply=$ota['reply'];data=updater.verify(reply['manifest'],reply['signature'])
ota_reject('tampered manifest accepted') { updater.verify(reply['manifest']+' ',reply['signature']) }
%w[../save.rxdata Data/Scripts.rxdata Data/PluginScripts.rxdata /Data/Map039.rxdata Graphics/UI/../save.png].each do |path|
  ota_check(!updater.allowed_path?(path),'forbidden path accepted: '+path)
end
updater.download(reply,data)
ota_check(updater.installed['version']==0,'download changed installed version')
ota_check($ota_files['Data/Map039.rxdata']=='old-map','download touched running map')
updater.apply_pending
ota_check(updater.installed['version']==1,'verified pack not applied')
data['files'].each { |r| ota_check(updater.sha_file(r['path'])==r['sha256'],'installed file hash differs') }
ota_check($ota_files[updater.path('rollback/Data/Map039.rxdata')]=='old-map','original map not backed up')
# An interrupted commit restores the original files before game initialization.
journal=updater.read_json(updater.path('rollback/info.json'));journal['phase']='applying'
updater.write_json(updater.path('journal.json'),journal)
$ota_files['Data/Map039.rxdata']='half-written'
updater.apply_pending
ota_check($ota_files['Data/Map039.rxdata']=='old-map' && !$ota_files.key?('Data/Map042.rxdata'),'interrupted update did not restore original filesystem')
ota_check(updater.installed['version']==0,'interruption left wrong version marker')
# Failure after the first rename must roll back the entire pack.
updater.write_json(updater.path('pending.json'),reply)
$ota_fault='Graphics/UI/test.png'
ota_reject('simulated disk failure was ignored') { updater.apply_pending }
ota_check($ota_files['Data/Map039.rxdata']=='old-map' && $ota_files['Graphics/UI/test.png']=='old-image','disk failure left mixed versions')
ota_check(updater.installed['version']==0,'disk failure changed installed version')
# A manually modified base is rejected before any target is overwritten.
$ota_files['Data/Map039.rxdata']='unknown-local-map'
ota_reject('unknown base file was overwritten') { updater.apply_pending }
ota_check($ota_files['Data/Map039.rxdata']=='unknown-local-map','wrong base was modified')
$ota_files['Data/Map039.rxdata']='old-map'
updater.apply_pending
ota_check(updater.installed['version']==1,'retry after failure did not install')
''','crypto/download/rollback scenarios')
if '--pc' in sys.argv:
    ruby.load_source('''
updater=NordelunaOnline::ContentUpdates
$ota_files.delete(updater.path('installed.json'))
$ota_files['Data/Map039.rxdata']='pc-factory-map'
$ota_files['Graphics/UI/test.png']='old-image'
$ota_files.delete('Data/Map042.rxdata')
factory={'base'=>updater::BASE,'files'=>{'Data/Map039.rxdata'=>updater::SHA256.new.update('pc-factory-map').hexdigest}}
updater.write_json('Data/PCContentBase.json',factory)
updater.instance_variable_set(:@pc_factory,nil)
reply=$ota['reply'];data=updater.verify(reply['manifest'],reply['signature'])
updater.download(reply,data)
updater.apply_pending
ota_check(updater.installed['version']==1,'PC factory could not receive the shared signed pack')
ota_check($ota_files[updater.path('rollback/Data/Map039.rxdata')]=='pc-factory-map','PC factory rollback lost original map')
ota_check(updater.sha_file('Data/Map039.rxdata')==data['files'][0]['sha256'],'PC update output differs')
''','different PC factory receives the same signed server pack')
print('PASS: real Ruby SHA-256 vectors, RSA verification, forbidden paths, staged download, file hashes, atomic apply, interrupted-boot recovery, disk-failure rollback, wrong-base rejection and retry. Native zlib and Android device playback remain device checks.')
