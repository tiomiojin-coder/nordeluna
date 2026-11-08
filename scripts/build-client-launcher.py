"""Compile the Windows launcher with the pinned public verification key."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from updater_core import ROOT


def build(output, code=111):
    output.mkdir(parents=True, exist_ok=True)
    modulus=json.loads((ROOT/'server/content-key.json').read_text(encoding='utf-8'))['n']
    key=ROOT/'build/launcher/LauncherKeys.cs';key.parent.mkdir(parents=True,exist_ok=True)
    key.write_text('namespace Nordeluna { static class LauncherKeys { public const string Modulus="'+modulus+'"; public const int Code='+str(code)+'; } }',encoding='utf-8')
    compiler=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    subprocess.run([str(compiler),'/nologo','/codepage:65001','/target:winexe','/platform:x64','/optimize+',
        '/reference:System.Windows.Forms.dll','/reference:System.Drawing.dll','/reference:System.Web.Extensions.dll',
        '/reference:System.IO.Compression.dll','/reference:System.IO.Compression.FileSystem.dll',
        '/win32icon:'+str(ROOT/'windows/nordeluna.ico'),'/out:'+str(output/'Nordeluna.exe'),str(ROOT/'windows/Launcher.cs'),str(key)],check=True)
    return output/'Nordeluna.exe'


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'build/launcher');parser.add_argument('--code',type=int,default=111)
    args=parser.parse_args();print(build(args.output,args.code))
