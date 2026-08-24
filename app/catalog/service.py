from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.cache import CatalogCache
from app.catalog.repository import CatalogRepository
from app.catalog.schemas import HotelRead, RoomTypeRead


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
