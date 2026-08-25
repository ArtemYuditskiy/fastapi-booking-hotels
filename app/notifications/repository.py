from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.models import Notification, NotificationKind


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
