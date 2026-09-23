"""Pydantic parameter models for MCP tools and services."""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


# ── Project Parameters ──────────────────────────────

class ProjectOpenParams(BaseModel):
    project_name: str = "default"


class ProjectCreateParams(BaseModel):
    project_name: str


class ProjectRenameParams(BaseModel):
    old_name: str
    new_name: str


class ProjectListParams(BaseModel):
    pass


# ── Image Parameters ────────────────────────────────

class ImageCreateParams(BaseModel):
    project_name: str = "default"
    prompt: str
    aspect_ratio: str = "16:9"
    model_name: str = "Nano Banana Pro"
    quantity: int = 1
    image_name: str = ""
    assets: str = ""
    download: str = "2K"


class ImageCreateByUploadParams(BaseModel):
    project_name: str = "default"
    image_path: str
    image_name: str = ""

ImageUploadParams = ImageCreateByUploadParams


class ImageStatusParams(BaseModel):
    job_id: str


class ImageListParams(BaseModel):
    project_name: str = "default"


# ── Video Parameters ────────────────────────────────

class VideoCreateParams(BaseModel):
    project_name: str = "default"
    prompt: str
    model_name: str = "Omni 1.1 Flash"
    resolution: str = "720p"
    quantity: int = 1
    assets: str = ""
    video_name: str = ""
    download: str = "720p"


class VideoCreateByUploadParams(BaseModel):
    project_name: str = "default"
    video_path: str
    video_name: str = ""

VideoUploadParams = VideoCreateByUploadParams


class VideoStatusParams(BaseModel):
    job_id: str


class VideoListParams(BaseModel):
    project_name: str = "default"


# ── Character Parameters ────────────────────────────

class CharacterCreateParams(BaseModel):
    project_name: str = "default"
    prompt: str
    character_name: str
    model_name: str = "Nano banana pro"
    full_body: bool = False


class CharacterCreateByUploadParams(BaseModel):
    project_name: str = "default"
    character_name: str
    portrait_image_path: str
    full_body_image_path: str = ""

CharacterUploadParams = CharacterCreateByUploadParams


class CharacterStatusParams(BaseModel):
    job_id: str


class CharacterListParams(BaseModel):
    project_name: str = "default"


# ── Queue / Task Parameters ─────────────────────────

class TaskQueueStatusParams(BaseModel):
    pass


class TaskCancelParams(BaseModel):
    job_id: str
