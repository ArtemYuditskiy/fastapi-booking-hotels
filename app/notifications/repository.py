from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.notifications.models import (
    Notification,
    NotificationKind,
    NotificationStatus,
)


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_booking_confirmation(
        self,
        *,
        booking_id: int,
    ) -> Notification | None:
        statement = select(Notification).where(
            Notification.booking_id == booking_id,
            Notification.kind == NotificationKind.BOOKING_CONFIRMATION,
        )
        return await self._session.scalar(statement)

    async def add(
        self,
        *,
        booking_id: int,
        kind: NotificationKind,
        recipient_email: str,
        subject: str,
        body: str,
    ) -> Notification:
        notification = Notification(
            booking_id=booking_id,
            kind=kind,
            recipient_email=recipient_email,
            subject=subject,
            body=body,
        )
        self._session.add(notification)
        await self._session.flush()
        return notification

    async def list_dispatchable_ids(
        self,
        *,
        now: datetime,
        stale_before: datetime,
        limit: int,
    ) -> list[int]:
        statement = (
            select(Notification.id)
            .where(self._is_dispatchable(now=now, stale_before=stale_before))
            .order_by(Notification.next_attempt_at, Notification.id)
            .limit(limit)
        )
        return list(await self._session.scalars(statement))

    async def claim_for_delivery(
        self,
        *,
        notification_id: int,
        now: datetime,
        stale_before: datetime,
    ) -> Notification | None:
        statement = (
            select(Notification)
            .where(
                Notification.id == notification_id,
                self._is_dispatchable(now=now, stale_before=stale_before),
            )
            .with_for_update(skip_locked=True)
        )
        notification = await self._session.scalar(statement)
        if notification is None:
            return None

        notification.status = NotificationStatus.PROCESSING
        notification.attempts += 1
        notification.locked_at = now
        await self._session.flush()
        return notification

    async def get_claimed_for_update(
        self,
        *,
        notification_id: int,
        locked_at: datetime,
    ) -> Notification | None:
        statement = (
            select(Notification)
            .where(
                Notification.id == notification_id,
                Notification.status == NotificationStatus.PROCESSING,
                Notification.locked_at == locked_at,
            )
            .with_for_update()
        )
        return await self._session.scalar(statement)

    @staticmethod
    def _is_dispatchable(
        *,
        now: datetime,
        stale_before: datetime,
    ) -> ColumnElement[bool]:
        return or_(
            and_(
                Notification.status == NotificationStatus.PENDING,
                Notification.next_attempt_at <= now,
            ),
            and_(
                Notification.status == NotificationStatus.PROCESSING,
                or_(
                    Notification.locked_at.is_(None),
                    Notification.locked_at <= stale_before,
                ),
            ),
        )
