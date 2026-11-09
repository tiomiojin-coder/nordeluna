"""Encrypt distributable test builds; only the creator can unwrap their keys."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import secrets
import sys

ROOT=Path(__file__).resolve().parents[1]


def module(name, file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/file)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


def lock(source, output, key=None, iv=None):
    sys.path.insert(0,str(ROOT/'.cache/tester-crypto'))
    from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
    from cryptography.hazmat.primitives import padding
    key=key or secrets.token_bytes(32);iv=iv or secrets.token_bytes(16)
    cipher=Cipher(algorithms.AES(key),modes.CBC(iv)).encryptor();pad=padding.PKCS7(128).padder()
    output.parent.mkdir(parents=True,exist_ok=True)
    plain=hashlib.sha256();size=0
    with source.open('rb') as src,output.open('wb') as dst:
        dst.write(iv)
        while body:=src.read(1024*1024):
            plain.update(body);size+=len(body);dst.write(cipher.update(pad.update(body)))
        dst.write(cipher.update(pad.finalize())+cipher.finalize())
    public=json.loads((ROOT/'server/content-key.json').read_text(encoding='utf-8'))
    wrapped=module('tester_wrap','export-build-signing-key.py').encrypt(key,public)
    with output.open('rb') as body:digest=hashlib.file_digest(body,'sha256').hexdigest()
    meta=dict(schema=1,size=output.stat().st_size,sha256=digest,plain=dict(size=size,sha256=plain.hexdigest()),wrapped=wrapped)
    output.with_suffix(output.suffix+'.json').write_text(json.dumps(meta,separators=(',',':')),encoding='utf-8')
    print('Pacote de testes protegido:',output.name)  # No plaintext keys in CI logs.
    return meta


def fixture(folder):
    folder.mkdir(parents=True,exist_ok=True);source=folder/'test-plain.bin';source.write_bytes(bytes(range(256))*1025+b'tester fixture')
    key=bytes(range(32));row=lock(source,folder/'test-locked.bin',key,bytes(range(16)))
    row['encrypted']=True
    (folder/'test-row.json').write_text(json.dumps(row),encoding='utf-8')


def private_release(pc,android,pc_code,android_code,compat,notes):
    """Asset metadata is public; only this local owner process unwraps AES keys."""
    import urllib.request
    private=json.loads((ROOT/'.cache/content-updates/private-key.json').read_text(encoding='utf-8'))
    wrapper=module('tester_unwrap','export-build-signing-key.py');signer=module('tester_sign','client-release-tools.py')
    rows={};keys={}
    for platform,release,pattern,code in [('windows',pc,'-Completo.zip.locked',pc_code),('android',android,'-testers-arm64-',android_code)]:
        matches=[a for a in release['assets'] if (a['name'].endswith(pattern) if platform=='windows' else pattern in a['name'] and a['name'].endswith('.apk.locked'))]
        if len(matches)!=1:raise ValueError('Pacote protegido ausente: '+platform)
        asset=matches[0];meta_asset=next(a for a in release['assets'] if a['name']==asset['name']+'.json')
        with urllib.request.urlopen(meta_asset['browser_download_url'],timeout=30) as response:raw=response.read(16385)
        if len(raw)>16384:raise ValueError('Metadados grandes demais')
        meta=json.loads(raw)
        if meta['size']!=asset['size'] or asset.get('digest')!='sha256:'+meta['sha256']:raise ValueError('Pacote protegido nao confere com GitHub')
        key=wrapper.decrypt(meta['wrapped'],private)
        if len(key)!=32:raise ValueError('Chave invalida')
        keys[platform]=key.hex()
        rows[platform]=dict(url=asset['browser_download_url'],size=meta['size'],sha256=meta['sha256'],plain=meta['plain'],encrypted=True,code=code,version=release['tag_name'],compatibility=compat+'-testers',notes=notes)
    return dict(catalog=signer.sign(dict(schema=1,channels=dict(testers=rows))),keys=keys)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('output',type=Path,nargs='?');parser.add_argument('--fixture',action='store_true')
    args=parser.parse_args()
    if args.fixture:fixture(args.source)
    elif args.output:lock(args.source,args.output)
    else:parser.error('Informe o arquivo de saída')
