"""Build a shareable Windows installer without editing the source game or saves."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zlib
import importlib.util
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from updater_core import DEFAULT_GAME, ROOT, inventory


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def distributable(name):
    parts = Path(name).parts
    if len(parts)>1 and parts[0]=='Plugins' and parts[1]=='New Animation Editor BETA':
        return False
    if any(p.lower() in {'tests', 'editor'} for p in parts[:-1]):
        return False
    return not any(p.startswith('.') or p in {'__pycache__', 'Saves', 'Screenshots'} for p in parts) and Path(name).suffix.lower() not in {'.log', '.py', '.pyc', '.pyi', '.ps1', '.bat', '.cmd', '.zip', '.rar', '.bak', '.tmp', '.sqlite', '.db'}


def pc_update_source(source):
    """Keep signed downloads/rollback intact; accept the PC's own factory hashes."""
    needle = "old[target] || row['base_sha256']"
    if source.count(needle) != 1:
        raise ValueError('O atualizador mudou. Revise a integração PC antes de distribuir.')
    helper = '''      def pc_factory_hash(target)
        @pc_factory ||= read_json('Data/PCContentBase.json')
        raise Error,'Base PC incompativel.' unless @pc_factory['base']==BASE
        value=@pc_factory.fetch('files').fetch(target,nil)
        raise Error,'Hash PC invalido.' unless value.nil? || (value.is_a?(String) && value.match?(/\\A[0-9a-f]{64}\\z/))
        value
      end
'''
    return source.replace('    class << self\n', '    class << self\n' + helper, 1).replace(needle, "old[target] || pc_factory_hash(target) || row['base_sha256']")


def integrate_pc_updates(output, copied, public):
    from plugin_tools import Ruby
    sys.path.insert(0, str(ROOT))
    from server.updates import allowed_path
    factory = {'base': public['base'], 'files': {name: digest(output / name) for name in copied if allowed_path(name)}}
    (output / 'Data/PCContentBase.json').write_text(json.dumps(factory, separators=(',', ':')), encoding='utf-8')
    path = output / 'Plugins/Nordeluna Online/028_ContentUpdates.rb'
    source = pc_update_source(path.read_text(encoding='utf-8'))
    ruby = Ruby(output)
    ruby.evaluate('RubyVM::InstructionSequence.compile([%s].pack("H*").force_encoding("UTF-8")); "OK"' % json.dumps(source.encode().hex()))
    bundle_path = output / 'Data/PluginScripts.rxdata'
    code = '''
bundle=Marshal.load([%s].pack('H*'))
before=Marshal.dump(bundle.reject { |entry| entry[0]=='Nordeluna Online' })
plugin=bundle.find { |entry| entry[0]=='Nordeluna Online' }
raise 'Online ausente' unless plugin
entry=plugin[2].select { |row| row[0].end_with?('028_ContentUpdates.rb') }
raise 'Atualizador ausente/duplicado' unless entry.length==1
entry[0][1]=[%s].pack('H*')
raise 'Outros plugins alterados' unless before==Marshal.dump(bundle.reject { |item| item[0]=='Nordeluna Online' })
Marshal.dump(bundle).unpack1('H*')
''' % (json.dumps(bundle_path.read_bytes().hex()), json.dumps(zlib.compress(source.encode()).hex()))
    bundle_path.write_bytes(bytes.fromhex(ruby.evaluate(code)))
    path.write_text(source, encoding='utf-8')


def stage(game, output):
    files = inventory(game)
    for name in ('Game.exe', 'RGSS104E.dll', 'x64-msvcrt-ruby310.dll', 'zlib1.dll'):
        path = game / name
        if not path.is_file():
            raise ValueError('Arquivo obrigatório ausente: ' + name)
        stat = path.stat()
        files[name] = (stat.st_size, stat.st_mtime_ns)
    bridge = 'Plugins/Nordeluna Online/bridge/WindowsHttpBridge-2.exe'
    if bridge not in files:
        raise ValueError('Transporte online Windows ausente.')
    copied = []
    for index, (name, original) in enumerate(sorted(files.items()), 1):
        if not distributable(name):
            continue
        source, target = game / name, output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if (source.stat().st_size, source.stat().st_mtime_ns) != original:
            raise ValueError('O projeto mudou durante a cópia. Feche o jogo/editor e tente novamente.')
        copied.append(name)
        if index % 2000 == 0:
            print(f'Copiando arquivos: {index}/{len(files)}', flush=True)
    # Keep the installed identity stable and never carry the creator's preferences.
    ini = output / 'Game.ini'
    text = ini.read_text(encoding='utf-8-sig')
    ini.write_text(re.sub(r'(?m)^Title=[^\r\n]*', 'Title=Pokemon Nordeluna', text), encoding='utf-8')
    config = output / 'mkxp.json'
    config.write_text(re.sub(r'("windowTitle"\s*:\s*)"[^"]*"', r'\1"Pokémon Nordeluna"', config.read_text(encoding='utf-8')), encoding='utf-8')
    public = json.loads((ROOT / 'server/content-key.json').read_text())
    plugin = (output / 'Plugins/Nordeluna Online/028_ContentUpdates.rb').read_text(encoding='utf-8')
    if public['base'] not in plugin or public['n'] not in plugin:
        raise ValueError('A identidade do atualizador não corresponde à chave pública do servidor.')
    integrate_pc_updates(output, copied, public)
    copied.append('Data/PCContentBase.json')
    spec=importlib.util.spec_from_file_location('launcher_builder',ROOT/'scripts/build-client-launcher.py')
    launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
    launcher.build(output)
    manifest = {'created': datetime.now(timezone.utc).isoformat(), 'content_base': public['base'],
        'files': {name: digest(output / name) for name in copied}}
    (output / 'pc-package.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', type=Path, default=DEFAULT_GAME)
    parser.add_argument('--compiler', type=Path, default=ROOT / '.cache/inno/compiler/ISCC.exe')
    parser.add_argument('--version', default='1.1.0')
    args = parser.parse_args()
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:\.\d+)?', args.version):
        parser.error('Use uma versão numérica, como 1.0.0.')
    if not args.compiler.is_file():
        parser.error('Instale o Inno Setup e indique --compiler caminho/ISCC.exe.')
    # Unique build directory: do not recursively remove existing output or player data.
    staging = ROOT / 'build/pc' / ('source-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f'))
    print('Preparando cópia de distribuição...', flush=True)
    manifest = stage(args.game.resolve(), staging)
    print(f"Conferidos {len(manifest['files'])} arquivos. Compilando instalador...", flush=True)
    subprocess.run([str(args.compiler.resolve()), '/Qp', f'/DGameSource={staging}',
                    f'/DAppVersion={args.version}', str(ROOT / 'windows/Nordeluna.iss')], check=True)
    installer = ROOT / 'build/pc' / f'Nordeluna-PC-{args.version}-Setup.exe'
    installer.with_suffix('.exe.sha256').write_text(digest(installer) + '  ' + installer.name + '\n', encoding='ascii')
    full=ROOT/'build/pc'/f'Nordeluna-PC-{args.version}-Completo.zip'
    print('Preparando atualização completa para o launcher...',flush=True)
    with zipfile.ZipFile(full,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as archive:
        for name in manifest['files']:
            archive.write(staging/name,name)
        archive.write(staging/'pc-package.json','pc-package.json')
    full.with_suffix('.zip.sha256').write_text(digest(full)+'  '+full.name+'\n',encoding='ascii')
    print('Instalador pronto: ' + str(installer), flush=True)


if __name__ == '__main__':
    main()
