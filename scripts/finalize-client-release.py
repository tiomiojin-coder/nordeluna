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

from updater_core import ROOT,GitHub,git


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pc-tag',default='pc-1.1.1');parser.add_argument('--android-tag',default='android-1.14')
    parser.add_argument('--pc-code',type=int,default=111);parser.add_argument('--android-code',type=int,default=21)
    parser.add_argument('--pc-commit');parser.add_argument('--android-commit')
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
    notes=(ROOT/'docs/release-1.14.md').read_text(encoding='utf-8')
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
    stable=row(android,r'Nordeluna-Android-arm64-.*\.apk',args.android_code,compat)
    testers=row(android,r'Nordeluna-Android-testers-arm64-.*\.apk',args.android_code,compat+'-testers')
    beta=dict(windows);beta['compatibility']+='-testers'
    data=dict(schema=1,channels=dict(stable=dict(windows=windows,android=stable),testers=dict(windows=beta,android=testers)))
    output=ROOT/'public/launcher/releases.json';output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(signer.sign(data),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Catalogo conferido e assinado. Downloads estavel e testers prontos.')
    if args.publish:
        git('add','--','public/launcher/releases.json')
        git('commit','-m','Publish signed PC and Android launcher catalogue')
        git('push','origin','main')
        print('Catalogo publicado. Os jogadores ja podem consultar pelo launcher.')


if __name__=='__main__':main()
