<#
.SYNOPSIS
    Google Flow MCP 综合控制中心 (Master / Worker / Browser / Status / Stop)
.DESCRIPTION
    统一命令体系：flow_mcp.ps1 <module> [status|start|stop]
    所有配置（Worker ID、Master 端口、gRPC 调度目标、HTTP 地址等）默认从项目根目录 .env 文件自动读取，无需且不许在命令行手动指定。

    用法示例：
      .\flow_mcp.ps1 master status      # 检查 Master 状态
      .\flow_mcp.ps1 master start       # 启动 Master 网关 (读取 .env 配置)
      .\flow_mcp.ps1 master stop        # 停止 Master 服务
      
      .\flow_mcp.ps1 worker status      # 检查本地 Worker 状态
      .\flow_mcp.ps1 worker start       # 启动 Worker 节点 (读取 .env 配置)
      .\flow_mcp.ps1 worker stop        # 停止本地 Worker 节点

      .\flow_mcp.ps1 browser status     # 检查 Chrome 自动化浏览器状态
      .\flow_mcp.ps1 browser start      # 启动 Chrome 自动化浏览器
      .\flow_mcp.ps1 browser stop       # 停止 Chrome 自动化浏览器

      .\flow_mcp.ps1 status             # 全局综合状态巡检
      .\flow_mcp.ps1 stop               # 全局停止所有服务
#>
param(
    [Parameter(Position = 0)]
    [string]$Module = "",

    [Parameter(Position = 1)]
    [string]$Action = ""
)

$ErrorActionPreference = "Continue"

# 统一控制台编码为 UTF-8 (65001)，杜绝中文乱码
try { chcp 65001 > $null } catch {}
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
$EnvFilePath = Join-Path $ScriptDir ".env"

# ── 1. 自动从 .env 加载环境变量配置 ──────────────────
function Import-ProjectEnv {
    if (Test-Path $EnvFilePath) {
        Get-Content $EnvFilePath -Encoding UTF8 | ForEach-Object {
            $line = $_.Trim()
            if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
                $idx = $line.IndexOf("=")
                $key = $line.Substring(0, $idx).Trim()
                $val = $line.Substring($idx + 1).Trim().Trim('"').Trim("'")
                if (-not [System.Environment]::GetEnvironmentVariable($key, "Process")) {
                    [System.Environment]::SetEnvironmentVariable($key, $val, "Process")
                }
            }
        }
    }
}
Import-ProjectEnv

function Ensure-Environment {
    if (-not (Test-Path $VenvPython)) {
        Write-Host "[ERROR] 未检测到虚拟环境: $VenvPython" -ForegroundColor Red
        Write-Host "请先初始化环境: uv venv .venv --python 3.12 && uv pip install -e .[dev]" -ForegroundColor Yellow
        exit 1
    }
}

