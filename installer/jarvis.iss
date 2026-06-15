; Atlas - Windows installer (Inno Setup 6)
#define MyAppName "Atlas"
#define MyAppVersion "0.1.0-beta"
#define MyAppPublisher "Atlas"
#define MyAppURL "https://github.com/atlas"
#define MyAppExeName "Atlas.exe"

[Setup]
AppId={{A7B4E2C1-9F3D-4A8B-8C2E-1D5F6A9B0C3E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\Atlas
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\installer\output
OutputBaseFilename=Atlas_Setup
SetupIconFile=assets\jarvis.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: checkedonce

[Files]
Source: "..\staging\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Match the actual data-dir candidates resolved by jarvis_desktop/data_paths.py:
;   1) %USERPROFILE%\.jarvis_desktop  2) %LOCALAPPDATA%\Atlas\desktop_data
; (The old {userappdata}\.jarvis_desktop path was %APPDATA% and never matched, so
;  uninstall left user data behind.)
Type: filesandordirs; Name: "{%USERPROFILE}\.jarvis_desktop"
Type: filesandordirs; Name: "{localappdata}\Atlas"
