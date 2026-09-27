<#
.SYNOPSIS
    Google Flow MCP 综合控制中心 (Master / Worker / Status / Browser / Stop)
.DESCRIPTION
    支持参数化直接执行，或无参数时进入交互式菜单（输入数字执行）：
      .\flow_mcp.ps1 master [-Port 8000] [-Force]
      .\flow_mcp.ps1 worker [-WorkerId <id>] [-MasterGrpc <ip:port>] [-MasterHttp <url>]
      .\flow_mcp.ps1 status
      .\flow_mcp.ps1 browser [status|start|stop]
      .\flow_mcp.ps1 stop [-StopBrowser]
#>
param(
    [string]$Command = "",
    [int]$Port = 8000,
    [string]$WorkerId = "",
    [string]$MasterGrpc = "127.0.0.1:50051",
    [string]$MasterHttp = "http://127.0.0.1:8765",
    [switch]$Force,
    [switch]$StopBrowser
)

$ErrorActionPreference = "Continue"

# 强制设置控制台输入/输出代码页为 UTF-8 (65001)，彻底避免中文字符串和子进程乱码
try {
    chcp 65001 > $null
} catch {}

try {
    [Console]::InputEncoding  = [System.Text.Encoding]::UTF8
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
} catch {}

$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1" 

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$VenvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"
$VenvCli = Join-Path $ScriptDir ".venv\Scripts\flow-mcp.exe"

function Ensure-Environment {
    if (-not (Test-Path $VenvPython)) {
        Write-Host "[ERROR] 未检测到虚拟环境: $VenvPython" -ForegroundColor Red
        Write-Host "请先初始化环境: uv venv .venv --python 3.12 && uv pip install -e .[dev]" -ForegroundColor Yellow
        exit 1
    }
}

function Invoke-StartMaster {
    param([int]$McpPort = 8000, [bool]$AutoForce = $false)
    Ensure-Environment

    Write-Host ""
    Write-Host "[1/3] 检查 Master 端口占用 (SSE=$McpPort, HTTP=8765, gRPC=50051)..." -ForegroundColor Cyan
    $Ports = @($McpPort, 8765, 50051)
    foreach ($p in $Ports) {
        $conns = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
        if ($conns) {
            $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
            if ($AutoForce -or $Force) {
                Write-Host "[WARN] 端口 $p 已被占用 (PID: $pids)，正在强制终止旧进程..." -ForegroundColor Yellow
                foreach ($procId in $pids) {
                    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                }
                Start-Sleep -Seconds 1
            } else {
                Write-Host "[FAIL] 端口 $p 当前正被占用 (PID: $pids)！" -ForegroundColor Red
                Write-Host "提示: 可传入 -Force 参数或在菜单中使用 [5] 停止旧进程。" -ForegroundColor Yellow
                return
            }
        }
    }
    Write-Host "[OK] 端口检查通过。" -ForegroundColor Green

    Write-Host "[2/3] 检查 Google Flow Chrome 自动化浏览器..." -ForegroundColor Cyan
    $bStatus = & $VenvCli browser --status 2>&1
    if ($bStatus -match "RUNNING") {
        Write-Host "[OK] Chrome 浏览器已在线运行。" -ForegroundColor Green
    } else {
        Write-Host "[INFO] 正在拉起 Chrome 自动化浏览器实例..." -ForegroundColor Cyan
        Start-Process -FilePath $VenvCli -ArgumentList "browser" -WindowStyle Minimized
        Start-Sleep -Seconds 3
    }

    Write-Host ""
    Write-Host "==========================================================" -ForegroundColor Magenta
    Write-Host "     Flow-MCP Master 核心网关已启动 (SSE 模式)            " -ForegroundColor Magenta
    Write-Host "==========================================================" -ForegroundColor Magenta
    Write-Host "  * FastMCP SSE 接入地址 : http://127.0.0.1:$McpPort/sse" -ForegroundColor Cyan
    Write-Host "  * Master HTTP 素材服务 : http://127.0.0.1:8765" -ForegroundColor Cyan
    Write-Host "  * Master gRPC 调度总线 : 127.0.0.1:50051" -ForegroundColor Cyan
    Write-Host "  * 提示: 按 Ctrl+C 可停止当前 Master 服务" -ForegroundColor Yellow
    Write-Host "==========================================================`n" -ForegroundColor Magenta

    & $VenvCli master --transport sse --port $McpPort
}

function Invoke-StartWorker {
    param([string]$WId = "", [string]$Grpc = "127.0.0.1:50051", [string]$Http = "http://127.0.0.1:8765")
    Ensure-Environment

    if (-not $WId) {
        $randomSuffix = Get-Random -Minimum 100 -Maximum 999
        $WId = "worker_$env:COMPUTERNAME" + "_$randomSuffix"
    }

    Write-Host ""
    Write-Host "==========================================================" -ForegroundColor Magenta
    Write-Host "     Flow-MCP Worker 节点启动                             " -ForegroundColor Magenta
    Write-Host "==========================================================" -ForegroundColor Magenta
    Write-Host "  * Worker ID   : $WId" -ForegroundColor Cyan
    Write-Host "  * Master gRPC : $Grpc" -ForegroundColor Cyan
    Write-Host "  * Master HTTP : $Http" -ForegroundColor Cyan
    Write-Host "==========================================================`n" -ForegroundColor Magenta

    & $VenvCli worker --worker-id $WId --master-grpc $Grpc --master-http $Http
}

