from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bookings.models import Booking, BookingStatus
from app.catalog.models import Hotel, RoomType


@dataclass(frozen=True, slots=True)
class AvailableRoomTypeRecord:
    hotel: Hotel
    room_type: RoomType
    rooms_left: int


class CatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_hotel(self, hotel_id: int) -> Hotel | None:
        return await self._session.get(Hotel, hotel_id)

    async def list_room_types(self, hotel_id: int) -> list[RoomType]:
        statement = (
            select(RoomType)
            .where(RoomType.hotel_id == hotel_id)
            .order_by(RoomType.price, RoomType.name)
        )
        return list(await self._session.scalars(statement))

    async def search_available_room_types(
        self,
        *,
        city: str,
        date_from: date,
        date_to: date,
        min_price: Decimal | None,
        max_price: Decimal | None,
        now: datetime,
        limit: int,
        offset: int,
    ) -> list[AvailableRoomTypeRecord]:
        occupied_rooms = (
            select(
                Booking.room_type_id.label("room_type_id"),
                func.count(Booking.id).label("rooms_booked"),
            )
            .where(
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
            .group_by(Booking.room_type_id)
            .subquery()
        )
        rooms_left = RoomType.quantity - func.coalesce(
            occupied_rooms.c.rooms_booked,
            0,
        )

        filters = [
            func.lower(Hotel.city) == city.lower(),
            rooms_left > 0,
        ]
        if min_price is not None:
            filters.append(RoomType.price >= min_price)
        if max_price is not None:
            filters.append(RoomType.price <= max_price)

        eligible_hotels = (
            select(Hotel.id.label("hotel_id"), Hotel.name.label("hotel_name"))
            .join(RoomType, RoomType.hotel_id == Hotel.id)
            .outerjoin(
                occupied_rooms,
                occupied_rooms.c.room_type_id == RoomType.id,
            )
            .where(*filters)
            .distinct()
            .order_by(Hotel.name, Hotel.id)
            .limit(limit)
            .offset(offset)
            .cte("eligible_hotels")
        )

        statement = (
            select(Hotel, RoomType, rooms_left.label("rooms_left"))
            .join(eligible_hotels, eligible_hotels.c.hotel_id == Hotel.id)
            .join(RoomType, RoomType.hotel_id == Hotel.id)
            .outerjoin(
                occupied_rooms,
                occupied_rooms.c.room_type_id == RoomType.id,
            )
            .where(*filters)
            .order_by(Hotel.name, Hotel.id, RoomType.price, RoomType.id)
        )
        rows = (await self._session.execute(statement)).all()
        return [
            AvailableRoomTypeRecord(
                hotel=hotel,
                room_type=room_type,
                rooms_left=int(rooms_left_value),
            )
            for hotel, room_type, rooms_left_value in rows
        ]
