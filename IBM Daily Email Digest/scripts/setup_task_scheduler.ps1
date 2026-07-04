<#
.SYNOPSIS
    Registers (or updates) a Windows Scheduled Task that runs the IBM Daily
    Email Digest every day at a fixed local time.

.USAGE
    Daily at 7:00 AM (default):
        powershell -ExecutionPolicy Bypass -File .\setup_task_scheduler.ps1 -Time 07:00

    Every hour, on the hour:
        powershell -ExecutionPolicy Bypass -File .\setup_task_scheduler.ps1 -IntervalHours 1

    Re-running updates the schedule. With -IntervalHours the task repeats every
    N hours indefinitely, starting at -Time.

.NOTES
    To remove it later:
        Unregister-ScheduledTask -TaskName "IBM Daily Email Digest" -Confirm:$false
#>

param(
    [string]$Time = "07:00",                       # 24-hour HH:mm, local start time
    [int]$IntervalHours = 0,                        # 0 = daily; >0 = repeat every N hours
    [string]$TaskName = "IBM Daily Email Digest"
)

$ErrorActionPreference = "Stop"

# Resolve project paths relative to this script.
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runner    = Join-Path $ScriptDir "run_digest.bat"

if (-not (Test-Path $Runner)) {
    throw "Could not find run_digest.bat next to this script ($Runner)."
}

Write-Host "Runner: $Runner"

# ---- Hourly path: use schtasks.exe (reliable across Windows builds) ----------
# The Register-ScheduledTask repetition cmdlets are buggy for "every N hours"
# on some builds, so hourly is handled natively here and the script exits.
if ($IntervalHours -gt 0) {
    Write-Host "Registering '$TaskName' to run every $IntervalHours hour(s)"
    schtasks /create /tn "$TaskName" /tr "$Runner" /sc HOURLY /mo $IntervalHours /f
    if ($LASTEXITCODE -ne 0) { throw "schtasks failed (exit $LASTEXITCODE)." }
    Write-Host ""
    Write-Host "Done. '$TaskName' will run every $IntervalHours hour(s) while logged in."
    Write-Host "Inspect with:  schtasks /query /tn `"$TaskName`" /v /fo LIST"
    Write-Host "Remove with:   schtasks /delete /tn `"$TaskName`" /f"
    Write-Host "View logs in:  output\logs\"
    return
}

# ---- Daily path: Register-ScheduledTask (works fine for a daily trigger) ------
Write-Host "Registering '$TaskName' to run daily at $Time"
$Action  = New-ScheduledTaskAction -Execute $Runner
$Trigger = New-ScheduledTaskTrigger -Daily -At $Time
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

# Run under the current user, ONLY when logged on (Interactive). This is
# required for the Outlook desktop send method, which needs your live session.
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

# Replace any existing task with the same name.
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Existing task removed; re-creating."
}

Register-ScheduledTask -TaskName $TaskName `
    -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal `
    -Description "Runs the IBM Horizon Atlantic daily client-news opportunity digest." | Out-Null

Write-Host ""
if ($IntervalHours -gt 0) {
    Write-Host "Done. '$TaskName' will run every $IntervalHours hour(s)."
} else {
    Write-Host "Done. '$TaskName' will run every day at $Time."
}
Write-Host "Test it now with:  Start-ScheduledTask -TaskName `"$TaskName`""
Write-Host "View logs in:      output\logs\"
