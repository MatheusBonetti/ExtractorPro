Dim shell, fso, pasta
Set shell = CreateObject("WScript.Shell")
Set fso   = CreateObject("Scripting.FileSystemObject")
pasta     = fso.GetParentFolderName(WScript.ScriptFullName)
shell.Run "pythonw """ & pasta & "\Iniciar.pyw""", 0, False
