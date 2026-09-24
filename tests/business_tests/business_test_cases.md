# Google Flow MCP 业务功能测试用例与执行手册

本文档是 `Flow MCP` 业务功能测试套件的权威执行规范，严格对齐并覆盖全部 **19 个 MCP 业务工具** 与 **1 个端到端闭环流水线**（共计 22 个细分测试用例）。

> **核心执行规范**：
> 1. **全用例控制台输出**: 所有测试用例均在控制台实时打印工具调用名称、入参参数与返回的 JSON 结果（或原始文本），无需手动开启额外参数。
> 2. **异步任务实时轮询**: 针对创建角色（`character_create`、`character_create_by_upload`）、视频（`video_create`、`video_create_by_upload`）与图片（`image_create`、`image_create_by_upload`）任务，自动调用对应状态查询工具（`image_status`、`video_status`、`character_status`）进行多轮轮询并打印阶段状态与进度，任务完成后自动停止轮询或执行安全取消清理。

测试套件默认基于 **Master 独立调试模式**（单节点最小化调试，Master + Worker 0）已启动的前提下执行。

---

## 1. 测试环境与前置准备

根据 `docs/debugging_guide.md`（第 3 节：场景一 单节点最小化调试）：

### 步骤 1：检查并确认浏览器处于运行状态
```powershell
flow-mcp browser --status
```
*若未运行，执行 `flow-mcp browser` 启动并在弹出的 Chrome 中登录 Google 账号。*

### 步骤 2：启动 Master 节点（SSE 调试模式）
在独立终端执行：
```powershell
cd c:\dev\ai\mcp\flow-mcp
& .venv\Scripts\Activate.ps1
flow-mcp master --transport sse --port 8000
```
控制台将输出：
```text
[INFO] MasterServer background services started (gRPC: 0.0.0.0:50051, HTTP: 0.0.0.0:8765)
[INFO] Running FastMCP server with transport='sse'...
```

---

## 2. 工具矩阵与用例索引速查表

| 序号 | 业务领域 | MCP 工具名称 | 用例编号 | 对应测试函数 | 测试文件 | 状态工具轮询 |
| :---: | :--- | :--- | :--- | :--- | :--- | :---: |
| 1 | 工具发现 | `list_tools` | TC-DISC-001 | `test_tools_discovery_all_19_tools_present` | `test_01_tools_discovery.py` | - |
| 2 | 工具发现 | Schema 校验 | TC-DISC-002 | `test_tools_schemas_and_descriptions` | `test_01_tools_discovery.py` | - |
| 3 | 队列集群 | `task_queue_status` | TC-QUE-001 | `test_task_queue_status_worker_0_registered` | `test_02_task_queue_status.py` | - |
| 4 | 队列集群 | `task_cancel` | TC-QUE-002 | `test_task_cancel_non_existent_job` | `test_02_task_queue_status.py` | - |
| 5 | 项目管理 | `website_open` | TC-PRJ-001 | `test_website_open` | `test_03_project_management.py` | - |
| 6 | 项目管理 | `project_list` | TC-PRJ-002 | `test_project_list` | `test_03_project_management.py` | - |
| 7 | 项目管理 | `project_open` | TC-PRJ-003 | `test_project_open_or_create` | `test_03_project_management.py` | - |
| 8 | 项目管理 | `project_create` | TC-PRJ-004 | `test_project_create` | `test_03_project_management.py` | - |
| 9 | 项目管理 | `project_rename` | TC-PRJ-005 | `test_project_rename` | `test_03_project_management.py` | - |
| 10 | 图片生成 | `image_create` | TC-IMG-001 | `test_image_create_and_status_query` | `test_04_image_workflow.py` | `image_status` 轮询 |
| 11 | 图片生成 | `image_status` | TC-IMG-002 | `test_image_status_not_found` | `test_04_image_workflow.py` | - |
| 12 | 图片生成 | `image_create_by_upload` | TC-IMG-003 | `test_image_create_by_upload_submission` | `test_04_image_workflow.py` | `image_status` 轮询 |
| 13 | 图片生成 | `image_list` | TC-IMG-004 | `test_image_list` | `test_04_image_workflow.py` | - |
| 14 | 视频生成 | `video_create` | TC-VID-001 | `test_video_create_and_status_query` | `test_05_video_workflow.py` | `video_status` 轮询 |
| 15 | 视频生成 | `video_status` | TC-VID-002 | `test_video_status_not_found` | `test_05_video_workflow.py` | - |
| 16 | 视频生成 | `video_create_by_upload` | TC-VID-003 | `test_video_create_by_upload_submission` | `test_05_video_workflow.py` | `video_status` 轮询 |
| 17 | 视频生成 | `video_list` | TC-VID-004 | `test_video_list` | `test_05_video_workflow.py` | - |
| 18 | 角色一致 | `character_create` | TC-CHR-001 | `test_character_create_and_status_query` | `test_06_character_workflow.py` | `character_status` 轮询 |
| 19 | 角色一致 | `character_status` | TC-CHR-002 | `test_character_status_not_found` | `test_06_character_workflow.py` | - |
| 20 | 角色一致 | `character_create_by_upload` | TC-CHR-003 | `test_character_create_by_upload_submission` | `test_06_character_workflow.py` | `character_status` 轮询 |
| 21 | 角色一致 | `character_list` | TC-CHR-004 | `test_character_list` | `test_06_character_workflow.py` | - |
| 22 | 全链闭环 | 端到端流水线 | TC-E2E-001 | `test_end_to_end_business_pipeline` | `test_07_end_to_end_pipeline.py` | `image_status` 轮询 |


