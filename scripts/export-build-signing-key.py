"""One-time encrypted migration of the existing Android signing cache."""
import argparse
import hashlib
import json
from pathlib import Path
import secrets

ROOT=Path(__file__).resolve().parents[1]


def encrypt(data,public):
    if not 0<len(data)<=32768:raise ValueError('Invalid keystore size')
    blocks=[]
    for offset in range(0,len(data),200):
        body=data[offset:offset+200];padding=bytearray()
        while len(padding)<253-len(body):
            padding.extend(b for b in secrets.token_bytes(256) if b)
        encoded=b'\0\2'+bytes(padding[:253-len(body)])+b'\0'+body
        blocks.append(f'{pow(int.from_bytes(encoded,"big"),65537,int(public["n"],16)):0512x}')
    return dict(schema=1,key=hashlib.sha256(public['n'].encode()).hexdigest(),blocks=blocks)


def decrypt(envelope,private):
    if envelope.get('schema')!=1 or envelope.get('key')!=hashlib.sha256(private['n'].encode()).hexdigest() or not 1<=len(envelope.get('blocks',[]))<=164:raise ValueError('Invalid encrypted keystore')
    output=bytearray()
    for block in envelope['blocks']:
        if len(block)!=512:raise ValueError('Invalid encrypted block')
        raw=pow(int(block,16),int(private['d'],16),int(private['n'],16)).to_bytes(256,'big');separator=raw.find(b'\0',2)
        if raw[:2]!=b'\0\2' or separator<10:raise ValueError('Invalid encrypted padding')
        output.extend(raw[separator+1:])
    if len(output)>32768:raise ValueError('Invalid decrypted size')
    return bytes(output)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('keystore',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
    data=encrypt(args.keystore.read_bytes(),json.loads((ROOT/'server/content-key.json').read_text(encoding='utf-8')))
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(data),encoding='utf-8')
    print('Encrypted signing-key migration prepared. No plaintext exported.')
