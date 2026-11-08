"""Create the signed, public release catalogue. The private key stays local."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import urllib.parse

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from server.updates import verify_signature,DIGEST_INFO


def validate(data):
    if data.get('schema')!=1 or not isinstance(data.get('channels'),dict):raise ValueError('Catalogo invalido')
    for channel,rows in data['channels'].items():
        if channel not in ('stable','testers') or not isinstance(rows,dict):raise ValueError('Canal invalido')
        for platform,row in rows.items():
            if platform not in ('windows','android'):raise ValueError('Plataforma invalida')
            if type(row.get('code')) is not int or row['code']<1:raise ValueError('Versao invalida')
            url=urllib.parse.urlparse(row.get('url',''))
            if url.scheme!='https' or not url.hostname or url.username or url.password:raise ValueError('Use um link HTTPS direto, sem credenciais')
            if type(row.get('size')) is not int or not 0<row['size']<=3*1024**3:raise ValueError('Tamanho invalido')
            if not isinstance(row.get('sha256'),str) or len(row['sha256'])!=64 or any(c not in '0123456789abcdef' for c in row['sha256']):raise ValueError('Hash invalido')
            if not isinstance(row.get('compatibility'),str) or not 1<=len(row['compatibility'])<=100:raise ValueError('Identidade online invalida')
            if not isinstance(row.get('notes'),str) or len(row['notes'])>6000:raise ValueError('Novidades grandes demais')
    return data


def sign(data,private=None):
    validate(data)
    private=private or ROOT/'.cache/content-updates/private-key.json'
    key=json.loads(private.read_text(encoding='utf-8'))
    public=json.loads((ROOT/'server/content-key.json').read_text(encoding='utf-8'))
    if key['n']!=public['n']:raise ValueError('Chave nao corresponde aos clientes')
    raw=json.dumps(data,ensure_ascii=False,separators=(',',':'))
    encoded=DIGEST_INFO+hashlib.sha256(raw.encode()).digest();block=b'\0\1'+b'\xff'*(256-len(encoded)-3)+b'\0'+encoded
    signature=f'{pow(int.from_bytes(block,"big"),int(key["d"],16),int(key["n"],16)):0512x}'
    verify_signature(raw,signature,public)
    return dict(manifest=raw,signature=signature)


def row(path,url,version,code,compatibility,notes):
    with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    return dict(url=url,version=version,code=code,compatibility=compatibility,notes=notes,size=path.stat().st_size,sha256=digest)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--channel',choices=['stable','testers'],default='stable')
    p.add_argument('--pc',type=Path,required=True);p.add_argument('--pc-url',required=True);p.add_argument('--apk',type=Path,required=True);p.add_argument('--apk-url',required=True)
    p.add_argument('--pc-version',default='1.1.1');p.add_argument('--pc-code',type=int,default=111);p.add_argument('--android-version',default='1.14.0');p.add_argument('--android-code',type=int,default=21)
    p.add_argument('--compatibility',required=True);p.add_argument('--notes',type=Path,required=True)
    p.add_argument('--output',type=Path,default=ROOT/'public/launcher/releases.json');args=p.parse_args()
    data={'schema':1,'channels':{}}
    if args.output.is_file():
        previous=json.loads(args.output.read_text(encoding='utf-8'))
        verify_signature(previous['manifest'],previous['signature'],json.loads((ROOT/'server/content-key.json').read_text(encoding='utf-8')))
        data=validate(json.loads(previous['manifest']))
    notes=args.notes.read_text(encoding='utf-8')
    if args.channel=='testers' and not args.compatibility.endswith('-testers'):args.compatibility+='-testers'
    data['channels'][args.channel]={'windows':row(args.pc,args.pc_url,args.pc_version,args.pc_code,args.compatibility,notes),'android':row(args.apk,args.apk_url,args.android_version,args.android_code,args.compatibility,notes)}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(sign(data),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Catalogo assinado:',args.output)


if __name__=='__main__':main()
