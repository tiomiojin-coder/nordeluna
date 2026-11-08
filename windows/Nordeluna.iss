#ifndef GameSource
  #error Defina GameSource usando scripts/build-pc-installer.py
#endif
#ifndef AppVersion
  #define AppVersion "1.1.0"
#endif

[Setup]
AppId={{D24A01A7-5589-4797-AC7C-1F0494BC767B}
AppName=Pokémon Nordeluna
AppVersion={#AppVersion}
AppPublisher=Equipe Nordeluna
DefaultDirName={localappdata}\Programs\Pokemon Nordeluna
DefaultGroupName=Pokémon Nordeluna
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\build\pc
OutputBaseFilename=Nordeluna-PC-{#AppVersion}-Setup
SetupIconFile=nordeluna.ico
UninstallDisplayIcon={app}\Nordeluna.ico
WizardStyle=modern
Compression=lzma2/fast
SolidCompression=yes
CloseApplications=no
RestartApplications=no
DisableProgramGroupPage=yes
InfoAfterFile=LEIA-ME.txt
UninstallDisplayName=Pokémon Nordeluna

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"

[Files]
Source: "{#GameSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs uninsneveruninstall; Excludes: "pc-package.json"
Source: "{#GameSource}\pc-package.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "nordeluna.ico"; DestDir: "{app}"; DestName: "Nordeluna.ico"; Flags: ignoreversion
Source: "LEIA-ME.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Pokémon Nordeluna"; Filename: "{app}\Nordeluna.exe"; WorkingDir: "{app}"; IconFilename: "{app}\Nordeluna.ico"
Name: "{autodesktop}\Pokémon Nordeluna"; Filename: "{app}\Nordeluna.exe"; WorkingDir: "{app}"; IconFilename: "{app}\Nordeluna.ico"; Tasks: desktopicon
Name: "{group}\Como atualizar o jogo"; Filename: "{app}\LEIA-ME.txt"

[Run]
Filename: "{app}\Nordeluna.exe"; WorkingDir: "{app}"; Description: "Abrir Pokémon Nordeluna"; Flags: nowait postinstall skipifsilent unchecked

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
  if ExpandConstant('{param:VERIFYONLY|0}') = '1' then
  begin
    // Compiler/loader smoke test: no installation and no registry writes.
    Result := False;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if FileExists(ExpandConstant('{app}\Game.exe')) then
    begin
      // Do not forcibly close the game, battles or trades.
      if not WizardSilent then
        if MsgBox('Feche o jogo antes de continuar para preservar a partida e as atualizações. O jogo está fechado?', mbConfirmation, MB_YESNO) <> IDYES then
          Result := 'Feche o jogo e tente novamente.';
    end;
  if Result = '' then
    if DirExists(ExpandConstant('{app}\.nordeluna-updates')) then
      if not RenameFile(ExpandConstant('{app}\.nordeluna-updates'),
        ExpandConstant('{app}\.nordeluna-updates-backup-') + GetDateTimeString('yyyymmddhhnnss', '-', ':')) then
        Result := 'Não foi possível preservar o conteúdo anterior. Feche o jogo e tente novamente.';
end;
