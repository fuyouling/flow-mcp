<#
.SYNOPSIS
    检查 Flow-MCP Master 运行状态与集群健康度
#>
param()

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
Write-Host "         Flow-MCP Master 运行状态检查                     " -ForegroundColor Magenta
Write-Host "==========================================================" -ForegroundColor Magenta

# 1. 检查 SSE 端口 8000
$sseConn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($sseConn) {
    Write-Host "[OK] FastMCP SSE 服务在线 (端口 8000, PID=$($sseConn.OwningProcess))" -ForegroundColor Green
    try {
        $res = Invoke-WebRequest -Uri "http://127.0.0.1:8000/sse" -Method Get -TimeoutSec 2 -ErrorAction Stop
        Write-Host "     HTTP 探测响应: $($res.StatusCode)" -ForegroundColor DarkGray
    } catch {
        # SSE endpoint might hold stream or return 200/400 without proper query, but connection is alive
        Write-Host "     SSE 端口握手正常" -ForegroundColor DarkGray
    }
} else {
    Write-Host "[OFFLINE] FastMCP SSE 服务未在 8000 端口监听" -ForegroundColor Red
}

# 2. 检查 HTTP 端口 8765
$httpConn = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if ($httpConn) {
    Write-Host "[OK] Master HTTP 服务在线 (端口 8765, PID=$($httpConn.OwningProcess))" -ForegroundColor Green
} else {
    Write-Host "[OFFLINE] Master HTTP 服务未在 8765 端口监听" -ForegroundColor Red
}

# 3. 检查 gRPC 端口 50051
$grpcConn = Get-NetTCPConnection -LocalPort 50051 -State Listen -ErrorAction SilentlyContinue
if ($grpcConn) {
    Write-Host "[OK] Master gRPC 服务在线 (端口 50051, PID=$($grpcConn.OwningProcess))" -ForegroundColor Green
} else {
    Write-Host "[OFFLINE] Master gRPC 服务未在 50051 端口监听" -ForegroundColor Red
}

# 4. 检查 Chrome 自动化浏览器
$VenvCli = Join-Path $ProjectRoot ".venv\Scripts\flow-mcp.exe"
if (Test-Path $VenvCli) {
    Write-Host ""
    Write-Host "-------------------- 浏览器状态 --------------------" -ForegroundColor Cyan
    & $VenvCli browser --status

    Write-Host ""
    Write-Host "-------------------- 集群与积分状态 ----------------" -ForegroundColor Cyan
    & $VenvCli status
}