---

## 3. 详细测试用例与测试命令

### 3.1 工具发现模块 (Discovery)

#### 用例 1: `list_tools` 工具集注册完整性 (TC-DISC-001)
- **测试目标**: 校验 Master 节点成功注册全部 19 个业务工具，无任何缺失。
- **参数规格**: 无参数 `{}`。
- **测试命令**:
  ```powershell
  # 精确单用例测试
  & .venv\Scripts\pytest tests/business_tests/test_01_tools_discovery.py -k test_tools_discovery_all_19_tools_present -v -s

  # 模块化测试
  & .venv\Scripts\python tests/business_tests/run_tests.py --module discovery -v
  ```
- **预期响应**:
  ```json
  {
    "tools_count": 19,
    "tools": [
      "website_open", "project_list", "project_open", "project_create", "project_rename",
      "image_create", "image_create_by_upload", "image_status", "image_list",
      "video_create", "video_create_by_upload", "video_status", "video_list",
      "character_create", "character_create_by_upload", "character_status", "character_list",
      "task_queue_status", "task_cancel"
    ]
  }
  ```

#### 用例 2: 工具参数 Schema 与描述校验 (TC-DISC-002)
- **测试目标**: 校验所有 19 个工具具备有效非空描述，且核心工具参数 Schema（必填项、属性类型）符合设计规范。
- **参数规格**: 无参数 `{}`。
- **测试命令**:
  ```powershell
  # 精确单用例测试
  & .venv\Scripts\pytest tests/business_tests/test_01_tools_discovery.py -k test_tools_schemas_and_descriptions -v -s

  # 模块化测试
  & .venv\Scripts\python tests/business_tests/run_tests.py --module discovery -v
  ```
- **核心断言**:
  - `image_create`: inputSchema 包含 `prompt`, `project_name`, `aspect_ratio`
  - `video_create`: inputSchema 包含 `prompt`, `duration`, `resolution`
  - `character_create`: inputSchema 包含 `character_name`, `prompt`
  - `task_cancel`: inputSchema 包含 `job_id`

---

### 3.2 集群与队列管理模块 (Queue & Cluster)

#### 用例 3: `task_queue_status` 集群与 Worker 状态查询 (TC-QUE-001)
- **测试目标**: 校验 Master 节点正确注册内置 Worker 0 (`master_local_worker`)，返回当前活跃任务队列、在线 Worker 与额度信息。
- **参数规格**: 无参数 `{}`。
- **测试命令**:
  ```powershell
  # 精确单用例测试
  & .venv\Scripts\pytest tests/business_tests/test_02_task_queue_status.py -k test_task_queue_status_worker_0_registered -v -s

  # 模块化测试
  & .venv\Scripts\python tests/business_tests/run_tests.py --module queue -v
  ```
- **预期响应**:
  ```json
  {
    "status": "success",
    "active_jobs_count": 0,
    "workers_count": 1,
    "workers": [
      {
        "worker_id": "master_local_worker",
        "phase": "IDLE",
        "account": "master_local@google.com",
        "daily_free": 50,
        "balance": null,
        "is_available": true,
        "current_job_id": null
      }
    ],
    "active_jobs": [],
    "accounts": []
  }
  ```

