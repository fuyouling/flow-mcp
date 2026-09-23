"""Credit and account models."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import time
import uuid
from enum import StrEnum

from pydantic import BaseModel, Field

DAILY_FREE_GRANT = 50     # Daily free grant
UTC_RESET_HOUR = 5        # Resets at UTC 05:00


def get_current_cycle_date() -> str:
    """Return the current daily cycle date string (UTC YYYY-MM-DD), rolling over at UTC 05:00."""
    now = datetime.now(timezone.utc)
    if now.hour < UTC_RESET_HOUR:
        cycle_dt = now - timedelta(days=1)
    else:
        cycle_dt = now
    return cycle_dt.strftime("%Y-%m-%d")


class ReservationState(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    RELEASED = "released"


class CreditReservation(BaseModel):
    reservation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str
    account: str
    reserved_free: int = 0
    reserved_balance: int = 0
    state: ReservationState = ReservationState.PENDING
    created_at: float = Field(default_factory=time.time)


class AccountInfo(BaseModel):
    email: str
    worker_id: str = ""
    balance: int | None = None
    daily_free_remaining: int = DAILY_FREE_GRANT
    daily_cycle_date: str = ""   # UTC YYYY-MM-DD
    updated_at: str = ""