# ── 2. Master 模块控制器 (status | start | stop) ──────
function Invoke-MasterAction {
    param([string]$Act)
    Ensure-Environment

    $mcpPort = 8000
    if ($env:FASTMCP_PORT) { $mcpPort = [int]$env:FASTMCP_PORT }
    $httpPort = if ($env:MASTER_HTTP_PORT) { [int]$env:MASTER_HTTP_PORT } else { 8765 }
    $grpcPort = if ($env:MASTER_GRPC_PORT) { [int]$env:MASTER_GRPC_PORT } else { 50051 }

    switch ($Act.ToLower()) {
        "status" {
            Write-Host "==========================================================" -ForegroundColor Magenta
            Write-Host "         Flow-MCP Master 运行状态检查                     " -ForegroundColor Magenta
            Write-Host "==========================================================" -ForegroundColor Magenta
            
            $sseConn = Get-NetTCPConnection -LocalPort $mcpPort -State Listen -ErrorAction SilentlyContinue
            if ($sseConn) {
                Write-Host "[OK] FastMCP SSE 服务在线 (端口 $mcpPort, PID=$($sseConn.OwningProcess))" -ForegroundColor Green
            } else {
                Write-Host "[OFFLINE] FastMCP SSE 服务未在 $mcpPort 端口监听" -ForegroundColor Red
            }

            $httpConn = Get-NetTCPConnection -LocalPort $httpPort -State Listen -ErrorAction SilentlyContinue
            if ($httpConn) {
                Write-Host "[OK] Master HTTP 服务在线 (端口 $httpPort, PID=$($httpConn.OwningProcess))" -ForegroundColor Green
            } else {
                Write-Host "[OFFLINE] Master HTTP 服务未在 $httpPort 端口监听" -ForegroundColor Red
            }

            $grpcConn = Get-NetTCPConnection -LocalPort $grpcPort -State Listen -ErrorAction SilentlyContinue
            if ($grpcConn) {
                Write-Host "[OK] Master gRPC 服务在线 (端口 $grpcPort, PID=$($grpcConn.OwningProcess))" -ForegroundColor Green
            } else {
                Write-Host "[OFFLINE] Master gRPC 服务未在 $grpcPort 端口监听" -ForegroundColor Red
            }
        }
        "start" {
            Write-Host ""
            Write-Host "[1/3] 检查 Master 端口占用 (SSE=$mcpPort, HTTP=$httpPort, gRPC=$grpcPort)..." -ForegroundColor Cyan
            $ports = @($mcpPort, $httpPort, $grpcPort)
            foreach ($p in $ports) {
                $conns = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
                if ($conns) {
                    $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
                    Write-Host "[WARN] 端口 $p 已被占用 (PID: $pids)，正在强制释放旧进程..." -ForegroundColor Yellow
                    foreach ($procId in $pids) {
                        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                    }
                    Start-Sleep -Seconds 1
                }
            }
            Write-Host "[OK] 端口检查就绪。" -ForegroundColor Green

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
            Write-Host "  * FastMCP SSE 接入地址 : http://127.0.0.1:$mcpPort/sse" -ForegroundColor Cyan
            Write-Host "  * Master HTTP 素材服务 : http://127.0.0.1:$httpPort" -ForegroundColor Cyan
            Write-Host "  * Master gRPC 调度总线 : 127.0.0.1:$grpcPort" -ForegroundColor Cyan
            Write-Host "  * 提示: 按 Ctrl+C 可停止当前 Master 服务" -ForegroundColor Yellow
            Write-Host "==========================================================`n" -ForegroundColor Magenta

            & $VenvCli master --transport sse --port $mcpPort
        }
        "stop" {
            Write-Host "==========================================================" -ForegroundColor Magenta
            Write-Host "         停止 Flow-MCP Master 服务                        " -ForegroundColor Magenta
            Write-Host "==========================================================" -ForegroundColor Magenta
            $ports = @($mcpPort, $httpPort, $grpcPort)
            $stopped = $false
            foreach ($port in $ports) {
                $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
                if ($conns) {
                    $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
                    foreach ($procId in $pids) {
                        try {
                            $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
                            $pName = if ($proc) { $proc.ProcessName } else { "Unknown" }
                            Write-Host "[STOPPING] 发现端口 $port 上的进程 (PID: $procId, Name: $pName)，正在终止..." -ForegroundColor Yellow
                            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                            Write-Host "[OK] 已成功终止 PID: $procId" -ForegroundColor Green
                            $stopped = $true
                        } catch {
                            Write-Host "[FAIL] 终止 PID $procId 失败: $_" -ForegroundColor Red
                        }
                    }
                }
            }
            if (-not $stopped) {
                Write-Host "[DONE] 未发现运行中的 Flow-MCP Master 进程。" -ForegroundColor Green
            } else {
                Write-Host "[DONE] Flow-MCP Master 服务已完全停止。" -ForegroundColor Green
            }
        }
        default {
            Write-Host "[ERROR] 未知的 Master 操作: '$Act'。支持的操作: status | start | stop" -ForegroundColor Red
            Write-Host "用法示例: .\flow_mcp.ps1 master [status|start|stop]" -ForegroundColor Yellow
        }
    }
}

