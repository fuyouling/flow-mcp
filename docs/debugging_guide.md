# Google Flow MCP — 调试与启动操作指南

本文档详细说明 `flow-mcp` 项目在开发与测试过程中的完整启动与调试步骤，涵盖**单节点快速调试**、**单机模拟多节点集群调试**、**跨机器分布式联调**及**常见问题排查**。

---

## 目录
1. [系统架构与调试拓扑](#1-系统架构与调试拓扑)
2. [调试环境准备](#2-调试环境准备)
3. [场景一：单节点最小化调试（Master + Worker 0）](#3-场景一单节点最小化调试master--worker-0)
4. [场景二：单机模拟多 Worker 集群调试](#4-场景二单机模拟多-worker-集群调试)
5. [场景三：跨机器分布式集群联调](#5-场景三跨机器分布式集群联调)
6. [场景四：MCP Client（Inspector / Claude / Cursor）调试](#6-场景四mcp-clientinspector--claude--cursor调试)
7. [数据库与存储状态调试](#7-数据库与存储状态调试)
8. [常见故障排查指南 (Troubleshooting)](#8-常见故障排查指南-troubleshooting)
9. [调试命令速查表](#9-调试命令速查表)

---

## 1. 系统架构与调试拓扑

调试涉及的核心网络端口与进程关系如下：

```
+-----------------------------------------------------------------------------------+
|                                  Master 宿主机                                    |
|                                                                                   |
|  [Chrome 实例 1] <---CDP(9222)---+                                                |
|                                   |                                               |
|  [MCP Client]                     v                                               |
|  (Inspector /    ---Stdio/SSE--> [Master 进程 (flow-mcp master)]                  |
|   Claude)                         |-- FastMCP Gateway                             |
|                                   |-- MasterServer: gRPC(:50051) + HTTP(:8765)    |
|                                   |-- SQLite WAL (data/flow_mcp.db)               |
|                                   +-- AssetHub (data/assets/)                     |
|                                           ^               ^                       |
+-------------------------------------------|---------------|-----------------------+
                                     gRPC   |               | HTTP
                                   (:50051) |               | (:8765)
+-------------------------------------------|---------------|-----------------------+
|  [Worker 进程 (flow-mcp worker)] ---------+               |                       |
|         |                                                 |                       |
|         +---CDP(9223/9222)---> [Chrome 实例 2]            v                       |
|                                (登录独立账号) <----+ [JIT 素材拉取/回传]           |
|                                                                                   |
|                           Worker 节点 (单机或局域网机器)                          |
+-----------------------------------------------------------------------------------+
```

---

## 2. 调试环境准备

### 2.1 依赖安装与虚拟环境激活
打开 Windows PowerShell (`pwsh`)：
```powershell
cd c:\dev\ai\mcp\flow-mcp

# 激活专属虚拟环境
& .venv\Scripts\Activate.ps1

# 验证 CLI 命令是否可用
flow-mcp --help
```

### 2.2 准备 Google Flow 登录态
Flow MCP 需要通过 Chrome 浏览器的 CDP (Chrome DevTools Protocol) 自动化操作 Google Agentspace Flow：
1. 首次调试前，必须通过调试命令拉起 Chrome 并手动登录 Google 账号：
   ```powershell
   flow-mcp browser
   ```
2. 浏览器启动后会自动打开 `https://flow.google.com`。
3. 请在弹出的 Chrome 窗口中**完成 Google 账号登录**，并进入 Flow 项目列表主页。
4. 登录成功后，用户 Cookie 与会话数据会自动持久化保存在 `chrome_data/` 目录中，后续启动无需重复登录。

---

## 3. 场景一：单节点最小化调试（Master + Worker 0）

此模式适合日常开发、页面元素适配、单个工具逻辑验证。Master 进程内置了 Worker 0 本地执行器，不需要启动额外的 Worker 进程。

### 步骤 1：检查并确认浏览器处于运行状态
```powershell
flow-mcp browser --status
```
输出应显示：
```
[OK] Browser is RUNNING on port 9222 (PID=xxxx)
```
*如果未运行，执行 `flow-mcp browser` 启动即可。*

### 步骤 2：启动 Master 节点（独立调试模式）
推荐使用 **SSE 模式** 进行调试，这样日志输出到控制台，不会与 MCP Stdio 协议混淆：
```powershell
# 可选：设置调试日志级别
$env:LOG_LEVEL = "DEBUG"

# 启动 Master 服务（SSE 传输）
flow-mcp master --transport sse --port 8000
```
控制台将输出：
```
[INFO] Initializing Flow MCP Master node...
[INFO] FlowMCPGateway initialization complete.
[INFO] MasterServer background services started (gRPC: 0.0.0.0:50051, HTTP: 0.0.0.0:8765)
[INFO] Running FastMCP server with transport='sse'...
```

### 步骤 3：在新终端检查集群与 Worker 0 状态
打开第二个 PowerShell 终端：
```powershell
cd c:\dev\ai\mcp\flow-mcp
& .venv\Scripts\Activate.ps1

flow-mcp status
```
此时应能查看到内置的 `master_local_worker` 处于 `IDLE` 状态，拥有 50 每日免费积分。

---

## 4. 场景二：单机模拟多 Worker 集群调试

此模式用于验证：
- 节点心跳与动态加入/摘除
- 任务广播（图片/角色同时同步到多个节点）
- 视频任务的积分优先路由决策与多节点争抢
- 远端生成视频并回传到 Master AssetHub

单机模拟的关键在于：**为每个 Worker 分配独立的 Chrome 调试端口与独立的 User Data 目录**。

### 终端 1：Master 节点与主浏览器 (Port 9222)
```powershell
# 1. 确保主浏览器运行在 9222 端口
flow-mcp browser --status

# 2. 启动 Master 节点
flow-mcp master --transport sse --port 8000
```

### 终端 2：启动模拟 Worker 1 的专属 Chrome 浏览器 (Port 9223)
启动一个使用全新数据目录和 `9223` 端口的 Chrome 实例：
```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
    --remote-debugging-port=9223 `
    --user-data-dir="c:\dev\ai\mcp\flow-mcp\chrome_data_worker1" `
    --no-first-run `
    --no-default-browser-check `
    "https://flow.google.com"
```
*在弹出的 9223 端口浏览器中，登录第二个测试 Google 账号（或同一账号的不同 Session）。*

### 终端 3：启动模拟 Worker 1 客户端进程
```powershell
cd c:\dev\ai\mcp\flow-mcp
& .venv\Scripts\Activate.ps1

# 指定 Worker 1 连接 9223 端口的浏览器
$env:CHROME_DEBUGGING_PORT = "9223"
$env:WORKER_ACCOUNT = "worker1_test@gmail.com"

# 启动 Worker 客户端并连接 Master
flow-mcp worker --worker-id worker_sim_1 --master-grpc 127.0.0.1:50051 --master-http http://127.0.0.1:8765
```
控制台将输出注册成功的日志：
```
[INFO] WorkerClient [worker_sim_1] registered successfully with Master.
[INFO] Heartbeat loop started (interval: 10.0s).
```

### 终端 4：查看集群状态
```powershell
flow-mcp status
```
你将看到集群中同时存在 `master_local_worker` 和 `worker_sim_1` 两个节点！

---

## 5. 场景三：跨机器分布式集群联调

当 Worker 部署在不同的物理机或 GPU 工作站上时：

### 5.1 Master 机器准备
1. **防火墙配置**：确保 Master 机器放行以下入站端口：
   - TCP `50051`（Master gRPC 控制流）
   - TCP `8765`（Master HTTP 素材上传与回传）
2. **确认 Master 局域网 IP**（例如 `192.168.1.100`）：
   ```powershell
   ipconfig
   ```
3. **启动 Master**：
   ```powershell
   flow-mcp master --transport sse --port 8000
   ```

### 5.2 Worker 远端机器运行
在局域网内的 Worker 机器上：
1. 启动本地 Chrome 并登录：
   ```powershell
   flow-mcp browser
   ```
2. 启动 Worker 并指定 Master 的 IP 地址：
   ```powershell
   flow-mcp worker `
       --worker-id gpu_worker_01 `
       --master-grpc 192.168.1.100:50051 `
       --master-http http://192.168.1.100:8765
   ```

---

## 6. 场景四：MCP Client（Inspector / Claude / Cursor）调试

### 6.1 使用官方 MCP Inspector 进行交互式可视化调试（强烈推荐）
MCP Inspector 允许在 Web 界面中点击调用每一个工具，实时输入 JSON 参数并检查工具输出：

```powershell
npx @modelcontextprotocol/inspector c:\dev\ai\mcp\flow-mcp\.venv\Scripts\flow-mcp.exe master --transport stdio
```

执行后：
1. 控制台会输出 Inspector 页面链接（如 `http://localhost:5173` 或类似地址）。
2. 在浏览器中打开该链接。
3. 点击 **List Tools**，可以看到 `flow-mcp` 注册的 17 个全部工具。
4. 可以直接点击 `project_list` 或 `task_queue_status` 进行调用测试，查看底层实时交互。

### 6.2 在 Claude Desktop 中联调
编辑 Claude Desktop 配置文件：`%APPDATA%\Claude\claude_desktop_config.json`：
```json
{
  "mcpServers": {
    "flow-cluster": {
      "command": "c:\\dev\\ai\\mcp\\flow-mcp\\.venv\\Scripts\\flow-mcp.exe",
      "args": [
        "master",
        "--transport",
        "stdio"
      ],
      "cwd": "c:\\dev\\ai\\mcp\\flow-mcp"
    }
  }
}
```
保存后重启 Claude Desktop，在工具列表中即可看到 `flow-mcp` 的全部集群自动化工具。

### 6.3 在 Cursor 中联调
在 Cursor `Settings` -> `Features` -> `MCP Servers` 中添加：
- **Name**: `flow-cluster`
- **Type**: `command`
- **Command**: `c:\dev\ai\mcp\flow-mcp\.venv\Scripts\flow-mcp.exe master --transport stdio`

---

## 7. 数据库与存储状态调试

Master 节点的底层状态完全持久化在 `data/` 目录中：

### 7.1 SQLite 数据库检查
数据库位于 `data/flow_mcp.db`，可以使用任何 SQLite 工具（如 `sqlite3` CLI、VS Code SQLite Viewer 或 DBeaver）查看：

```powershell
# 查看任务表数据
sqlite3 data/flow_mcp.db "SELECT id, task_type, phase, assigned_worker FROM jobs ORDER BY created_at DESC LIMIT 5;"

# 查看 Worker 账户与积分表
sqlite3 data/flow_mcp.db "SELECT * FROM accounts;"

# 查看积分预占记录
sqlite3 data/flow_mcp.db "SELECT * FROM reservations;"

# 查看全局素材表
sqlite3 data/flow_mcp.db "SELECT id, name, kind, sha256 FROM assets;"
```

### 7.2 素材文件存储
素材物理文件保存在 `data/assets/` 目录下：
- 图片素材：`data/assets/<hash>.png`
- 视频生成产物：`data/assets/<job_id>_<name>.mp4`
可通过 HTTP 服务直接下载测试：
```powershell
curl http://localhost:8765/assets/<asset_id> -o downloaded_test.png
```

---

## 8. 常见故障排查指南 (Troubleshooting)

### 故障 1：`DrissionPage` 提示无法连接到浏览器 / `BrowserInitError`
- **原因**：Chrome 进程未启动，或者未开启 `--remote-debugging-port=9222`。
- **排查步骤**：
  1. 检查端口占用：
     ```powershell
     Test-NetConnection -ComputerName 127.0.0.1 -Port 9222
     ```
  2. 如果提示连接失败，先杀掉孤儿 Chrome 进程：
     ```powershell
     flow-mcp browser --stop
     ```
  3. 清理锁文件（如果上一次非正常退出）：
     ```powershell
     Remove-Item "chrome_data\SingletonLock" -ErrorAction SilentlyContinue
     ```
  4. 重新拉起浏览器：
     ```powershell
     flow-mcp browser
     ```

### 故障 2：gRPC 连接拒绝 `StatusCode.UNAVAILABLE`
- **原因**：Worker 启动时 Master 尚未就绪，或 Master gRPC 端口被防火墙阻断。
- **排查步骤**：
  1. 确认 Master 控制台是否有输出 `MasterServer background services started`。
  2. 测试端口连通性：
     ```powershell
     Test-NetConnection -ComputerName 127.0.0.1 -Port 50051
     ```
  3. Worker 具备自动指数退避重连机制，当 Master 重新上线后会自动重连并补发心跳。

### 故障 3：Stdio 模式下客户端报错 JSON-RPC 格式解析错误
- **原因**：任何打印到 `stdout` 的普通文本日志都会破坏 Stdio 协议传输。
- **保护机制**：Master CLI 在 `--transport stdio` 时已强制重定向所有日志输出至 `stderr`。请不要在代码中使用原生 `print(...)` 打印内容，始终使用 `loguru.logger`。

### 故障 4：重置全部测试环境数据
如果需要重置所有测试任务与本地缓存，执行以下命令即可：
```powershell
# 1. 停止运行中的服务
# 2. 清除数据库与素材缓存
Remove-Item "data\flow_mcp.db*" -Force -ErrorAction SilentlyContinue
Remove-Item "data\assets\*" -Force -Recurse -ErrorAction SilentlyContinue
```

---

## 9. 调试命令速查表

| 操作需求 | 完整命令行 |
|---|---|
| **检查浏览器状态** | `flow-mcp browser --status` |
| **拉起调试浏览器** | `flow-mcp browser` |
| **强制重启浏览器** | `flow-mcp browser --force` |
| **启动 Master (SSE 模式，推荐调试)** | `flow-mcp master --transport sse --port 8000` |
| **启动 Master (Stdio 模式，供 Client 接入)** | `flow-mcp master --transport stdio` |
| **启动 Worker 节点** | `flow-mcp worker --worker-id worker_1` |
| **查看集群与积分报表** | `flow-mcp status` |
| **导出集群 JSON 状态** | `flow-mcp status --json` |
| **使用 MCP Inspector 调试** | `npx @modelcontextprotocol/inspector .venv\Scripts\flow-mcp.exe master --transport stdio` |
| **运行全部自动化测试** | `pytest tests -v` |
| **单独运行集成测试** | `pytest tests/integration/test_cluster_grpc_http.py -v` |
