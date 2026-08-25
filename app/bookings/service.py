from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.bookings.models import Booking
from app.bookings.policy import BOOKING_HOLD_DURATION
from app.bookings.repository import BookingRepository
from app.bookings.schemas import BookingCreate
from app.logger import logger


class RoomTypeNotFoundError(ValueError):
    pass


class NoAvailabilityError(ValueError):
    pass


class BookingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = BookingRepository(session)

    async def create(self, *, user_id: int, data: BookingCreate) -> Booking:
        now = datetime.now(UTC)
        nights = (data.date_to - data.date_from).days

        try:
            room_type = await self._repository.get_room_type_for_update(
                data.room_type_id
            )
            if room_type is None:
                raise RoomTypeNotFoundError

            occupied = await self._repository.count_active_overlapping(
                room_type_id=room_type.id,
                date_from=data.date_from,
                date_to=data.date_to,
                now=now,
            )
            if occupied >= room_type.quantity:
                raise NoAvailabilityError

            booking = await self._repository.add(
                user_id=user_id,
                room_type_id=room_type.id,
                date_from=data.date_from,
                date_to=data.date_to,
                price_per_night=room_type.price,
                total_cost=room_type.price * nights,
                expires_at=now + BOOKING_HOLD_DURATION,
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        logger.info(
            "booking_created",
            extra={
                "booking_id": booking.id,
                "user_id": booking.user_id,
                "room_type_id": booking.room_type_id,
                "date_from": booking.date_from.isoformat(),
                "date_to": booking.date_to.isoformat(),
            },
        )
        return booking