#### 用例 4: `task_cancel` 任务取消与边界异常处理 (TC-QUE-002)
- **测试目标**: 校验根据 `job_id` 取消排队任务，释放预扣额度；并验证传入不存在任务 ID 时的边界容错返回。
- **参数规格**:
  ```json
  {
    "job_id": "test_fake_job_uuid_000000"
  }
  ```
- **测试命令**:
  ```powershell
  # 精确单用例测试
  & .venv\Scripts\pytest tests/business_tests/test_02_task_queue_status.py -k test_task_cancel_non_existent_job -v -s

  # 模块化测试
  & .venv\Scripts\python tests/business_tests/run_tests.py --module queue -v
  ```
- **预期响应**:
  ```json
  {
    "status": "error",
    "message": "Job 'test_fake_job_uuid_000000' not found."
  }
  ```

---

### 3.3 项目生命周期管理模块 (Project Management)

#### 用例 5: `website_open` 打开 Google Flow 主页 (TC-PRJ-001)
- **测试目标**: 控制已连接的 Chrome 标签页导航至 Flow 主页，并自动处理初始欢迎弹窗。
- **参数规格**:
  ```json
  {
    "url": ""
  }
  ```
- **测试命令**:
  ```powershell
  # 精确单用例测试
  & .venv\Scripts\pytest tests/business_tests/test_03_project_management.py -k test_website_open -v -s

  # 模块化测试
  & .venv\Scripts\python tests/business_tests/run_tests.py --module project -v
  ```
- **预期响应**:
  ```json
  {
    "status": "success",
    "message": "Opened https://flow.google.com",
    "current_url": "https://flow.google.com/..."
  }
  ```

#### 用例 6: `project_list` 获取项目列表 (TC-PRJ-002)
- **测试目标**: 扫描 Flow 平台当前项目，并将其 UUID 映射同步保存至本地 SQLite 数据库。
- **参数规格**: 无参数 `{}`。
- **测试命令**:
  ```powershell
  # 精确单用例测试
  & .venv\Scripts\pytest tests/business_tests/test_03_project_management.py -k test_project_list -v -s

  # 模块化测试
  & .venv\Scripts\python tests/business_tests/run_tests.py --module project -v
  ```
- **预期响应**:
  ```json
  {
    "status": "success",
    "count": 1,
    "projects": [
      {
        "title": "default",
        "local_uuid": "37f48e35-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
      }
    ]
  }
  ```

#### 用例 7: `project_open` 打开或按需创建项目 (TC-PRJ-003)
- **测试目标**: 根据名称在浏览器中打开项目；若不存在则自动点击新建、重命名并导航进入该项目。
- **参数规格**:
  ```json
  {
    "project_name": "test_business_suite_proj"
  }
  ```
- **测试命令**:
  ```powershell
  # 精确单用例测试
  & .venv\Scripts\pytest tests/business_tests/test_03_project_management.py -k test_project_open_or_create -v -s

  # 模块化测试
  & .venv\Scripts\python tests/business_tests/run_tests.py --module project -v
  ```
- **预期响应**:
  ```json
  {
    "status": "success",
    "project_name": "test_business_suite_proj",
    "url": "https://flow.google.com/project/xxxx-xxxx-xxxx"
  }
  ```

#### 用例 8: `project_create` 显式创建并命名新项目 (TC-PRJ-004)
- **测试目标**: 显式创建并命名全新 Flow 项目，完成本地 DAO 映射记录。
- **参数规格**:
  ```json
  {
    "project_name": "test_create_explicit_proj"
  }
  ```
- **测试命令**:
  ```powershell
  # 精确单用例测试
  & .venv\Scripts\pytest tests/business_tests/test_03_project_management.py -k test_project_create -v -s

  # 模块化测试
  & .venv\Scripts\python tests/business_tests/run_tests.py --module project -v
  ```
- **预期响应**:
  ```json
  {
    "status": "success",
    "project_name": "test_create_explicit_proj",
    "url": "https://flow.google.com/project/xxxx-xxxx-xxxx"
  }
  ```

#### 用例 9: `project_rename` 项目重命名 (TC-PRJ-005)
- **测试目标**: 对已存在的项目执行更名，并同步更新本地数据库别名映射。
- **参数规格**:
  ```json
  {
    "old_name": "test_create_explicit_proj",
    "new_name": "test_renamed_explicit_proj"
  }
  ```
- **测试命令**:
  ```powershell
  # 精确单用例测试
  & .venv\Scripts\pytest tests/business_tests/test_03_project_management.py -k test_project_rename -v -s

  # 模块化测试
  & .venv\Scripts\python tests/business_tests/run_tests.py --module project -v
  ```
