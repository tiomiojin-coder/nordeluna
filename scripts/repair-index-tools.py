"""Index ZIP byte ranges for verified, selective Windows repair downloads."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile
import unicodedata

ROOT=Path(__file__).resolve().parents[1]
MUTABLE={'installed-client.json','client-repair.json'}


def repair_path(name):
    parts=name.split('/')
    if not name or '\\' in name or ':' in name or any(not p or p in ('.','..') or p.startswith('.') or p.endswith((' ','.')) for p in parts):return False
    if name in MUTABLE:return False
    if any(p.casefold()=='saves' for p in parts):return False
    import re
    if re.fullmatch(r'(?:Save_?\d*|Game)\.(?:rxdata|rvdata2?)',parts[-1],re.I):return False
    if parts[0] in ('Data','Graphics','Audio','Movies','Fonts','Plugins') and len(parts)>1:return True
    return name in ('Game.exe','Game.ini','mkxp.json','pc-package.json','RGSS104E.dll','x64-msvcrt-ruby310.dll','zlib1.dll','soundfont.sf2','achievements.dat')


def build_index(archive,output=None):
    rows=[];seen=set()
    with zipfile.ZipFile(archive) as packed,Path(archive).open('rb') as raw:
        for entry in packed.infolist():
            if entry.is_dir() or not repair_path(entry.filename):continue
            if entry.filename.casefold() in seen or entry.compress_type not in (0,8) or entry.flag_bits&1:raise ValueError('Unsupported repair ZIP entry')
            seen.add(entry.filename.casefold());raw.seek(entry.header_offset);header=raw.read(30)
            if header[:4]!=b'PK\x03\x04':raise ValueError('Invalid ZIP local header')
            names,extra=struct.unpack_from('<HH',header,26);offset=entry.header_offset+30+names+extra
            with packed.open(entry) as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
            rows.append(dict(path=entry.filename,size=entry.file_size,sha256=digest,offset=offset,packed_size=entry.compress_size,method=entry.compress_type,mutable=entry.filename=='mkxp.json'))
    with Path(archive).open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    data=dict(schema=1,platform='windows',archive_sha256=digest,archive_size=Path(archive).stat().st_size,files=rows)
    if output:Path(output).write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    return data


def android_manifest(source):
    rows=[]
    for file in sorted(source.rglob('*')):
        name=unicodedata.normalize('NFC',file.relative_to(source).as_posix())
        if not file.is_file() or not repair_path(name):continue
        with file.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        rows.append(dict(path=name,size=file.stat().st_size,sha256=digest,mutable=name=='mkxp.json'))
    return dict(schema=1,platform='android',files=rows)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive',type=Path);p.add_argument('output',type=Path);a=p.parse_args();build_index(a.archive,a.output)
