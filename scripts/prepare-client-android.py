"""Add the launch screen after applying the pinned engine patch."""
import argparse
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
ANDROID='{http://schemas.android.com/apk/res/android}'


def prepare(engine):
    main=engine/'android/app/src/main'
    folder=main/'java/com/mkxpz/launcher';folder.mkdir(parents=True,exist_ok=True)
    for name in ('ClientFiles.java','ClientLauncher.java','ClientUpdateProvider.java'):
        shutil.copyfile(ROOT/'android'/name,folder/name)
    key=json.loads((ROOT/'server/content-key.json').read_text(encoding='utf-8'))['n']
    (folder/'LauncherKeys.java').write_text('package com.mkxpz.launcher; final class LauncherKeys { static final String MODULUS="'+key+'"; }',encoding='utf-8')
    manifest=main/'AndroidManifest.xml';ET.register_namespace('android','http://schemas.android.com/apk/res/android');tree=ET.parse(manifest);doc=tree.getroot();app=doc.find('application')
    if app.find("activity[@"+ANDROID+"name='com.mkxpz.launcher.ClientLauncher']") is not None:raise ValueError('Launcher ja preparado')
    ET.SubElement(doc,'uses-permission',{ANDROID+'name':'android.permission.REQUEST_INSTALL_PACKAGES'})
    queries=ET.SubElement(doc,'queries')
    for package in ('com.tiomi.nordeluna','com.tiomi.nordeluna.testers'):ET.SubElement(queries,'package',{ANDROID+'name':package})
    game=app.find("activity[@"+ANDROID+"name='com.mkxpz.MainActivity']")
    if game is None:raise ValueError('Aplique nordeluna.patch primeiro')
    for child in list(game):
        if child.tag=='intent-filter':game.remove(child)
    game.set(ANDROID+'exported','false')
    launcher=ET.SubElement(app,'activity',{ANDROID+'name':'com.mkxpz.launcher.ClientLauncher',ANDROID+'exported':'true',ANDROID+'label':'@string/app_name'})
    launch=ET.SubElement(launcher,'intent-filter');ET.SubElement(launch,'action',{ANDROID+'name':'android.intent.action.MAIN'})
    for cat in ('android.intent.category.LAUNCHER','android.intent.category.LEANBACK_LAUNCHER'):ET.SubElement(launch,'category',{ANDROID+'name':cat})
    ET.SubElement(app,'provider',{ANDROID+'name':'com.mkxpz.launcher.ClientUpdateProvider',ANDROID+'authorities':'${applicationId}.updates',ANDROID+'exported':'false',ANDROID+'grantUriPermissions':'true'})
    tree.write(manifest,encoding='utf-8',xml_declaration=True)
    activity=main/'java/com/mkxpz/MainActivity.java';source=activity.read_text(encoding='utf-8')
    needle='        super.onCreate(savedInstanceState);'
    if source.count(needle)!=1:raise ValueError('Inicializacao da Activity mudou')
    source=source.replace(needle,needle+'\n        com.mkxpz.launcher.ClientLauncher.gameRunning = !mBrokenLibraries;')
    needle='    private void runSDLThread()\n    {'
    replacement=needle+'''
        if (!mStarted) {
            try { com.mkxpz.launcher.ClientLauncher.prepareGame(this, new File(GAME_PATH)); }
            catch (Exception error) {
                new AlertDialog.Builder(this).setTitle("Não foi possível preparar o save")
                    .setMessage("Os saves anteriores foram preservados. " + error.getMessage())
                    .setPositiveButton("Voltar", (dialog, which) -> finish()).show();
                return;
            }
        }
'''
    if source.count(needle)!=1:raise ValueError('Entrada SDL mudou. Revise o launcher.')
    source=source.replace(needle,replacement)
    needle='        return new File[] { gameFolder, dataDir };'
    if source.count(needle)!=1:raise ValueError('Raizes de save mudaram')
    source=source.replace(needle,'        return new File[] { com.mkxpz.launcher.ClientLauncher.selectedSaves(this) };')
    activity.write_text(source,encoding='utf-8')
    gradle=engine/'android/app/build.gradle';build=gradle.read_text(encoding='utf-8')
    needle='    defaultConfig {'
    if build.count(needle)!=1:raise ValueError('Configuracao Gradle mudou')
    build=build.replace(needle,'''    flavorDimensions "channel"
    productFlavors {
        stable { dimension "channel" }
        beta { dimension "channel"; applicationIdSuffix ".testers"; versionNameSuffix "-testers" }
    }
'''+needle)
    gradle.write_text(build,encoding='utf-8')
    beta=engine/'android/app/src/beta/res/values/client_channel.xml';beta.parent.mkdir(parents=True,exist_ok=True)
    beta.write_text('<resources><string name="app_name">Nordeluna Testers</string></resources>',encoding='utf-8')
    print('Launcher Android preparado:',engine)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('engine',type=Path);prepare(parser.parse_args().engine)
