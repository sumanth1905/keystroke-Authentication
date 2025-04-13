Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")
scriptDir = objFSO.GetParentFolderName(WScript.ScriptFullName)

' Launch all required executables directly (no pythonw)
objShell.Run """" & scriptDir & "\Lockscreen.exe""", 0, False
objShell.Run """" & scriptDir & "\CheckUnlock.exe""", 0, False

Set objShell = Nothing
Set objFSO = Nothing