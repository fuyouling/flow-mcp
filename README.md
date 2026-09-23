# Google Flow MCP — 集群原生多节点服务

本项目是全新的 Google Agentspace Flow 集群原生 MCP 服务，专为分布式自动化多媒体生成而设计。

---

## 业务架构模式

### 1. 图片 / 角色生成：全量广播模型 (Full Broadcast Model)
- **Master 本机 (Worker 0) 执行**：Master 节点通过本地浏览器完成图片/角色创建。
- **存储至 Master AssetHub**：产物统一存入 Master AssetHub（支持 SHA256 去重与元数据注册）。
- **全网广播**：Master 将生成的素材文件广播下发至所有活跃的 Worker 节点，Worker 自动上传到本地 Flow 的同名项目中。
- **业务价值**：所有节点在后续生成视频时均已预置素材，避免视频生成时等待素材跨节点传输。

### 2. 视频生成：积分优先单节点路由 (Credit-Priority Routing)
- **多梯队路由**：依据各 Worker 账户的每日免费积分（50点/天，UTC 05:00 自动翻转重置）及付费余额，优先选择最优 Worker。
- **两阶段积分预占**：`reserve -> confirm / release`，确保任务失败时原子回滚释放积分。
- **JIT 素材对齐**：Worker 执行前若缺少所需素材，通过 HTTP 自动从 Master AssetHub 拉取并上传至 Flow 项目。
- **视频回传**：Worker 完成视频生成与下载后，通过 HTTP Multipart 自动回传至 Master AssetHub，统一交付。

---

## 快速上手

### 1. 环境准备

本项目使用 `uv` 管理虚拟环境：

```powershell
# 进入 flow-mcp 项目目录
cd c:\dev\ai\mcp\flow-mcp

# 创建虚拟环境并安装全部依赖（含 dev 开发测试依赖）
uv venv .venv --python 3.12
uv pip install -e ".[dev]"
```

### 2. 启动并登录浏览器

```powershell
# 检查浏览器运行状态
& .venv\Scripts\flow-mcp.exe browser --status

# 启动 Chrome 并登录 Google Flow
& .venv\Scripts\flow-mcp.exe browser
```

### 3. 启动 Master 节点（MCP Gateway + 控制平面）

```powershell
# Stdio 模式（供 Claude Desktop / Cursor / Antigravity 使用）
& .venv\Scripts\flow-mcp.exe master --transport stdio

# 或 SSE 模式（Web API）
& .venv\Scripts\flow-mcp.exe master --transport sse --port 8000
```

Master 启动后会自动在后台拉起：
- **gRPC Server** (`:50051`)：与分布式 Worker 保持双向流通信。
- **HTTP Server** (`:8765`)：提供素材上传/下载与集群监控 API。
- **Worker 0**：本地浏览器接入集群执行引擎。

### 4. 启动远端 Worker 节点（其他机器或本地终端）

```powershell
& .venv\Scripts\flow-mcp.exe worker --worker-id worker_gpu_1 --master-grpc 192.168.1.100:50051 --master-http http://192.168.1.100:8765
```

### 5. 查看集群状态与积分

```powershell
& .venv\Scripts\flow-mcp.exe status
```

---

## MCP 核心工具一览

| 工具分类 | 工具名称 | 功能描述 |
|---|---|---|
| **项目管理** | `website_open` | 打开 Google Flow 主页 |
| | `project_list` | 列出集群中的 Google Flow 项目 |
| | `project_open` | 打开或创建指定项目 |
| | `project_create` | 创建新项目 |
| | `project_rename` | 重命名项目 |
| **图片生成** | `image_create` | 生成图片（支持宽高比、模型、素材引用、数量倍率） |
| | `image_create_by_upload` | 通过上传图片生成素材 |
| | `image_status` | 查询图片生成实时状态 |
| | `image_list` | 列出项目中的图片 |
| **视频生成** | `video_create` | 文/图生视频（支持模型分辨率选择、按积分路由调度） |
| | `video_create_by_upload` | 通过首尾帧素材生视频 |
| | `video_status` | 查询视频生成实时进度、完成时下载并回传文件路径 |
| | `video_list` | 列出项目中的视频 |
| **角色管理** | `character_create` | 创建角色（生成头像 + 全身视图） |
| | `character_create_by_upload`| 上传参考图创建角色 |
| | `character_status` | 查询角色状态 |
| | `character_list` | 列出项目中的所有角色 |
| **队列调度** | `task_queue_status` | 查询调度队列、各 Worker 节点状态及账户积分 |
| | `task_cancel` | 取消排队中或执行中的任务 |

---

## 运行自动化测试

```powershell
& .venv\Scripts\python.exe -m pytest tests -v
```
