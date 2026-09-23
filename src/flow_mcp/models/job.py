"""Job 任务数据模型."""
from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TaskType(StrEnum):
    # ── 用户可见任务 ──────────────────────────────────────────
    IMAGE_CREATE = "image_create"
    IMAGE_CREATE_BY_UPLOAD = "image_create_by_upload"
    CHARACTER_CREATE = "character_create"
    CHARACTER_CREATE_BY_UPLOAD = "character_create_by_upload"
    VIDEO_CREATE = "video_create"
    VIDEO_CREATE_BY_UPLOAD = "video_create_by_upload"
    # ── 系统内部广播任务（对 MCP 调用者不可见）──────────────────
    BROADCAST_IMAGE = "broadcast_image"
    BROADCAST_CHARACTER = "broadcast_character"


class JobPhase(StrEnum):
    # 通用
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    # 图片/角色（Master 本地执行 + 广播）
    MASTER_RUNNING = "master_running"
    BROADCASTING = "broadcasting"
    # 视频（Worker 远程执行）
    ASSIGNED = "assigned"
    SYNCING_ASSETS = "syncing_assets"
    GENERATING = "generating"
    DOWNLOADING = "downloading"
    UPLOADING = "uploading"
    # 广播子任务
    FETCHING_ASSET = "fetching_asset"
    UPLOADING_TO_FLOW = "uploading_to_flow"


# 已完成的终态集合
FINISHED_PHASES: frozenset[JobPhase] = frozenset(
    [JobPhase.COMPLETED, JobPhase.FAILED, JobPhase.CANCELLED]
)


class JobSpec(BaseModel):
    """不可变：任务的完整输入规格."""
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_type: TaskType
    project_alias: str
    params: dict[str, Any] = Field(default_factory=dict)
    required_assets: list[str] = Field(default_factory=list)
    cost_credits: int = 0
    target_worker_id: str | None = None   # 非空时强制路由（广播专用）
    parent_job_id: str | None = None      # 广播子任务指向父任务 ID
    retry_count: int = 0
    max_retries: int = 2
    created_at: float = Field(default_factory=time.time)


class JobStatus(BaseModel):
    """可变：任务的实时运行状态."""
    job_id: str
    phase: JobPhase = JobPhase.PENDING
    worker_id: str = ""
    progress_percent: int = 0
    progress_text: str = ""
    elapsed_seconds: float = 0.0
    queue_position: int = 0
    message: str = ""
    next_action: str = ""
    is_finished: bool = False
    # 完成结果
    result: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    produced_assets: list[dict[str, Any]] = Field(default_factory=list)
    # 广播状态（图片/角色专用）: worker_id → "success"|"failed"|"pending"
    broadcast_results: dict[str, str] = Field(default_factory=dict)
    updated_at: float = Field(default_factory=time.time)


class Job(BaseModel):
    """任务完整视图（Spec + Status）."""
    spec: JobSpec
    status: JobStatus

    @property
    def job_id(self) -> str:
        return self.spec.job_id

    @property
    def task_type(self) -> TaskType:
        return self.spec.task_type

    @property
    def phase(self) -> JobPhase:
        return self.status.phase

    @property
    def is_finished(self) -> bool:
        return self.status.is_finished

    @classmethod
    def create(cls, spec: JobSpec) -> "Job":
        return cls(
            spec=spec,
            status=JobStatus(job_id=spec.job_id),
        )