- **预期响应**:
  ```json
  {
    "status": "success",
    "old_name": "test_create_explicit_proj",
    "new_name": "test_renamed_explicit_proj"
  }
  ```

---

### 3.4 图片生成业务模块 (Image Workflow)

#### 用例 10: `image_create` 文生图任务提交与状态轮询 (TC-IMG-001)
- **测试目标**: 提交文本生成图片任务，校验入参规格，验证返回唯一 `job_id` 与 pending 状态。
- **参数规格**:
  ```json
  {
    "prompt": "A futuristic laboratory with holographic interfaces, 8k render",
    "project_name": "test_image_proj",
    "aspect_ratio": "16:9",
    "model_name": "Nano Banana Pro",
    "quantity": 1,
    "download": "2K"
  }
  ```
- **测试命令**:
  ```powershell
  # 精确单用例测试
  & .venv\Scripts\pytest tests/business_tests/test_04_image_workflow.py -k test_image_create_full_params -v -s

  # 模块化测试
  & .venv\Scripts\python tests/business_tests/run_tests.py --module image -v
  ```
- **预期响应**:
  ```json
  {
    "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status": "pending",
    "message": "Image generation task submitted. Poll image_status(job_id) for progress.",
    "next_action": "Call image_status(job_id='a1b2c3d4-e5f6-7890-abcd-ef1234567890') to check status."
  }
  ```

#### 用例 11: `image_status` 查询图片任务实时状态 (TC-IMG-002)
- **测试目标**: 轮询查询图片任务执行阶段、进度及结果；并校验传入无效 `job_id` 时的 not_found 响应。
- **参数规格**:
  ```json
  {
    "job_id": "non_existent_img_job_000000"
  }
  ```
- **测试命令**:
  ```powershell
  # 精确单用例测试
  & .venv\Scripts\pytest tests/business_tests/test_04_image_workflow.py -k test_image_status_not_found -v -s

  # 模块化测试
  & .venv\Scripts\python tests/business_tests/run_tests.py --module image -v
  ```
- **预期响应**:
  ```json
  {
    "status": "not_found",
    "message": "Job 'non_existent_img_job_000000' not found."
  }
  ```

#### 用例 12: `image_create_by_upload` 本地参考图上传生图 (TC-IMG-003)
- **测试目标**: 将本地参考图片上传至目标项目画布作为输入资产。
- **参数规格**:
  ```json
  {
    "image_path": "C:\\temp\\dummy_sample.png",
    "project_name": "test_image_proj",
    "image_name": "test_sample.png"
  }
  ```
- **测试命令**:
  ```powershell
  # 精确单用例测试
  & .venv\Scripts\pytest tests/business_tests/test_04_image_workflow.py -k test_image_create_by_upload_full_params -v -s

  # 模块化测试
  & .venv\Scripts\python tests/business_tests/run_tests.py --module image -v
  ```
- **预期响应**:
  ```json
  {
    "job_id": "xxxx-xxxx-xxxx",
    "status": "pending",
    "message": "Image upload task submitted. Poll image_status(job_id) for progress."
  }
  ```

#### 用例 13: `image_list` 项目内图片资产查询 (TC-IMG-004)
- **测试目标**: 列出指定 Flow 项目画布中所有已生成的图片资产及元数据。
- **参数规格**:
  ```json
  {
    "project_name": "default"
  }
  ```
- **测试命令**:
  ```powershell
  # 精确单用例测试
  & .venv\Scripts\pytest tests/business_tests/test_04_image_workflow.py -k test_image_list -v -s

  # 模块化测试
  & .venv\Scripts\python tests/business_tests/run_tests.py --module image -v
  ```
- **预期响应**:
  ```json
  {
    "status": "success",
    "project_name": "default",
    "count": 0,
    "images": []
  }
  ```

---

### 3.5 视频生成业务模块 (Video Workflow)

#### 用例 14: `video_create` 文生视频任务提交 (TC-VID-001)
- **测试目标**: 提交视频生成任务，支持时长（8s）、分辨率（720p/1080p）与比例设置。
- **参数规格**:
  ```json
  {
    "prompt": "Cinematic drone tracking shot over mountain landscape at sunset",
    "project_name": "test_video_proj",
    "model_name": "Omni 1.1 Flash",
    "mode": "asset",
    "duration": 8,
    "resolution": "720p",
    "aspect_ratio": "16:9"
  }
  ```
