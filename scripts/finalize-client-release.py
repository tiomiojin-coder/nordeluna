"""Sign the catalogue only after both GitHub builds have published their files."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import urllib.request
import tempfile
import zipfile
import hashlib
import zlib
import urllib.parse

from updater_core import ROOT,GitHub,git,REPOSITORY


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pc-tag',default='pc-1.2.0');parser.add_argument('--android-tag',default='android-1.15')
    parser.add_argument('--pc-code',type=int,default=120);parser.add_argument('--android-code',type=int,default=22)
    parser.add_argument('--pc-commit');parser.add_argument('--android-commit')
    parser.add_argument('--stable-only',action='store_true',help='Publicar somente o catalogo estavel')
    parser.add_argument('--publish',action='store_true');args=parser.parse_args()
    client=GitHub();repo=client.get('')
    if repo['private']:raise ValueError('Os jogadores precisam de acesso publico aos downloads.')
    commit=git('rev-parse','HEAD')
    for workflow in ('nordeluna-android.yml','nordeluna-pc.yml'):
        expected_commit=args.pc_commit if workflow=='nordeluna-pc.yml' else args.android_commit
        expected_commit=git('rev-parse',expected_commit) if expected_commit else commit
        runs=client.get(f'actions/workflows/{workflow}/runs?per_page=20')['workflow_runs']
        if not any(row['head_sha']==expected_commit and row['conclusion']=='success' for row in runs):raise ValueError('Aguarde a build '+workflow+' deste commit terminar com sucesso.')
    spec=importlib.util.spec_from_file_location('catalog_signer',ROOT/'scripts/client-release-tools.py');signer=importlib.util.module_from_spec(spec);spec.loader.exec_module(signer)
    pc=client.get('releases/tags/'+args.pc_tag);android=client.get('releases/tags/'+args.android_tag)
    # Derive identity from the exact versioned archive, never a moving editor folder.
    expected=(ROOT/'game-assets/sha256.txt').read_text(encoding='utf-8').split()[0]
    with tempfile.TemporaryFile() as archive:
        digest=hashlib.sha256()
        for part in sorted((ROOT/'game-assets').glob('game-assets.zip.part[0-9][0-9][0-9]')):
            with part.open('rb') as stream:
                while body:=stream.read(1024*1024):digest.update(body);archive.write(body)
        if digest.hexdigest()!=expected:raise ValueError('O arquivo local nao corresponde a build publicada')
        archive.seek(0)
        with zipfile.ZipFile(archive) as game:
            build=re.search(r'BUILD = "([^"]+)"',game.read('Plugins/Nordeluna Online/001_Config.rb').decode('utf-8'))[1]
            crc=0
            for name in ('species','moves','abilities','items','types','trainer_types'):crc=zlib.crc32(game.read('Data/'+name+'.dat'),crc)
    meta={'compatibility':build+'-'+str(crc)}
    notes=(ROOT/'docs/release-1.15.md').read_text(encoding='utf-8')
    def row(release,pattern,code,compat):
        matches=[asset for asset in release['assets'] if re.fullmatch(pattern,asset['name'])]
        if len(matches)!=1:raise ValueError('Nao foi encontrado exatamente um pacote: '+pattern)
        asset=matches[0];checksum=next(a for a in release['assets'] if a['name']==asset['name']+'.sha256')
        with urllib.request.urlopen(checksum['browser_download_url'],timeout=30) as response:text=response.read(2048).decode('ascii')
        digest=text.split()[0].lower()
        if asset.get('digest') and asset['digest']!='sha256:'+digest:raise ValueError('Hash publicado nao corresponde ao asset do GitHub.')
        return dict(url=asset['browser_download_url'],version=release['tag_name'],code=code,compatibility=compat,size=asset['size'],sha256=digest,notes=notes)
    compat=meta['compatibility']
    windows=row(pc,r'Nordeluna-PC-.*-Completo\.zip',args.pc_code,compat)
    repair_asset=next((a for a in pc['assets'] if a['name'].endswith('-Completo.zip.repair.json')),None)
    if repair_asset:
        with urllib.request.urlopen(repair_asset['browser_download_url'],timeout=40) as response:raw=response.read(8*1024*1024+1)
        if len(raw)>8*1024*1024:raise ValueError('Indice de reparacao grande demais')
        digest=hashlib.sha256(raw).hexdigest()
        if repair_asset.get('digest') and repair_asset['digest']!='sha256:'+digest:raise ValueError('Indice publicado corrompido')
        repair=json.loads(raw)
        if repair.get('schema')!=1 or repair.get('platform')!='windows' or repair.get('archive_sha256')!=windows['sha256'] or repair.get('archive_size')!=windows['size']:raise ValueError('Indice de outra build')
        repair.update(code=args.pc_code,archive_url=windows['url'])
        signed=(json.dumps(signer.sign_payload(repair),ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')
        name=repair_asset['name'].removesuffix('.json')+'.signed.json'
        existing=next((a for a in pc['assets'] if a['name']==name),None)
        headers={'Authorization':'Bearer '+client.token,'User-Agent':'Nordeluna-Publisher','Accept':'application/vnd.github+json'}
        signed_hash=hashlib.sha256(signed).hexdigest()
        if existing and existing.get('digest')=='sha256:'+signed_hash:uploaded=existing
        else:
            if existing:
                request=urllib.request.Request('https://api.github.com/repos/'+REPOSITORY+'/releases/assets/'+str(existing['id']),method='DELETE',headers=headers)
                with client.opener.open(request,timeout=30):pass
            upload=pc['upload_url'].split('{',1)[0]+'?'+urllib.parse.urlencode({'name':name})
            if not upload.startswith('https://uploads.github.com/'):raise ValueError('Destino de upload invalido')
            request=urllib.request.Request(upload,data=signed,method='POST',headers=dict(headers,**{'Content-Type':'application/json'}))
            with client.opener.open(request,timeout=60) as response:uploaded=json.load(response)
        windows['repair']=dict(url=uploaded['browser_download_url'],size=len(signed),sha256=signed_hash)
    stable=row(android,r'Nordeluna-Android-arm64-.*\.apk',args.android_code,compat)
    data=dict(schema=1,channels=dict(stable=dict(windows=windows,android=stable)))
    if not args.stable_only:
        spec=importlib.util.spec_from_file_location('tester_release',ROOT/'scripts/tester-build-tools.py');tester=importlib.util.module_from_spec(spec);spec.loader.exec_module(tester)
        protected=tester.private_release(pc,android,args.pc_code,args.android_code,compat,notes)
        private_output=ROOT/'.cache/testers/publicacao-testers.json';private_output.parent.mkdir(parents=True,exist_ok=True)
        private_output.write_text(json.dumps(protected,ensure_ascii=False),encoding='utf-8')
        print('Publicacao privada preparada. Importe no painel Testers; nao compartilhe esse JSON.')
    output=ROOT/'public/launcher/releases.json';output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(signer.sign(data),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Catalogo publico estavel conferido e assinado. Testers nunca entram no catalogo publico.')
    if args.publish:
        git('add','--','public/launcher/releases.json')
        git('commit','-m','Publish signed PC and Android launcher catalogue')
        git('push','origin','main')
        print('Catalogo publicado. Os jogadores ja podem consultar pelo launcher.')


if __name__=='__main__':main()
