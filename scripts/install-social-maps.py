"""Install the already validated LOCAL map pack with a backup and rollback."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from updater_core import DEFAULT_GAME,ROOT

OUT=ROOT/'build/social-maps'


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    game=DEFAULT_GAME.resolve(strict=True)
    report=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    validation=json.loads((OUT/'validation.json').read_text(encoding='utf-8'))
    if validation['errors']:raise RuntimeError('Map validation failed; no installation performed')
    for executable in ['RPGXP.exe','Game.exe']:
        result=subprocess.run(['tasklist','/FI','IMAGENAME eq '+executable,'/FO','CSV','/NH'],capture_output=True,check=True)
        if executable.lower().encode() in result.stdout.lower():
            raise RuntimeError('Feche o RPG Maker XP e o jogo antes de instalar. Nenhum arquivo foi alterado.')
    for relative,expected in report['source_files'].items():
        if digest(game/relative)!=expected:raise RuntimeError('O projeto mudou desde a preparacao: '+relative)
    files=report['install_files']
    allowed={'Data/Map039.rxdata','Data/Map040.rxdata','Data/Map041.rxdata','Data/MapInfos.rxdata','Data/map_metadata.dat',
             'Data/PluginScripts.rxdata','PBS/map_metadata.txt','Plugins/Nordeluna Online/016_IdentityAndAreas.rb','Plugins/Nordeluna Online/020_SocialMaps.rb'}
    if set(files)!=allowed:raise RuntimeError('Unexpected files in map pack')
    new_files={'Data/Map040.rxdata','Data/Map041.rxdata','Plugins/Nordeluna Online/020_SocialMaps.rb'}
    for relative in new_files:
        if (game/relative).exists():raise RuntimeError('New file already exists: '+relative)
    for relative,expected in files.items():
        if digest(OUT/relative)!=expected:raise RuntimeError('Changed package file: '+relative)
        if not (game/relative).resolve().is_relative_to(game):raise RuntimeError('Destination outside game folder')
    backup=ROOT/'.cache/social-maps-backups'/datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir(parents=True)
    originals={}
    for relative in files:
        path=game/relative
        originals[relative]=path.read_bytes() if path.exists() else None
        if originals[relative] is not None:
            destination=backup/relative;destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes(originals[relative])
    applied=[]
    try:
        for relative in files:
            destination=game/relative
            destination.parent.mkdir(parents=True,exist_ok=True)
            temporary=destination.with_name('.'+destination.name+'.social-maps-tmp')
            temporary.write_bytes((OUT/relative).read_bytes())
            temporary.replace(destination)
            applied.append(relative)
        for relative,expected in files.items():
            if digest(game/relative)!=expected:raise RuntimeError('Post-install verification failed: '+relative)
    except Exception:
        for relative in reversed(applied):
            destination=game/relative
            if originals[relative] is None:destination.unlink()
            else:destination.write_bytes(originals[relative])
        raise
    installed=dict(game=str(game),backup=str(backup),created_files=sorted(new_files),installed=files)
    (backup/'installation.json').write_text(json.dumps(installed,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'installation.json').write_text(json.dumps(installed,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(installed_maps=[39,40,41],backup=str(backup),files=len(files),remote_actions=False),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
