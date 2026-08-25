from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.bookings.repository import BookingRepository
from app.logger import logger


class BookingExpirationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = BookingRepository(session)

    async def expire_due_holds(self, *, now: datetime | None = None) -> list[int]:
        current_time = now or datetime.now(UTC)

        try:
            booking_ids = await self._repository.expire_due_holds(now=current_time)
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        for booking_id in booking_ids:
            logger.info(
                "booking_expired",
                extra={
                    "booking_id": booking_id,
                    "expiration_source": "celery_beat",
                },
            )
        return booking_ids
