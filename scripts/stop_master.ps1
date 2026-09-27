<#
.SYNOPSIS
    停止正在运行的 Flow-MCP Master 服务
.PARAMETER StopBrowser
    是否一并停止后台运行的 Google Flow Chrome 自动化浏览器
#>
param(
    [switch]$StopBrowser
)

$ErrorActionPreference = "Continue"

try { chcp 65001 > $null } catch {}
try {
    [Console]::InputEncoding  = [System.Text.Encoding]::UTF8
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
} catch {}
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1" 

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path "$ScriptDir\..").Path
Set-Location $ProjectRoot

Write-Host "==========================================================" -ForegroundColor Magenta
Write-Host "         停止 Flow-MCP Master 服务                        " -ForegroundColor Magenta
Write-Host "==========================================================" -ForegroundColor Magenta

$Ports = @(8000, 8765, 50051)
$stoppedAny = $false

foreach ($port in $Ports) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($conns) {
        $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($procId in $pids) {
            try {
                $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
                $procName = if ($proc) { $proc.ProcessName } else { "Unknown" }
                Write-Host "[STOPPING] 发现端口 $port 上的进程 (PID: $procId, Name: $procName)，正在终止..." -ForegroundColor Yellow
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                Write-Host "[OK] 已成功终止 PID: $procId" -ForegroundColor Green
                $stoppedAny = $true
            } catch {
                Write-Host "[FAIL] 终止 PID $procId 失败: $_" -ForegroundColor Red
            }
        }
    } else {
        Write-Host "[INFO] 端口 $port 未被占用。" -ForegroundColor DarkGray
    }
}

if ($StopBrowser) {
    Write-Host "[INFO] 正在检查并停止自动化 Chrome 浏览器..." -ForegroundColor Cyan
    $VenvCli = Join-Path $ProjectRoot ".venv\Scripts\flow-mcp.exe"
    if (Test-Path $VenvCli) {
        & $VenvCli browser --stop
    }
}

if (-not $stoppedAny) {
    Write-Host "[DONE] 未发现运行中的 Flow-MCP Master 进程。" -ForegroundColor Green
} else {
    Write-Host "[DONE] Flow-MCP Master 服务已完全停止。" -ForegroundColor Green
}