function Invoke-CheckStatus {
    Ensure-Environment
    & "$ScriptDir\scripts\status_master.ps1"
}

function Invoke-ManageBrowser {
    Ensure-Environment
    Write-Host ""
    Write-Host "--- Chrome 浏览器管理 ---" -ForegroundColor Cyan
    Write-Host "[1] 检查浏览器运行状态"
    Write-Host "[2] 启动浏览器并打开 Google Flow"
    Write-Host "[3] 停止当前运行的浏览器"
    Write-Host "[0] 返回上一级"
    $bChoice = Read-Host "请选择浏览器操作 [0-3]"
    switch ($bChoice) {
        "1" { & $VenvCli browser --status }
        "2" {
            Write-Host "正在启动 Chrome 并导航至 Google Flow..." -ForegroundColor Cyan
            & $VenvCli browser
        }
        "3" {
            Write-Host "正在停止 Chrome 浏览器..." -ForegroundColor Yellow
            & $VenvCli browser --stop
        }
        default { Write-Host "已返回。" }
    }
}

function Invoke-StopServices {
    param([bool]$StopB = $false)
    if ($StopB -or $StopBrowser) {
        & "$ScriptDir\scripts\stop_master.ps1" -StopBrowser
    } else {
        & "$ScriptDir\scripts\stop_master.ps1"
    }
}

# ----------------- 命令行参数直接分发 -----------------
$action = $Command.ToLower()
if ($action) {
    switch ($action) {
        "master"  { Invoke-StartMaster -McpPort $Port -AutoForce $Force }
        "worker"  { Invoke-StartWorker -WId $WorkerId -Grpc $MasterGrpc -Http $MasterHttp }
        "status"  { Invoke-CheckStatus }
        "browser" { Invoke-ManageBrowser }
        "stop"    { Invoke-StopServices -StopB $StopBrowser }
        default {
            Write-Host "未知指令: $Command" -ForegroundColor Red
            Write-Host "可用参数: master | worker | status | browser | stop" -ForegroundColor Yellow
        }
    }
    exit 0
}

# ----------------- 交互式控制台菜单 -----------------
while ($true) {
    Clear-Host
    Write-Host "==========================================================" -ForegroundColor Magenta
    Write-Host "             Google Flow MCP 综合控制中心                 " -ForegroundColor Magenta
    Write-Host "==========================================================" -ForegroundColor Magenta
    Write-Host " 项目根目录: $ScriptDir"
    Write-Host " 运行模式  : 独立脚本控制 (SSE 协议)"
    Write-Host "----------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host " [1] 启动 Master 服务 (FastMCP SSE :8000 + HTTP :8765 + gRPC :50051)" -ForegroundColor White
    Write-Host " [2] 启动 Worker 节点 (分布式工作节点)" -ForegroundColor White
    Write-Host " [3] 检查 Master 状态与集群 Worker/积分池 (Status)" -ForegroundColor White
    Write-Host " [4] 管理 Google Flow 自动化 Chrome 浏览器" -ForegroundColor White
    Write-Host " [5] 停止 Flow-MCP 后台服务 (释放占用端口)" -ForegroundColor Yellow
    Write-Host " [0] 退出控制台" -ForegroundColor DarkGray
    Write-Host "==========================================================" -ForegroundColor Magenta

    $choice = Read-Host "请输入功能编号 [0-5]"
    switch ($choice) {
        "1" {
            $isForce = Read-Host "如遇端口占用是否强制重启? (y/n, 默认 y)"
            $forceParam = if ($isForce -ne "n") { $true } else { $false }
            Invoke-StartMaster -McpPort 8000 -AutoForce $forceParam
            Read-Host "`n按回车键返回菜单..."
        }
        "2" {
            $wId = Read-Host "请输入 Worker ID (直接回车自动分配)"
            Invoke-StartWorker -WId $wId
            Read-Host "`n按回车键返回菜单..."
        }
        "3" {
            Invoke-CheckStatus
            Read-Host "`n按回车键返回菜单..."
        }
        "4" {
            Invoke-ManageBrowser
            Read-Host "`n按回车键返回菜单..."
        }
        "5" {
            $alsoBrowser = Read-Host "是否一并停止自动化 Chrome 浏览器? (y/n, 默认 n)"
            $stopB = if ($alsoBrowser -eq "y") { $true } else { $false }
            Invoke-StopServices -StopB $stopB
            Read-Host "`n按回车键返回菜单..."
        }
        "0" {
            Write-Host "已退出控制台。" -ForegroundColor Green
            exit 0
        }
        default {
            Write-Host "无效输入，请重新输入 0-5。" -ForegroundColor Red
            Start-Sleep -Seconds 1
        }
    }
}
