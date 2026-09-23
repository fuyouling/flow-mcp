"""Asset 资产数据模型."""
from __future__ import annotations

import time
from enum import StrEnum

from pydantic import BaseModel, Field


class AssetKind(StrEnum):
    IMAGE = "image"
    CHARACTER = "character"
    VIDEO = "video"


class AssetRecord(BaseModel):
    """Master AssetHub 中的资产注册记录."""
    name: str
    kind: AssetKind
    file_name: str
    file_path: str
    file_size: int = 0
    sha256: str = ""
    created_by_worker: str = "master"
    source_job_id: str = ""
    created_at: float = Field(default_factory=time.time)
