from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.bookings.models import Booking, BookingStatus
from app.catalog.models import RoomType


class BookingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_room_type_for_update(self, room_type_id: int) -> RoomType | None:
        statement = (
            select(RoomType).where(RoomType.id == room_type_id).with_for_update()
        )
        return await self._session.scalar(statement)

    async def list_owned(
        self,
        *,
        user_id: int,
        limit: int,
        offset: int,
    ) -> list[Booking]:
        statement = (
            select(Booking)
            .where(Booking.user_id == user_id)
            .order_by(Booking.created_at.desc(), Booking.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(await self._session.scalars(statement))

    async def get_owned(self, *, booking_id: int, user_id: int) -> Booking | None:
        statement = select(Booking).where(
            Booking.id == booking_id,
            Booking.user_id == user_id,
        )
        return await self._session.scalar(statement)

    async def get_owned_for_update(
        self,
        *,
        booking_id: int,
        user_id: int,
    ) -> Booking | None:
        statement = (
            select(Booking)
            .where(
                Booking.id == booking_id,
                Booking.user_id == user_id,
            )
            .with_for_update()
        )
        return await self._session.scalar(statement)

    async def count_active_overlapping(
        self,
        *,
        room_type_id: int,
        date_from: date,
        date_to: date,
        now: datetime,
    ) -> int:
        statement = select(func.count(Booking.id)).where(
            Booking.room_type_id == room_type_id,
            Booking.date_from < date_to,
            Booking.date_to > date_from,
            or_(
                Booking.status == BookingStatus.CONFIRMED,
                and_(
                    Booking.status == BookingStatus.CREATED,
                    Booking.expires_at > now,
                ),
            ),
        )
        return int(await self._session.scalar(statement) or 0)

    async def add(
        self,
        *,
        user_id: int,
        room_type_id: int,
        date_from: date,
        date_to: date,
        price_per_night: Decimal,
        total_cost: Decimal,
        expires_at: datetime,
    ) -> Booking:
        booking = Booking(
            user_id=user_id,
            room_type_id=room_type_id,
            date_from=date_from,
            date_to=date_to,
            price_per_night=price_per_night,
            currency="USD",
            total_cost=total_cost,
            status=BookingStatus.CREATED,
            expires_at=expires_at,
        )
        self._session.add(booking)
        await self._session.flush()
        await self._session.refresh(booking)
        return booking

    async def expire_due_holds(self, *, now: datetime) -> list[int]:
        statement = (
            update(Booking)
            .where(
                Booking.status == BookingStatus.CREATED,
                Booking.expires_at <= now,
            )
            .values(
                status=BookingStatus.EXPIRED,
                updated_at=now,
            )
            .returning(Booking.id)
        )
        return list(await self._session.scalars(statement))
