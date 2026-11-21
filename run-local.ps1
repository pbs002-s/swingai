<#
Starts StitchSense locally as detached processes so the web and API servers
survive independently of the shell/terminal that launched them.

Usage:  powershell -ExecutionPolicy Bypass -File .\run-local.ps1
Logs:   .local-logs\api.out.log / api.err.log / web.out.log / web.err.log
#>
$ErrorActionPreference = "Stop"

$root   = Split-Path -Parent $MyInvocation.MyCommand.Path
$apiDir = Join-Path $root "apps\api"
$webDir = Join-Path $root "apps\web"
$logs   = Join-Path $root ".local-logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

# Stop anything currently owning our ports or running from our app folders.
foreach ($port in @(8000, 3100)) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        $procId = $c.OwningProcess
        $parent = (Get-CimInstance Win32_Process -Filter "ProcessId=$procId").ParentProcessId
        foreach ($id in @($procId, $parent)) {
            if ($id -and $id -ne $PID) {
                Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
            }
        }
    }
}
Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like "*swing-polokda\apps\api*" -or $_.CommandLine -like "*swing-polokda\apps\web*" } |
    Where-Object { $_.Name -in @("node.exe", "python.exe", "npm.cmd", "cmd.exe") } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

$env:NEXT_PUBLIC_DEMO = "1"
$env:API_URL = "http://127.0.0.1:8000"

$uvicorn = Join-Path $apiDir ".venv\Scripts\uvicorn.exe"
$apiProc = Start-Process -FilePath $uvicorn `
    -ArgumentList @("app.main:app", "--host", "0.0.0.0", "--port", "8000") `
    -WorkingDirectory $apiDir -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $logs "api.out.log") `
    -RedirectStandardError  (Join-Path $logs "api.err.log")

$webProc = Start-Process -FilePath "npm.cmd" `
    -ArgumentList @("run", "dev", "--", "-p", "3100", "-H", "0.0.0.0") `
    -WorkingDirectory $webDir -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $logs "web.out.log") `
    -RedirectStandardError  (Join-Path $logs "web.err.log")

Write-Host "API started (PID $($apiProc.Id)) -> http://localhost:8000"
Write-Host "Web started (PID $($webProc.Id)) -> http://localhost:3100"
Write-Host "Logs in $logs"
