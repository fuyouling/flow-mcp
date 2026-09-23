"""Worker node models."""
from __future__ import annotations

import time
from enum import StrEnum

from pydantic import BaseModel, Field

HEARTBEAT_TIMEOUT_SECONDS = 30
UNHEALTHY_FAILURE_THRESHOLD = 3


class WorkerPhase(StrEnum):
    IDLE = "idle"
    BUSY = "busy"
    DISCONNECTED = "disconnected"
    UNHEALTHY = "unhealthy"


class WorkerInfo(BaseModel):
    worker_id: str
    ip: str = ""
    account: str = ""
    phase: WorkerPhase = WorkerPhase.IDLE
    current_job_id: str | None = None
    project_mappings: dict[str, str] = Field(default_factory=dict)
    cached_assets: set[str] = Field(default_factory=set)
    daily_free_remaining: int = 50
    balance: int | None = None
    last_heartbeat: float = Field(default_factory=time.time)
    consecutive_failures: int = 0
    registered_at: float = Field(default_factory=time.time)

    model_config = {"arbitrary_types_allowed": True}

    @property
    def daily_free(self) -> int:
        return self.daily_free_remaining

    @daily_free.setter
    def daily_free(self, val: int) -> None:
        self.daily_free_remaining = val

    @property
    def is_available(self) -> bool:
        return self.phase == WorkerPhase.IDLE

    @property
    def is_online(self) -> bool:
        return self.phase not in (WorkerPhase.DISCONNECTED, WorkerPhase.UNHEALTHY)

    def heartbeat_age(self) -> float:
        return time.time() - self.last_heartbeat

    def is_heartbeat_expired(self) -> bool:
        return self.heartbeat_age() > HEARTBEAT_TIMEOUT_SECONDS

    def can_afford(self, cost: int) -> bool:
        total = self.daily_free_remaining + (self.balance or 0)
        return total >= cost
