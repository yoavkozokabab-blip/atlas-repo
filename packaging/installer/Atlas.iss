; Atlas — Windows installer (Inno Setup 6, Phase 152)
#include "generated_version.iss"

#define MyAppName "Atlas"
#define MyAppPublisher "Atlas"
#define MyAppURL "https://github.com/atlas"
#define MyAppExeName "Atlas.exe"

[Setup]
AppId={{A7B4E2C1-9F3D-4A8B-8C2E-1D5F6A9B0C3E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\Atlas
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=Atlas_Setup
SetupIconFile=assets\atlas.ico
; Phase 155 — show plain-language beta + install notes before installing.
InfoBeforeFile=install_notes.txt
AppComments=Atlas (Windows beta). Self-contained — no Python required to use the installer.
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
VersionInfoVersion={#MyAppVersionInfo}
VersionInfoProductVersion={#MyAppVersionInfo}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Atlas Repository Intelligence
VersionInfoTextVersion={#MyAppVersion} ({#MyBuildDate}) {#MyCommitHash}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: checkedonce

[Files]
Source: "staging\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\Launch {#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\.jarvis_desktop"
Type: filesandordirs; Name: "{localappdata}\Atlas\desktop_data"
