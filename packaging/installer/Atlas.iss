; Atlas — Windows installer (Inno Setup 6, Phase 152)
#include "generated_version.iss"

#define MyAppName "Atlas"
#define MyAppPublisher "Atlas"
#define MyAppURL "https://github.com/yoavkozokabab-blip/atlas-repo"
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
; Phase 155 — show plain-language install notes before installing.
InfoBeforeFile=install_notes.txt
AppComments=Atlas for Windows. Self-contained — no Python required to use the installer.
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
; Installer-update flow: suppress Inno's default "files in use" / Restart Manager
; dialogs and generic technical errors. A dedicated [Code] flow (PrepareToInstall)
; detects and closes a running Atlas with product-friendly messaging instead.
CloseApplications=no
RestartApplications=no
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

; Atlas repository scans, account/session state, settings and history are user
; data, not installer payload. They are intentionally absent from [Files] and
; intentionally excluded from uninstall deletion, so installs, in-place updates,
; and uninstalls never overwrite or delete a user's repository memory.

[Code]
{ ============================================================================
  Running-application update flow.

  Detects a running Atlas before files are copied and shows a dedicated dialog
  ("Atlas is currently running") with four actions: close automatically, retry,
  open Task Manager instructions, or cancel. If automatic close fails, the same
  dialog explains how to close Atlas manually and shows the exact process name.
  No generic installer "file in use" error is ever shown.
  ============================================================================ }

#include "running_app_flow.iss"

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if IsAtlasRunning() then
  begin
    if not EnsureAtlasClosed() then
      { User cancelled. Return a clear, non-technical instruction (shown instead
        of any generic "file in use" error) and stop the update cleanly. }
      Result := 'Update paused: Atlas is still running.' + #13#10 + #13#10 +
                'Please close Atlas, then run this installer again.';
  end;
end;
