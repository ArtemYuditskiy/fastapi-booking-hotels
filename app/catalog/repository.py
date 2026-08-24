from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import Hotel, RoomType


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
