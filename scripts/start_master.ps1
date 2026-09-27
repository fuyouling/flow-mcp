<#
.SYNOPSIS
    Flow-MCP Master 独立启动与守护脚本 (SSE 模式)
.DESCRIPTION
    执行前置健康检查 (Python虚拟环境、端口占用、Chrome浏览器状态)，
    安全启动 FastMCP Master (SSE 模式，默认端口 8000)。
.PARAMETER Port
    FastMCP SSE 监听端口，默认 8000
.PARAMETER Force
    如果检测到端口被旧实例占用，强制终止旧进程并重启
.PARAMETER LaunchBrowser
    若 Chrome 未运行，自动拉起 Chrome 浏览器实例
#>
param(
    [int]$Port = 8000,
    [switch]$Force,
    [switch]$LaunchBrowser = $true
)

$ErrorActionPreference = "Stop"

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

function Write-Step {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK]   $Message" -ForegroundColor Green
}

function Write-WarnMsg {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Fail {
    param([string]$Message)
    Write-Host "[FAIL] $Message" -ForegroundColor Red
}

Write-Host "==========================================================" -ForegroundColor Magenta
Write-Host "      Google Flow MCP - Master 独立服务控制器 (SSE)       " -ForegroundColor Magenta
Write-Host "==========================================================" -ForegroundColor Magenta
Write-Host "工作目录: $ProjectRoot"
Write-Host "监听端口: SSE=$Port | HTTP=8765 | gRPC=50051"
Write-Host ""

# 1. 检查虚拟环境
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$VenvCli = Join-Path $ProjectRoot ".venv\Scripts\flow-mcp.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Fail "未找到虚拟环境: $VenvPython"
    Write-Host "请先初始化环境:" -ForegroundColor Yellow
    Write-Host "  uv venv .venv --python 3.12"
    Write-Host "  uv pip install -e `".[dev]`""
    exit 1
}
Write-Success "检测到 Python 运行环境: $VenvPython"

# 2. 检查端口占用情况
$PortsToCheck = @($Port, 8765, 50051)
foreach ($p in $PortsToCheck) {
    $conns = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    if ($conns) {
        $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
        if ($Force) {
            Write-WarnMsg "端口 $p 已被占用 (PID: $pids)，正在强制终止旧进程..."
            foreach ($procId in $pids) {
                try {
                    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                    Write-Success "已终止进程 PID=$procId"
                } catch {
                    Write-WarnMsg "终止进程 PID=$procId 失败: $_"
                }
            }
            Start-Sleep -Seconds 1
        } else {
            Write-Fail "端口 $p 当前正被占用 (PID: $pids)！"
            Write-Host "请使用以下方式处理:" -ForegroundColor Yellow
            Write-Host "  1. 运行 `.\stop_master.bat` 关闭旧服务"
            Write-Host "  2. 或添加 -Force 参数自动杀掉旧进程重启: `.\start_master.bat -Force`"
            exit 1
        }
    }
}
Write-Success "端口检查通过 (8000, 8765, 50051 可用)"

# 3. 检查 Chrome 浏览器运行状态
Write-Step "检查 Chrome 自动化浏览器状态..."
$browserStatusOutput = & $VenvCli browser --status 2>&1
if ($browserStatusOutput -match "RUNNING") {
    Write-Success "Chrome 浏览器已在线运行。"
} else {
    Write-WarnMsg "Chrome 浏览器当前未运行！"
    if ($LaunchBrowser) {
        Write-Step "正在启动 Chrome 浏览器实例..."
        Start-Process -FilePath $VenvCli -ArgumentList "browser" -WindowStyle Minimized
        Start-Sleep -Seconds 3
        $retryStatus = & $VenvCli browser --status 2>&1
        if ($retryStatus -match "RUNNING") {
            Write-Success "Chrome 浏览器已成功拉起并就绪。"
        } else {
            Write-WarnMsg "Chrome 启动响应较慢，将在后台继续加载。"
        }
    } else {
        Write-WarnMsg "请稍后运行 `.\.venv\Scripts\flow-mcp.exe browser` 启动浏览器并登录。"
    }
}

# 4. 启动 Flow-MCP Master (SSE 模式)
Write-Host ""
Write-Host "----------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "[READY] 正在启动 Master 核心网关与调度器..." -ForegroundColor Green
Write-Host "  * FastMCP SSE 接入地址 : http://127.0.0.1:$Port/sse" -ForegroundColor Cyan
Write-Host "  * Master HTTP 素材服务 : http://127.0.0.1:8765" -ForegroundColor Cyan
Write-Host "  * Master gRPC 调度总线 : 127.0.0.1:50051" -ForegroundColor Cyan
Write-Host "  * 提示: 按 Ctrl+C 可优雅停止服务" -ForegroundColor Yellow
Write-Host "----------------------------------------------------------" -ForegroundColor DarkGray
Write-Host ""

& $VenvCli master --transport sse --port $Port
