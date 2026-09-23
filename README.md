# Google Flow MCP — 集群原生多节点架构

本项目是全新的 Google Agentspace Flow 集群原生 MCP 服务，专门为多机分布式、自动化浏览器媒体生成设计。

---

## 核心业务与架构模型

### 1. 图片 / 角色生成（全量广播型）
- **Master 本机 Worker 0 先行执行**：Master 节点通过本地浏览器完成图片/角色的生成与下载。
- **存储到 Master AssetHub**：产出文件统一进入 Master AssetHub（支持 SHA256 去重与元数据注册）。
- **全量并发广播**：Master 将生成的素材文件并发广播下发到所有在线 Worker 节点，Worker 端自动上传到各自 Flow 的同名项目中。
- **效果**：所有节点在后续视频生成时均已预备好相关人物或素材，无需频繁实时跨机搬运。

### 2. 视频生成（积分优先单节点路由）
- **积分优先级路由**：基于每个 Worker 账号的每日免费积分（50/天，UTC 05:00 重置）及剩余余额，选出最优空闲 Worker。
- **两阶段积分预留**：`reserve -> confirm / release`，确保任务失败时积分原子退还。
- **JIT 素材兜底**：Worker 执行前若缺少所需素材，通过 HTTP 自动从 Master AssetHub 下载并上传到本地 Flow 项目。
- **视频结果回传**：Worker 本地生成并下载视频后，通过 HTTP Multipart 自动上传回 Master AssetHub，并更新任务状态为完成。

---

## 快速上手

### 1. 安装与环境准备

项目使用 `uv` 管理虚拟环境：

```powershell
# 在 flow-mcp 项目根目录下
uv venv
& .venv\Scripts\Activate.ps1
uv pip install -e .
```

### 2. 启动浏览器（可选独立守护）

```powershell
# 检查浏览器状态
flow-mcp browser --status

# 启动 Chrome 并连接 Google Flow
flow-mcp browser
```

### 3. 启动 Master 节点（MCP Gateway + 控制平面）

```powershell
# Stdio 模式（供 Claude Desktop / Cursor / Antigravity 使用）
flow-mcp master --transport stdio

# 或 SSE 模式
flow-mcp master --transport sse --port 8000
```

Master 启动后将同时在后台运行：
- **gRPC Server** (`:50051`)：与分布式 Worker 维持双向长连接流。
- **HTTP Server** (`:8765`)：提供素材上传/下载与集群监控 API。

### 4. 启动 Worker 节点（在其他机器或本地其他终端）

```powershell
flow-mcp worker --worker-id worker_gpu_1 --master-grpc 192.168.1.100:50051 --master-http http://192.168.1.100:8765
```

### 5. 查看集群状态

```powershell
flow-mcp status
```

---

## MCP 工具列表

| 工具分类 | 工具名称 | 描述 |
|---|---|---|
| **项目管理** | `website_open` | 导航至 Google Flow 网页 |
| | `project_list` | 列出集群中的 Google Flow 项目 |
| | `project_open` | 打开或创建指定别名的项目 |
| | `project_create` | 创建并命名新项目 |
| | `project_rename` | 重命名已有项目 |
| **图片生成** | `image_create` | 文生图（支持宽高比、模型、数量、素材引用、下载） |
| | `image_create_by_upload` | 通过本地上传生成图片素材 |
| | `image_status` | 查询图片任务实时进度与结果 |
| | `image_list` | 列出项目中的所有图片 |
| **视频生成** | `video_create` | 文/图生视频（支持模型分辨率选择、按积分最优路由） |
| | `video_create_by_upload` | 通过本地参考媒体生成视频 |
| | `video_status` | 查询视频任务实时进度、耗时与下载文件路径 |
| | `video_list` | 列出项目中的所有视频 |
| **角色管理** | `character_create` | 生成虚拟角色（头像 + 全身图） |
| | `character_create_by_upload`| 上传参考图生成虚拟角色 |
| | `character_status` | 查询角色任务进度 |
| | `character_list` | 列出项目中的所有角色 |
| **队列监控** | `task_queue_status` | 查询任务队列、在线 Worker 节点与账号积分详情 |
| | `task_cancel` | 取消排队中或执行中的任务 |

---

## 运行测试

```powershell
& .venv\Scripts\Activate.ps1
pytest tests/
```
