from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.cache import CatalogCache
from app.catalog.repository import CatalogRepository
from app.catalog.schemas import (
    AvailableRoomTypeRead,
    HotelRead,
    HotelSearchParams,
    HotelSearchResult,
    RoomTypeRead,
)
from app.logger import logger


class CatalogService:
    def __init__(self, session: AsyncSession, cache: CatalogCache) -> None:
        self._repository = CatalogRepository(session)
        self._cache = cache

    async def get_hotel(self, hotel_id: int) -> HotelRead | None:
        cached_hotel = await self._cache.get_hotel(hotel_id)
        if cached_hotel is not None:
            return cached_hotel

        hotel = await self._repository.get_hotel(hotel_id)
        if hotel is None:
            return None

        result = HotelRead.model_validate(hotel)
        await self._cache.set_hotel(result)
        return result

    async def list_room_types(self, hotel_id: int) -> list[RoomTypeRead] | None:
        hotel = await self.get_hotel(hotel_id)
        if hotel is None:
            return None

        cached_room_types = await self._cache.get_room_types(hotel_id)
        if cached_room_types is not None:
            return cached_room_types

        result = [
            RoomTypeRead.model_validate(room_type)
            for room_type in await self._repository.list_room_types(hotel_id)
        ]
        await self._cache.set_room_types(hotel_id, result)
        return result


class HotelSearchService:
    def __init__(self, session: AsyncSession) -> None:
        self._repository = CatalogRepository(session)

    async def search(
        self,
        params: HotelSearchParams,
    ) -> list[HotelSearchResult]:
        records = await self._repository.search_available_room_types(
            city=params.city,
            date_from=params.date_from,
            date_to=params.date_to,
            min_price=params.min_price,
            max_price=params.max_price,
            now=datetime.now(UTC),
            limit=params.limit,
            offset=params.offset,
        )
        nights = (params.date_to - params.date_from).days
        results_by_hotel: dict[int, HotelSearchResult] = {}

        for record in records:
            hotel = results_by_hotel.get(record.hotel.id)
            if hotel is None:
                hotel = HotelSearchResult(
                    id=record.hotel.id,
                    slug=record.hotel.slug,
                    name=record.hotel.name,
                    city=record.hotel.city,
                    country=record.hotel.country,
                    address=record.hotel.address,
                    services=record.hotel.services,
                    rooms=[],
                )
                results_by_hotel[record.hotel.id] = hotel

            room_type = record.room_type
            hotel.rooms.append(
                AvailableRoomTypeRead(
                    room_type_id=room_type.id,
                    code=room_type.code,
                    name=room_type.name,
                    description=room_type.description,
                    rooms_left=record.rooms_left,
                    price_per_night=room_type.price,
                    currency="USD",
                    total_cost=room_type.price * nights,
                    services=room_type.services,
                )
            )

        results = list(results_by_hotel.values())
        if not results:
            logger.info(
                "hotel_search_no_results",
                extra={
                    "city": params.city,
                    "date_from": params.date_from.isoformat(),
                    "date_to": params.date_to.isoformat(),
                    "min_price": str(params.min_price),
                    "max_price": str(params.max_price),
                },
            )
        return results