# ── 3. Worker 模块控制器 (status | start | stop) ──────
function Invoke-WorkerAction {
    param([string]$Act)
    Ensure-Environment

    # 严格从 .env 读取配置，不接受命令行覆写节点参数
    $workerId = if ($env:WORKER_ID) { $env:WORKER_ID } else { "worker_$env:COMPUTERNAME" }
    $grpcTarget = if ($env:MASTER_GRPC_TARGET) { $env:MASTER_GRPC_TARGET } else { "127.0.0.1:50051" }
    $httpUrl = if ($env:MASTER_HTTP_URL) { $env:MASTER_HTTP_URL } else { "http://127.0.0.1:8765" }
    $account = if ($env:WORKER_ACCOUNT) { $env:WORKER_ACCOUNT } else { "(自动检测)" }

    switch ($Act.ToLower()) {
        "status" {
            Write-Host "==========================================================" -ForegroundColor Magenta
            Write-Host "         Flow-MCP Worker 运行状态检查                     " -ForegroundColor Magenta
            Write-Host "==========================================================" -ForegroundColor Magenta
            Write-Host "当前 .env 配置信息:" -ForegroundColor Cyan
            Write-Host "  * Worker ID   : $workerId"
            Write-Host "  * 关联账号     : $account"
            Write-Host "  * Master gRPC : $grpcTarget"
            Write-Host "  * Master HTTP : $httpUrl"
            Write-Host "----------------------------------------------------------" -ForegroundColor DarkGray

            $procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
                $_.CommandLine -match "flow-mcp(\.exe)?\s+worker" -or $_.CommandLine -match "flow_mcp\.cli\.worker"
            }
            if ($procs) {
                Write-Host "[OK] 本机检测到正在运行的 Worker 进程:" -ForegroundColor Green
                foreach ($p in $procs) {
                    Write-Host "  * PID: $($p.ProcessId) | Command: $($p.CommandLine)" -ForegroundColor White
                }
            } else {
                Write-Host "[OFFLINE] 本机未检测到运行中的 Worker 进程。" -ForegroundColor Yellow
            }
        }
        "start" {
            Write-Host ""
            Write-Host "==========================================================" -ForegroundColor Magenta
            Write-Host "     Flow-MCP Worker 节点启动 (配置源自 .env)             " -ForegroundColor Magenta
            Write-Host "==========================================================" -ForegroundColor Magenta
            Write-Host "  * Worker ID   : $workerId" -ForegroundColor Cyan
            Write-Host "  * 绑定账号     : $account" -ForegroundColor Cyan
            Write-Host "  * Master gRPC : $grpcTarget" -ForegroundColor Cyan
            Write-Host "  * Master HTTP : $httpUrl" -ForegroundColor Cyan
            Write-Host "  * 提示: 节点名称与连接目标均已自 .env 载入，无需命令行传参" -ForegroundColor DarkGray
            Write-Host "==========================================================`n" -ForegroundColor Magenta

            & $VenvCli worker --worker-id $workerId --master-grpc $grpcTarget --master-http $httpUrl
        }
        "stop" {
            Write-Host "==========================================================" -ForegroundColor Magenta
            Write-Host "         停止本地 Flow-MCP Worker 进程                    " -ForegroundColor Magenta
            Write-Host "==========================================================" -ForegroundColor Magenta
            $procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
                $_.CommandLine -match "flow-mcp(\.exe)?\s+worker" -or $_.CommandLine -match "flow_mcp\.cli\.worker"
            }
            if ($procs) {
                foreach ($p in $procs) {
                    try {
                        Write-Host "[STOPPING] 正在终止 Worker 进程 PID: $($p.ProcessId)..." -ForegroundColor Yellow
                        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
                        Write-Host "[OK] 已成功终止 PID: $($p.ProcessId)" -ForegroundColor Green
                    } catch {
                        Write-Host "[FAIL] 终止 PID $($p.ProcessId) 失败: $_" -ForegroundColor Red
                    }
                }
            } else {
                Write-Host "[DONE] 本机未发现运行中的 Worker 进程。" -ForegroundColor Green
            }
        }
        default {
            Write-Host "[ERROR] 未知的 Worker 操作: '$Act'。支持的操作: status | start | stop" -ForegroundColor Red
            Write-Host "用法示例: .\flow_mcp.ps1 worker [status|start|stop]" -ForegroundColor Yellow
        }
    }
}

# ── 4. Browser 模块控制器 (status | start | stop) ─────
function Invoke-BrowserAction {
    param([string]$Act)
    Ensure-Environment

    switch ($Act.ToLower()) {
        "status" {
            Write-Host "--- Chrome 浏览器运行状态 ---" -ForegroundColor Cyan
            & $VenvCli browser --status
        }
        "start" {
            Write-Host "正在启动 Chrome 自动化浏览器并导航至 Google Flow..." -ForegroundColor Cyan
            & $VenvCli browser
        }
        "stop" {
            Write-Host "正在停止 Chrome 自动化浏览器..." -ForegroundColor Yellow
            & $VenvCli browser --stop
        }
        default {
            Write-Host "[ERROR] 未知的 Browser 操作: '$Act'。支持的操作: status | start | stop" -ForegroundColor Red
            Write-Host "用法示例: .\flow_mcp.ps1 browser [status|start|stop]" -ForegroundColor Yellow
        }
    }
}

# ── 5. 全局综合检查与停止 ────────────────────────────
function Invoke-GlobalStatus {
    Invoke-MasterAction "status"
    Write-Host ""
    Invoke-BrowserAction "status"
    Write-Host ""
    Write-Host "-------------------- 集群与积分状态 ----------------" -ForegroundColor Cyan
    & $VenvCli status
}

function Invoke-GlobalStop {
    Invoke-MasterAction "stop"
    Write-Host ""
    Invoke-WorkerAction "stop"
}

# ── 6. 命令行路由逻辑 ────────────────────────────────
$mod = $Module.ToLower().Trim()
$act = $Action.ToLower().Trim()

