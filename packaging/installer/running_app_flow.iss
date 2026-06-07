{ ============================================================================
  Atlas — running-application update flow (shared Pascal code).

  Included by Atlas.iss (the real installer) and by the verification harness
  (_verify/running_app_flow_test.iss) so screenshots and tests exercise the
  exact shipped code.

  Detects a running Atlas before files are copied and shows a dedicated dialog
  ("Atlas is currently running") with four actions: close automatically, retry,
  open Task Manager instructions, or cancel. If automatic close fails, the same
  dialog explains how to close Atlas manually and shows the exact process name.
  No generic installer "file in use" error is ever shown.
  ============================================================================ }

const
  ATLAS_PROCESS = 'Atlas.exe';
  { Custom dialog results (kept away from built-in mrOk=1 / mrCancel=2). }
  RUN_CLOSE   = 101;
  RUN_RETRY   = 102;
  RUN_TASKMGR = 103;
  RUN_CANCEL  = 104;

function IsAtlasRunningViaTasklist(): Boolean;
var
  ResultCode: Integer;
  Content: AnsiString;
  TmpPath: String;
begin
  Result := False;
  TmpPath := ExpandConstant('{tmp}\atlas_proc_check.txt');
  if Exec(ExpandConstant('{cmd}'),
          '/C tasklist /FI "IMAGENAME eq ' + ATLAS_PROCESS + '" /NH > "' + TmpPath + '"',
          '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if LoadStringFromFile(TmpPath, Content) then
      Result := Pos(LowerCase(ATLAS_PROCESS), LowerCase(String(Content))) > 0;
  end;
  DeleteFile(TmpPath);
end;

function IsAtlasRunning(): Boolean;
var
  Locator, Service, Procs: Variant;
begin
  try
    Locator := CreateOleObject('WbemScripting.SWbemLocator');
    Service := Locator.ConnectServer('localhost', 'root\CIMV2');
    Procs := Service.ExecQuery('SELECT Name FROM Win32_Process WHERE Name=''' + ATLAS_PROCESS + '''');
    Result := (Procs.Count > 0);
  except
    { WMI unavailable on this machine — fall back to tasklist. }
    Result := IsAtlasRunningViaTasklist();
  end;
end;

function CloseAtlas(): Boolean;
var
  ResultCode, I: Integer;
begin
  { 1) Ask Atlas to close gracefully so it can release its local server + state. }
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/IM ' + ATLAS_PROCESS,
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  for I := 1 to 6 do
  begin
    if not IsAtlasRunning() then
    begin
      Result := True;
      Exit;
    end;
    Sleep(500);
  end;

  { 2) Force-close the whole process tree (server + any child Atlas.exe). }
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM ' + ATLAS_PROCESS,
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  for I := 1 to 6 do
  begin
    if not IsAtlasRunning() then
    begin
      Result := True;
      Exit;
    end;
    Sleep(500);
  end;

  Result := not IsAtlasRunning();
end;

procedure ShowTaskManagerInstructions();
begin
  MsgBox(
    'How to close Atlas using Task Manager:' + #13#10 + #13#10 +
    '1.  Press Ctrl + Shift + Esc to open Task Manager.' + #13#10 +
    '2.  Click the "Processes" tab.' + #13#10 +
    '3.  Find "' + ATLAS_PROCESS + '" (shown as "Atlas") in the list.' + #13#10 +
    '4.  Select it and click "End task".' + #13#10 + #13#10 +
    'When Atlas has closed, return to the installer and click Retry.',
    mbInformation, MB_OK);
end;

function ShowAtlasRunningDialog(FailedClose: Boolean): Integer;
var
  Form: TSetupForm;
  Title, Body, Proc: TNewStaticText;
  BtnClose, BtnRetry, BtnTaskMgr, BtnCancel: TNewButton;
  ML, CW, Y: Integer;
begin
  { CreateNew (not Create) builds the form without loading a DFM resource. }
  Form := TSetupForm.CreateNew(nil, 0);
  try
    if WizardForm <> nil then
    begin
      Form.Font.Name := WizardForm.Font.Name;
      Form.Font.Size := WizardForm.Font.Size;
    end;
    Form.BorderStyle := bsDialog;
    Form.Caption := 'Atlas is currently running';
    Form.ClientWidth := ScaleX(480);
    ML := ScaleX(22);
    CW := ScaleX(436);
    Y := ScaleY(18);

    Title := TNewStaticText.Create(Form);
    Title.Parent := Form;
    Title.Left := ML;
    Title.Top := Y;
    Title.Width := CW;
    Title.AutoSize := False;
    Title.Height := ScaleY(26);
    Title.Font.Style := [fsBold];
    Title.Font.Size := 12;
    Title.Caption := 'Atlas is currently running';
    Y := Y + ScaleY(36);

    Body := TNewStaticText.Create(Form);
    Body.Parent := Form;
    Body.Left := ML;
    Body.Top := Y;
    Body.Width := CW;
    Body.AutoSize := False;
    Body.WordWrap := True;
    if FailedClose then
    begin
      Body.Height := ScaleY(140);
      Body.Caption :=
        'We couldn''t close Atlas automatically.' + #13#10 + #13#10 +
        'Please close Atlas manually, then click Retry:' + #13#10 +
        '    1.  Press Ctrl + Shift + Esc to open Task Manager.' + #13#10 +
        '    2.  Find "Atlas.exe" in the Processes list.' + #13#10 +
        '    3.  Select it and click "End task".';
      Y := Y + ScaleY(146);

      Proc := TNewStaticText.Create(Form);
      Proc.Parent := Form;
      Proc.Left := ML;
      Proc.Top := Y;
      Proc.Width := CW;
      Proc.AutoSize := False;
      Proc.Height := ScaleY(20);
      Proc.Font.Style := [fsBold];
      Proc.Caption := 'Process name:    ' + ATLAS_PROCESS;
      Y := Y + ScaleY(30);
    end
    else
    begin
      Body.Height := ScaleY(40);
      Body.Caption := 'Atlas must be closed before the update can continue.';
      Y := Y + ScaleY(52);
    end;

    BtnClose := TNewButton.Create(Form);
    BtnClose.Parent := Form;
    BtnClose.Left := ML;
    BtnClose.Top := Y;
    BtnClose.Width := CW;
    BtnClose.Height := ScaleY(34);
    BtnClose.Caption := 'Close Atlas automatically';
    BtnClose.ModalResult := RUN_CLOSE;
    Y := Y + ScaleY(42);

    BtnRetry := TNewButton.Create(Form);
    BtnRetry.Parent := Form;
    BtnRetry.Left := ML;
    BtnRetry.Top := Y;
    BtnRetry.Width := CW;
    BtnRetry.Height := ScaleY(34);
    BtnRetry.Caption := 'Retry';
    BtnRetry.ModalResult := RUN_RETRY;
    Y := Y + ScaleY(42);

    BtnTaskMgr := TNewButton.Create(Form);
    BtnTaskMgr.Parent := Form;
    BtnTaskMgr.Left := ML;
    BtnTaskMgr.Top := Y;
    BtnTaskMgr.Width := CW;
    BtnTaskMgr.Height := ScaleY(34);
    BtnTaskMgr.Caption := 'Open Task Manager instructions';
    BtnTaskMgr.ModalResult := RUN_TASKMGR;
    Y := Y + ScaleY(42);

    BtnCancel := TNewButton.Create(Form);
    BtnCancel.Parent := Form;
    BtnCancel.Left := ML;
    BtnCancel.Top := Y;
    BtnCancel.Width := CW;
    BtnCancel.Height := ScaleY(34);
    BtnCancel.Caption := 'Cancel';
    BtnCancel.ModalResult := RUN_CANCEL;
    Y := Y + ScaleY(34);

    Form.ClientHeight := Y + ScaleY(16);
    Form.Position := poScreenCenter;
    if FailedClose then
      Form.ActiveControl := BtnRetry
    else
      Form.ActiveControl := BtnClose;

    Result := Form.ShowModal();
    if (Result <> RUN_CLOSE) and (Result <> RUN_RETRY) and (Result <> RUN_TASKMGR) then
      Result := RUN_CANCEL;
  finally
    Form.Free();
  end;
end;

function EnsureAtlasClosed(): Boolean;
var
  Choice: Integer;
  FailedClose: Boolean;
begin
  { Silent / unattended update: never block on a dialog — auto-close Atlas and
    proceed. If it cannot be closed, fail so the update aborts cleanly. }
  if WizardSilent() then
  begin
    Result := CloseAtlas();
    Exit;
  end;

  FailedClose := False;
  while IsAtlasRunning() do
  begin
    Choice := ShowAtlasRunningDialog(FailedClose);
    if Choice = RUN_CLOSE then
    begin
      if CloseAtlas() then
        FailedClose := False
      else
        FailedClose := True;
    end
    else if Choice = RUN_RETRY then
      FailedClose := False
    else if Choice = RUN_TASKMGR then
      ShowTaskManagerInstructions()
    else
    begin
      Result := False;
      Exit;
    end;
  end;
  Result := True;
end;
