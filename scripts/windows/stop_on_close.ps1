# Watchdog for start.bat.
#
# start.bat streams container logs in the foreground. Ctrl+C lets it shut the
# stack down itself, but closing the window with the X button kills the batch
# file outright, and the containers would keep running inside the Docker daemon.
# This script is launched by start.bat once the stack is up, waits for that batch
# file's cmd.exe (its own parent) to disappear, and then shuts the stack down.
#
# It deliberately refuses to act on anything other than the exact containers it
# was armed for: a watchdog left over from an earlier window must never tear down
# a stack somebody started afterwards.

$ErrorActionPreference = 'SilentlyContinue'

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repoRoot

$parentId = (Get-CimInstance Win32_Process -Filter "ProcessId = $PID").ParentProcessId
if (-not $parentId) { exit 0 }

# Identity of the stack this watchdog is responsible for.
$armedId = (docker compose ps -q api | Out-String).Trim()
if (-not $armedId) { exit 0 }

while (Get-Process -Id $parentId -ErrorAction SilentlyContinue) {
    Start-Sleep -Seconds 2
}

$currentId = (docker compose ps -q api | Out-String).Trim()
if (-not $currentId) { exit 0 }            # Already stopped by someone else.
if ($currentId -ne $armedId) { exit 0 }    # A different, newer stack is running.

docker compose --profile tunnel down | Out-Null