- **测试命令**:
  ```powershell
  # 精确单用例测试
  & .venv\Scripts\pytest tests/business_tests/test_05_video_workflow.py -k test_video_create_full_params -v -s

  # 模块化测试
  & .venv\Scripts\python tests/business_tests/run_tests.py --module video -v
  ```
- **预期响应**:
  ```json
  {
    "job_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "status": "pending",
    "message": "Video task submitted and queued for best worker. Poll video_status(job_id).",
    "next_action": "Call video_status(job_id='b2c3d4e5-f6a7-8901-bcde-f12345678901') to check status."
  }
  ```

#### 用例 15: `video_status` 查询视频任务进度 (TC-VID-002)
- **测试目标**: 轮询视频生成任务的实时进度百分比（0% ~ 100%）与执行阶段。
- **参数规格**:
  ```json
  {
    "job_id": "non_existent_vid_job_000000"
  }
  ```
- **测试命令**:
  ```powershell
  # 精确单用例测试
  & .venv\Scripts\pytest tests/business_tests/test_05_video_workflow.py -k test_video_status_not_found -v -s

  # 模块化测试
  & .venv\Scripts\python tests/business_tests/run_tests.py --module video -v
  ```
- **预期响应**:
  ```json
  {
    "status": "not_found",
    "message": "Job 'non_existent_vid_job_000000' not found."
  }
  ```

#### 用例 16: `video_create_by_upload` 参考视频上传任务提交 (TC-VID-003)
- **测试目标**: 上传本地参考视频进行二次生成。
- **参数规格**:
  ```json
  {
    "video_path": "C:\\temp\\dummy_video.mp4",
    "project_name": "test_video_proj",
    "video_name": "sample_reference.mp4"
  }
  ```
- **测试命令**:
  ```powershell
  # 精确单用例测试
  & .venv\Scripts\pytest tests/business_tests/test_05_video_workflow.py -k test_video_create_by_upload_full_params -v -s

  # 模块化测试
  & .venv\Scripts\python tests/business_tests/run_tests.py --module video -v
  ```

#### 用例 17: `video_list` 项目内视频资产查询 (TC-VID-004)
- **测试目标**: 列出目标 Flow 项目中生成的全部视频列表。
- **参数规格**:
  ```json
  {
    "project_name": "default"
  }
  ```
- **测试命令**:
  ```powershell
  # 精确单用例测试
  & .venv\Scripts\pytest tests/business_tests/test_05_video_workflow.py -k test_video_list -v -s

  # 模块化测试
  & .venv\Scripts\python tests/business_tests/run_tests.py --module video -v
  ```
- **预期响应**:
  ```json
  {
    "status": "success",
    "project_name": "default",
    "count": 0,
    "videos": []
  }
  ```

---

### 3.6 角色一致性业务模块 (Character Workflow)

#### 用例 18: `character_create` 创建多姿态数字人角色 (TC-CHR-001)
- **测试目标**: 提交角色创建任务，锁定面部与外观一致性。
- **参数规格**:
  ```json
  {
    "character_name": "CyberPilot_Test",
    "prompt": "A female space commander with glowing visor and armored uniform",
    "project_name": "test_char_proj",
    "model_name": "Nano banana pro",
    "full_body": false
  }
  ```
- **测试命令**:
  ```powershell
  # 精确单用例测试
  & .venv\Scripts\pytest tests/business_tests/test_06_character_workflow.py -k test_character_create_full_params -v -s

  # 模块化测试
  & .venv\Scripts\python tests/business_tests/run_tests.py --module character -v
  ```
- **预期响应**:
  ```json
  {
    "job_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
    "status": "pending",
    "message": "Character task submitted. Poll character_status(job_id).",
    "next_action": "Call character_status(job_id='c3d4e5f6-a7b8-9012-cdef-123456789012') to check status."
  }
  ```

#### 用例 19: `character_status` 查询角色任务状态 (TC-CHR-002)
- **测试目标**: 轮询角色肖像生成进度；校验无效 `job_id` 的边界容错返回。
- **参数规格**:
  ```json
  {
    "job_id": "non_existent_chr_job_000000"
  }
  ```
- **测试命令**:
  ```powershell
  # 精确单用例测试
  & .venv\Scripts\pytest tests/business_tests/test_06_character_workflow.py -k test_character_status_not_found -v -s

  # 模块化测试
  & .venv\Scripts\python tests/business_tests/run_tests.py --module character -v
  ```