if ($mod) {
    # 快捷全局指令
    if ($mod -eq "status" -and -not $act) {
        Invoke-GlobalStatus
        exit 0
    }
    if ($mod -eq "stop" -and -not $act) {
        Invoke-GlobalStop
        exit 0
    }

    # 如果未指定 action，默认设为 status
    if (-not $act) {
        $act = "status"
    }

    switch ($mod) {
        "master"  { Invoke-MasterAction $act }
        "worker"  { Invoke-WorkerAction $act }
        "browser" { Invoke-BrowserAction $act }
        default {
            Write-Host "[ERROR] 未知模块: '$Module'" -ForegroundColor Red
            Write-Host "可用语法: .\flow_mcp.ps1 <master|worker|browser> [status|start|stop]" -ForegroundColor Yellow
            Write-Host "快捷指令: .\flow_mcp.ps1 status | .\flow_mcp.ps1 stop" -ForegroundColor Yellow
            exit 1
        }
    }
    exit 0
}

# ── 7. 无参数交互式控制台菜单 ────────────────────────
while ($true) {
    Clear-Host
    Write-Host "==========================================================" -ForegroundColor Magenta
    Write-Host "             Google Flow MCP 综合控制中心                 " -ForegroundColor Magenta
    Write-Host "==========================================================" -ForegroundColor Magenta
    Write-Host " 根目录   : $ScriptDir"
    Write-Host " 配置来源 : $EnvFilePath"
    $wId = if ($env:WORKER_ID) { $env:WORKER_ID } else { "未配置(自动分配)" }
    Write-Host " 默认节点 : $wId"
    Write-Host "----------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host " [Master 网关]" -ForegroundColor Cyan
    Write-Host "   1. master status  - 检查 Master 监听端口与健康度"
    Write-Host "   2. master start   - 启动 Master (FastMCP SSE + HTTP + gRPC)"
    Write-Host "   3. master stop    - 停止 Master 服务"
    Write-Host " [Worker 节点]" -ForegroundColor Cyan
    Write-Host "   4. worker status  - 检查本地 Worker 进程与配置"
    Write-Host "   5. worker start   - 启动 Worker 节点 (全配置自 .env 载入)"
    Write-Host "   6. worker stop    - 停止本地 Worker 进程"
    Write-Host " [Chrome 浏览器]" -ForegroundColor Cyan
    Write-Host "   7. browser status - 检查自动化 Chrome 运行状态"
    Write-Host "   8. browser start  - 启动自动化 Chrome 浏览器"
    Write-Host "   9. browser stop   - 停止自动化 Chrome 浏览器"
    Write-Host " [全局运维]" -ForegroundColor Yellow
    Write-Host "   s. status         - 全局综合健康巡检 (含集群积分)"
    Write-Host "   x. stop           - 一键停止 Master 与 Worker"
    Write-Host "   0. 退出控制台" -ForegroundColor DarkGray
    Write-Host "==========================================================" -ForegroundColor Magenta

    $choice = Read-Host "请输入功能编号或指令 (如 'master start')"
    $choice = $choice.Trim()

    switch -Regex ($choice) {
        "^1$" { Invoke-MasterAction "status"; Read-Host "`n按回车键返回菜单..." }
        "^2$" { Invoke-MasterAction "start"; Read-Host "`n按回车键返回菜单..." }
        "^3$" { Invoke-MasterAction "stop"; Read-Host "`n按回车键返回菜单..." }
        "^4$" { Invoke-WorkerAction "status"; Read-Host "`n按回车键返回菜单..." }
        "^5$" { Invoke-WorkerAction "start"; Read-Host "`n按回车键返回菜单..." }
        "^6$" { Invoke-WorkerAction "stop"; Read-Host "`n按回车键返回菜单..." }
        "^7$" { Invoke-BrowserAction "status"; Read-Host "`n按回车键返回菜单..." }
        "^8$" { Invoke-BrowserAction "start"; Read-Host "`n按回车键返回菜单..." }
        "^9$" { Invoke-BrowserAction "stop"; Read-Host "`n按回车键返回菜单..." }
        "^(s|status)$" { Invoke-GlobalStatus; Read-Host "`n按回车键返回菜单..." }
        "^(x|stop)$"   { Invoke-GlobalStop; Read-Host "`n按回车键返回菜单..." }
        "^0$" {
            Write-Host "已退出控制台。" -ForegroundColor Green
            exit 0
        }
        "^master\s+(status|start|stop)$" {
            $parts = $choice -split "\s+"
            Invoke-MasterAction $parts[1]
            Read-Host "`n按回车键返回菜单..."
        }
        "^worker\s+(status|start|stop)$" {
            $parts = $choice -split "\s+"
            Invoke-WorkerAction $parts[1]
            Read-Host "`n按回车键返回菜单..."
        }
        "^browser\s+(status|start|stop)$" {
            $parts = $choice -split "\s+"
            Invoke-BrowserAction $parts[1]
            Read-Host "`n按回车键返回菜单..."
        }
        default {
            Write-Host "无效输入，请重新输入。" -ForegroundColor Red
            Start-Sleep -Seconds 1
        }
    }
}
