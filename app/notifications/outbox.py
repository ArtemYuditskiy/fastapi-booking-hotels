from sqlalchemy.ext.asyncio import AsyncSession

from app.bookings.models import Booking
from app.notifications.models import Notification, NotificationKind
from app.notifications.repository import NotificationRepository


class NotificationOutboxService:
    def __init__(self, session: AsyncSession) -> None:
        self._repository = NotificationRepository(session)

    async def ensure_booking_confirmation(
        self,
        *,
        booking: Booking,
        recipient_email: str,
    ) -> tuple[Notification, bool]:
        existing = await self._repository.get_booking_confirmation(
            booking_id=booking.id
        )
        if existing is not None:
            return existing, False

        notification = await self._repository.add(
            booking_id=booking.id,
            kind=NotificationKind.BOOKING_CONFIRMATION,
            recipient_email=recipient_email,
            subject=f"Booking #{booking.id} confirmed",
            body=(
                f"Your booking #{booking.id} is confirmed.\n"
                f"Stay: {booking.date_from.isoformat()} to "
                f"{booking.date_to.isoformat()}.\n"
                f"Total: {booking.currency} {booking.total_cost:.2f}."
            ),
        )
        return notification, True
