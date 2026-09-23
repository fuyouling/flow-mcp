"""CreditManager: Two-phase credit reservation, deduction, and account management."""
from __future__ import annotations

from typing import Optional
from loguru import logger

from flow_mcp.db.account_dao import AccountDAO
from flow_mcp.models.credit import AccountInfo, CreditReservation


class CreditManager:
    """
    Manages accounts, daily free credit grants, and two-phase credit reservations.
    """

    def __init__(self, account_dao: AccountDAO | None = None):
        self.dao = account_dao or AccountDAO()

    async def get_account(self, email: str) -> AccountInfo | None:
        """Fetch account info with auto daily cycle reset."""
        return await self.dao.get_account(email)

    async def get_account_by_worker(self, worker_id: str) -> AccountInfo | None:
        """Fetch account associated with a worker ID."""
        return await self.dao.get_account_by_worker(worker_id)

    async def upsert_account(self, account: AccountInfo) -> None:
        """Upsert account details."""
        await self.dao.upsert_account(account)

    async def list_accounts(self) -> list[AccountInfo]:
        """List all cluster accounts."""
        return await self.dao.list_accounts()

    async def reserve(self, account_email: str, job_id: str, cost: int) -> CreditReservation:
        """
        Phase 1: Reserve credits for a job.
        Raises InsufficientCreditsError if available credits < cost.
        """
        if cost <= 0:
            return CreditReservation(
                job_id=job_id,
                account=account_email,
                reserved_free=0,
                reserved_balance=0,
            )
        return await self.dao.reserve_credits(account_email, job_id, cost)

    async def confirm(self, job_id: str) -> None:
        """Phase 2a: Confirm reservation upon successful task start."""
        await self.dao.confirm_reservation(job_id)

    async def release(self, job_id: str) -> None:
        """Phase 2b: Release reservation and refund credits upon failure/cancellation."""
        await self.dao.release_reservation(job_id)

    async def update_from_worker(
        self,
        worker_id: str,
        email: str,
        balance: Optional[int] = None,
        daily_free: Optional[int] = None,
    ) -> None:
        """Update account info reported by a worker."""
        if not email:
            return

        existing = await self.get_account(email)
        if existing:
            existing.worker_id = worker_id
            if balance is not None:
                existing.balance = balance
            if daily_free is not None:
                existing.daily_free_remaining = daily_free
            await self.upsert_account(existing)
        else:
            new_acc = AccountInfo(
                email=email,
                worker_id=worker_id,
                balance=balance,
                daily_free_remaining=daily_free if daily_free is not None else 50,
            )
            await self.upsert_account(new_acc)
        logger.info(f"Updated account info for worker {worker_id}: {email} (balance={balance})")
