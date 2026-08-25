from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.bookings.models import Booking, BookingStatus
from app.bookings.policy import BOOKING_HOLD_DURATION
from app.bookings.repository import BookingRepository
from app.bookings.schemas import BookingCreate
from app.logger import logger


class RoomTypeNotFoundError(ValueError):
    pass


class NoAvailabilityError(ValueError):
    pass


class BookingNotFoundError(ValueError):
    pass


class BookingHoldExpiredError(ValueError):
    pass


class BookingStateConflictError(ValueError):
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

    async def list(self, *, user_id: int, limit: int, offset: int) -> list[Booking]:
        return await self._repository.list_owned(
            user_id=user_id,
            limit=limit,
            offset=offset,
        )

    async def get(self, *, booking_id: int, user_id: int) -> Booking:
        booking = await self._repository.get_owned(
            booking_id=booking_id,
            user_id=user_id,
        )
        if booking is None:
            raise BookingNotFoundError
        return booking

    async def confirm(self, *, booking_id: int, user_id: int) -> Booking:
        now = datetime.now(UTC)
        transitioned_to_confirmed = False
        hold_expired = False

        try:
            booking = await self._repository.get_owned_for_update(
                booking_id=booking_id,
                user_id=user_id,
            )
            if booking is None:
                raise BookingNotFoundError

            if booking.status == BookingStatus.CREATED and booking.expires_at <= now:
                booking.status = BookingStatus.EXPIRED
                hold_expired = True
            elif booking.status == BookingStatus.CREATED:
                booking.status = BookingStatus.CONFIRMED
                transitioned_to_confirmed = True
            elif booking.status == BookingStatus.EXPIRED:
                hold_expired = True
            elif booking.status != BookingStatus.CONFIRMED:
                raise BookingStateConflictError

            await self._session.commit()
            await self._session.refresh(booking)
        except Exception:
            await self._session.rollback()
            raise

        if hold_expired:
            self._log_expired(booking)
            raise BookingHoldExpiredError

        if transitioned_to_confirmed:
            logger.info(
                "booking_confirmed",
                extra={
                    "booking_id": booking.id,
                    "user_id": booking.user_id,
                    "room_type_id": booking.room_type_id,
                },
            )
        return booking

    async def cancel(self, *, booking_id: int, user_id: int) -> Booking:
        now = datetime.now(UTC)
        transitioned_to_cancelled = False
        transitioned_to_expired = False

        try:
            booking = await self._repository.get_owned_for_update(
                booking_id=booking_id,
                user_id=user_id,
            )
            if booking is None:
                raise BookingNotFoundError

            if booking.status == BookingStatus.CREATED and booking.expires_at <= now:
                booking.status = BookingStatus.EXPIRED
                transitioned_to_expired = True
            elif booking.status in {
                BookingStatus.CREATED,
                BookingStatus.CONFIRMED,
            }:
                booking.status = BookingStatus.CANCELLED
                transitioned_to_cancelled = True

            await self._session.commit()
            await self._session.refresh(booking)
        except Exception:
            await self._session.rollback()
            raise

        if transitioned_to_expired:
            self._log_expired(booking)
        elif transitioned_to_cancelled:
            logger.info(
                "booking_cancelled",
                extra={
                    "booking_id": booking.id,
                    "user_id": booking.user_id,
                    "room_type_id": booking.room_type_id,
                },
            )
        return booking

    @staticmethod
    def _log_expired(booking: Booking) -> None:
        logger.info(
            "booking_expired",
            extra={
                "booking_id": booking.id,
                "user_id": booking.user_id,
                "room_type_id": booking.room_type_id,
            },
        )
