' Atlas — silent launcher (no console window)
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = dir
If fso.FileExists(dir & "\Atlas.exe") Then
  shell.Run """" & dir & "\Atlas.exe""", 1, False
Else
  shell.Run "cmd /c """ & dir & "\Launch Atlas.bat""", 0, False
End If
