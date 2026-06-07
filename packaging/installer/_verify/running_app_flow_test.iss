; Atlas — running-application update-flow VERIFICATION HARNESS (not shipped).
; Reuses the exact shared dialog code from running_app_flow.iss so screenshots
; reflect the real installer. Shows a dialog state chosen by /state=normal|failed|taskmgr
; then leaves the wizard on screen for the capture tool to screenshot and close.
[Setup]
AppName=Atlas Update-Flow Test
AppVersion=1.0
DefaultDirName={tmp}\atlas_flow_test
OutputDir=.
OutputBaseFilename=RunningAppFlowTest
DisableWelcomePage=no
PrivilegesRequired=lowest
Uninstallable=no

[Code]
#include "..\running_app_flow.iss"

var
  GShown: Boolean;

procedure CurPageChanged(CurPageID: Integer);
var
  State: String;
begin
  if (CurPageID = wpWelcome) and (not GShown) then
  begin
    GShown := True;
    State := ExpandConstant('{param:state|normal}');
    if State = 'failed' then
      ShowAtlasRunningDialog(True)
    else if State = 'taskmgr' then
      ShowTaskManagerInstructions()
    else
      ShowAtlasRunningDialog(False);
  end;
end;