- **预期响应**:
  ```json
  {
    "status": "not_found",
    "message": "Job 'non_existent_chr_job_000000' not found."
  }
  ```

#### 用例 20: `character_create_by_upload` 参考肖像图上传创建角色 (TC-CHR-003)
- **测试目标**: 上传正面半身与全身参考图建立一致性数字人资产。
- **参数规格**:
  ```json
  {
    "character_name": "Uploaded_Hero_Test",
    "portrait_image_path": "C:\\temp\\dummy_portrait.png",
    "project_name": "test_char_proj",
    "full_body_image_path": ""
  }
  ```
- **测试命令**:
  ```powershell
  # 精确单用例测试
  & .venv\Scripts\pytest tests/business_tests/test_06_character_workflow.py -k test_character_create_by_upload_full_params -v -s

  # 模块化测试
  & .venv\Scripts\python tests/business_tests/run_tests.py --module character -v
  ```

#### 用例 21: `character_list` 查询项目内角色资产列表 (TC-CHR-004)
- **测试目标**: 列出指定 Flow 项目画布中所有已保存的角色列表。
- **参数规格**:
  ```json
  {
    "project_name": "default"
  }
  ```
- **测试命令**:
  ```powershell
  # 精确单用例测试
  & .venv\Scripts\pytest tests/business_tests/test_06_character_workflow.py -k test_character_list -v -s

  # 模块化测试
  & .venv\Scripts\python tests/business_tests/run_tests.py --module character -v
  ```
- **预期响应**:
  ```json
  {
    "status": "success",
    "project_name": "default",
    "count": 0,
    "characters": []
  }
  ```

---

### 3.7 端到端全链路闭环模块 (End-to-End Pipeline)

#### 用例 22: 全业务流程端到端闭环流水线测试 (TC-E2E-001)
- **测试目标**: 串联完整的生产流水线闭环：
  1. 查询初始集群状态 `task_queue_status` 确认 Worker 0 在线；
  2. 自动打开或创建目标测试项目 `project_open`；
  3. 提交生成任务 `image_create` 获取任务 ID；
  4. 轮询校验任务状态 `image_status` 处于 pending/running；
  5. 校验任务在集群全局队列 `task_queue_status` 中被正确跟踪；
  6. 安全取消任务 `task_cancel` 并释放预扣额度；
  7. 最终校验任务状态迁移至 `cancelled`。
- **测试命令**:
  ```powershell
  # 精确单用例测试
  & .venv\Scripts\pytest tests/business_tests/test_07_end_to_end_pipeline.py -k test_end_to_end_business_pipeline -v -s

  # 模块化测试
  & .venv\Scripts\python tests/business_tests/run_tests.py --module e2e -v
  ```
- **预期结果**:
  - 全流程状态迁移契约完整无差错，额度退回无误，无遗留卡死任务。

---

## 4. 批量执行与回归诊断速查

### 4.1 使用独立运行器 (`run_tests.py`)
推荐日常开发使用，内置 Master 节点探活与清晰诊断反馈：
```powershell
# 执行全部 22 个业务用例
& .venv\Scripts\python tests/business_tests/run_tests.py

# 详细输出模式 (显示每一步参数与详细日志)
& .venv\Scripts\python tests/business_tests/run_tests.py -v

# 按业务功能模块分别执行
& .venv\Scripts\python tests/business_tests/run_tests.py --module discovery
& .venv\Scripts\python tests/business_tests/run_tests.py --module queue
& .venv\Scripts\python tests/business_tests/run_tests.py --module project
& .venv\Scripts\python tests/business_tests/run_tests.py --module image
& .venv\Scripts\python tests/business_tests/run_tests.py --module video
& .venv\Scripts\python tests/business_tests/run_tests.py --module character
& .venv\Scripts\python tests/business_tests/run_tests.py --module e2e
```

### 4.2 使用标准 pytest 命令行
```powershell
# 运行业务测试全集 (22 个用例)
& .venv\Scripts\pytest tests/business_tests/ -v

# 运行所有测试（包含原有 18 个单元测试与 22 个业务测试，共 40 个测试）
& .venv\Scripts\pytest tests/ -v
```

### 4.3 使用官方 MCP Inspector 进行图形化交互调试
```powershell
npx @modelcontextprotocol/inspector --transport sse --server-url http://localhost:8000/sse
```
打开浏览器界面后，在 **Tools** 页面选择对应工具，粘贴上述用例文档中的 JSON Payload 即可直观观察 Chrome 浏览器界面的自动化操作过程。
