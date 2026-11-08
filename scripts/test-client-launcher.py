"""Run the real Windows launcher core without opening UI or touching player saves."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
if os.name!='nt':
    print('Windows launcher core is tested on the Windows build runner.')
    raise SystemExit(0)
with tempfile.TemporaryDirectory(prefix='nordeluna-client-test-') as temporary:
    root=Path(temporary);key=root/'Keys.cs'
    modulus=json.loads((ROOT/'server/content-key.json').read_text(encoding='utf-8'))['n']
    key.write_text('namespace Nordeluna { static class LauncherKeys { public const string Modulus="'+modulus+'"; public const int Code=110; } }',encoding='utf-8')
    compiler=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    exe=root/'test.exe'
    subprocess.run([str(compiler),'/nologo','/codepage:65001','/target:exe','/main:ClientLauncherTest','/reference:System.Windows.Forms.dll',
        '/reference:System.Drawing.dll','/reference:System.Web.Extensions.dll','/reference:System.IO.Compression.dll',
        '/reference:System.IO.Compression.FileSystem.dll','/out:'+str(exe),str(ROOT/'windows/Launcher.cs'),str(ROOT/'scripts/fixtures/ClientLauncherTest.cs'),str(key)],check=True)
    subprocess.run([str(exe),str(root/'data')],check=True,timeout=60)
