$ErrorActionPreference = 'Stop'
$syncRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonwPath = (Get-Command pythonw.exe).Source
$syncPath = Join-Path $PSScriptRoot 'sync.py'
$action = New-ScheduledTaskAction -Execute $pythonwPath -Argument ('"' + $syncPath + '" --watch') -WorkingDirectory $syncRoot
$userName = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $userName
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName 'Yanfolio-PrivateSourceSync' -Action $action -Trigger $trigger -Settings $settings -User $userName -RunLevel Limited -Force | Out-Null
Start-ScheduledTask -TaskName 'Yanfolio-PrivateSourceSync'

