#define MyAppName "Nexyra CRM"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Nexyra"
#define MyAppExeName "NexyraCRM.exe"

[Setup]
AppId={{A275BFA1-5C47-47B2-A41F-79FC33E05220}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppComments=Nexyra CRM Desktop
DefaultDirName={localappdata}\Programs\Nexyra CRM
DefaultGroupName=Nexyra CRM
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=NexyraCRM_Setup_1.0.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
UninstallDisplayName=Nexyra CRM
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
VersionInfoVersion=1.0.0.0
VersionInfoCompany=Nexyra
VersionInfoDescription=Nexyra CRM Desktop
VersionInfoProductName=Nexyra CRM
VersionInfoProductVersion=1.0.0

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "..\dist\NexyraCRM.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Nexyra CRM"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Nexyra CRM"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos adicionais:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir Nexyra CRM"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
