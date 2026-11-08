"""Install only the local battle box integration and assets, with file backups."""
import hashlib
import json
import shutil
from datetime import datetime, timezone

from plugin_tools import DEFAULT_GAME, ROOT

game = DEFAULT_GAME.resolve()
plugins = (game / 'Plugins').resolve()
backup = plugins / '.backups' / ('battle-boxes-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f'))
backup.mkdir(parents=True)
files = []
for folder, names in {
    'Customizable Battle UI': ['meta.txt', '004_DataBoxStyles.rb'],
    'Nordeluna CBUI Book': ['meta.txt', '001_Compatibility.rb'],
}.items():
    for name in names:
        files.append(ROOT / 'game-plugins' / folder / name)
files.extend((ROOT / 'game-plugins/Customizable Battle UI/assets/databoxes').rglob('*'))
files = [p for p in files if p.is_file()]
hashes = lambda: {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (game / 'Data').glob('*')
                  if p.is_file() and p.name != 'PluginScripts.rxdata'}
before = hashes()
installed = []
try:
    for source in files:
        rel = source.relative_to(ROOT / 'game-plugins')
        destination = (plugins / rel).resolve()
        if not destination.is_relative_to(plugins):
            raise RuntimeError('Destination outside Plugins')
        if destination.is_file():
            saved = backup / rel
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, saved)
        else:
            saved = None
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + '.styles-tmp')
        temporary.write_bytes(source.read_bytes())
        temporary.replace(destination)
        installed.append((destination, saved))
    if hashes() != before:
        raise RuntimeError('Game data changed during installation; source changes rolled back')
except Exception:
    for destination, saved in reversed(installed):
        if saved:
            shutil.copy2(saved, destination)
        else:
            destination.unlink(missing_ok=True)
    raise
(backup / 'manifest.json').write_text(json.dumps({
    'files': [str(p.relative_to(plugins)) for p, _ in installed],
    'data_sha256': before,
}, indent=2), encoding='utf-8')
print('Installed', len(installed), 'files; game data unchanged.')
print('Backup:', backup)
