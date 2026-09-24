"""Data Access Object for Accounts and Credit Reservations."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import aiosqlite
from loguru import logger

from flow_mcp.db.connection import get_db_connection
from flow_mcp.models.credit import (
    DAILY_FREE_GRANT,
    AccountInfo,
    CreditReservation,
    ReservationState,
    get_current_cycle_date,
)
from flow_mcp.utils.errors import InsufficientCreditsError, ResourceNotFoundError


def _row_to_account(row: aiosqlite.Row) -> AccountInfo:
    return AccountInfo(
        email=row["email"],
        worker_id=row["worker_id"] or "",
        balance=row["balance"],
        daily_free_remaining=row["daily_free_remaining"],
        daily_cycle_date=row["daily_cycle_date"] or "",
        updated_at=row["updated_at"] or "",
    )


def _row_to_reservation(row: aiosqlite.Row) -> CreditReservation:
    return CreditReservation(
        reservation_id=row["reservation_id"],
        job_id=row["job_id"],
        account=row["account"],
        reserved_free=row["reserved_free"],
        reserved_balance=row["reserved_balance"],
        state=ReservationState(row["state"]),
        created_at=row["created_at"],
    )


class AccountDAO:
    """Async DAO for managing accounts, balances, and reservations in SQLite."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path

    async def get_account(self, email: str) -> AccountInfo | None:
        """Get account and apply daily reset if date rolled over."""
        query = "SELECT * FROM accounts WHERE email = ?"
        async with get_db_connection(self.db_path) as db:
            async with db.execute(query, (email,)) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                account = _row_to_account(row)

        # Check daily reset cycle
        current_cycle = get_current_cycle_date()
        if account.daily_cycle_date != current_cycle:
            account.daily_free_remaining = DAILY_FREE_GRANT
            account.daily_cycle_date = current_cycle
            account.updated_at = datetime.now(timezone.utc).isoformat()
            await self.upsert_account(account)

        return account

    async def get_account_by_worker(self, worker_id: str) -> AccountInfo | None:
        """Find account associated with a specific worker."""
        query = "SELECT email FROM accounts WHERE worker_id = ? LIMIT 1"
        async with get_db_connection(self.db_path) as db:
            async with db.execute(query, (worker_id,)) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                return await self.get_account(row["email"])

    async def upsert_account(self, account: AccountInfo) -> None:
        """Insert or update account info."""
        query = """
        INSERT INTO accounts (
            email, worker_id, balance, daily_free_remaining, daily_cycle_date, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(email) DO UPDATE SET
            worker_id = excluded.worker_id,
            balance = coalesce(excluded.balance, accounts.balance),
            daily_free_remaining = excluded.daily_free_remaining,
            daily_cycle_date = excluded.daily_cycle_date,
            updated_at = excluded.updated_at
        """
        async with get_db_connection(self.db_path) as db:
            await db.execute(
                query,
                (
                    account.email,
                    account.worker_id,
                    account.balance,
                    account.daily_free_remaining,
                    account.daily_cycle_date or get_current_cycle_date(),
                    account.updated_at or datetime.now(timezone.utc).isoformat(),
                ),
            )
            await db.commit()

    async def list_accounts(self) -> list[AccountInfo]:
        """List all accounts with daily reset applied."""
        query = "SELECT email FROM accounts ORDER BY email ASC"
        async with get_db_connection(self.db_path) as db:
            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()
        accounts = []
        for r in rows:
            acc = await self.get_account(r["email"])
            if acc:
                accounts.append(acc)
        return accounts

    async def create_reservation(self, res: CreditReservation) -> None:
        """Insert a credit reservation record."""
        query = """
        INSERT INTO credit_reservations (
            reservation_id, job_id, account, reserved_free, reserved_balance, state, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        async with get_db_connection(self.db_path) as db:
            await db.execute(
                query,
                (
                    res.reservation_id,
                    res.job_id,
                    res.account,
                    res.reserved_free,
                    res.reserved_balance,
                    res.state.value,
                    res.created_at,
                ),
            )
            await db.commit()

    async def get_reservation(self, reservation_id: str) -> CreditReservation | None:
        """Fetch reservation by ID."""
        query = "SELECT * FROM credit_reservations WHERE reservation_id = ?"
        async with get_db_connection(self.db_path) as db:
            async with db.execute(query, (reservation_id,)) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                return _row_to_reservation(row)

    async def get_reservation_by_job(self, job_id: str) -> CreditReservation | None:
        """Fetch active or latest reservation by job ID."""
        query = "SELECT * FROM credit_reservations WHERE job_id = ? ORDER BY created_at DESC LIMIT 1"
        async with get_db_connection(self.db_path) as db:
            async with db.execute(query, (job_id,)) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                return _row_to_reservation(row)

    async def update_reservation_state(self, reservation_id: str, state: ReservationState) -> None:
        """Update reservation state."""
        query = "UPDATE credit_reservations SET state = ? WHERE reservation_id = ?"
        async with get_db_connection(self.db_path) as db:
            await db.execute(query, (state.value, reservation_id))
            await db.commit()

    async def reserve_credits(
        self, email: str, job_id: str, cost: int
    ) -> CreditReservation:
        """
        Atomic two-phase credit reservation:
        1. Check account balance and daily free
        2. Deduct free first, then balance
        3. Insert PENDING reservation
        """
        account = await self.get_account(email)
        if not account:
            if not email:
                raise ResourceNotFoundError("Account email cannot be empty")
            # Auto-provision account with daily free credits grant
            account = AccountInfo(
                email=email,
                daily_free_remaining=DAILY_FREE_GRANT,
                daily_cycle_date=get_current_cycle_date(),
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            await self.upsert_account(account)
            logger.info(f"Auto-provisioned account '{email}' with {DAILY_FREE_GRANT} daily free credits.")

        total_avail = account.daily_free_remaining + (account.balance or 0)
        if total_avail < cost:
            raise InsufficientCreditsError(
                f"Account '{email}' has {total_avail} credits available, but {cost} required"
            )

        reserved_free = min(account.daily_free_remaining, cost)
        reserved_balance = cost - reserved_free

        account.daily_free_remaining -= reserved_free
        if account.balance is not None:
            account.balance -= reserved_balance
        account.updated_at = datetime.now(timezone.utc).isoformat()

        res = CreditReservation(
            reservation_id=str(uuid.uuid4()),
            job_id=job_id,
            account=email,
            reserved_free=reserved_free,
            reserved_balance=reserved_balance,
            state=ReservationState.PENDING,
        )

        async with get_db_connection(self.db_path) as db:
            # Update account
            await db.execute(
                """
                UPDATE accounts
                SET daily_free_remaining = ?, balance = ?, updated_at = ?
                WHERE email = ?
                """,
                (account.daily_free_remaining, account.balance, account.updated_at, email),
            )
            # Insert reservation
            await db.execute(
                """
                INSERT INTO credit_reservations (
                    reservation_id, job_id, account, reserved_free, reserved_balance, state, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    res.reservation_id,
                    res.job_id,
                    res.account,
                    res.reserved_free,
                    res.reserved_balance,
                    res.state.value,
                    res.created_at,
                ),
            )
            await db.commit()

        logger.info(
            f"Reserved {cost} credits for job {job_id} on {email} "
            f"(free={reserved_free}, balance={reserved_balance})"
        )
        return res

    async def confirm_reservation(self, job_id: str) -> None:
        """Confirm a pending reservation upon job execution start."""
        res = await self.get_reservation_by_job(job_id)
        if not res:
            logger.warning(f"No reservation found to confirm for job {job_id}")
            return
        if res.state == ReservationState.PENDING:
            await self.update_reservation_state(res.reservation_id, ReservationState.CONFIRMED)
            logger.info(f"Confirmed reservation {res.reservation_id} for job {job_id}")

    async def release_reservation(self, job_id: str) -> None:
        """Release reservation and refund credits to account upon job failure/cancellation."""
        res = await self.get_reservation_by_job(job_id)
        if not res or res.state == ReservationState.RELEASED:
            return

        async with get_db_connection(self.db_path) as db:
            # Refund to account
            await db.execute(
                """
                UPDATE accounts SET
                    daily_free_remaining = daily_free_remaining + ?,
                    balance = CASE WHEN balance IS NOT NULL THEN balance + ? ELSE NULL END,
                    updated_at = ?
                WHERE email = ?
                """,
                (
                    res.reserved_free,
                    res.reserved_balance,
                    datetime.now(timezone.utc).isoformat(),
                    res.account,
                ),
            )
            # Mark reservation released
            await db.execute(
                "UPDATE credit_reservations SET state = ? WHERE reservation_id = ?",
                (ReservationState.RELEASED.value, res.reservation_id),
            )
            await db.commit()

        logger.info(
            f"Released reservation {res.reservation_id} for job {job_id}: "
            f"refunded free={res.reserved_free}, balance={res.reserved_balance}"
        )
