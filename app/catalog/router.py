from fastapi import APIRouter

from app.catalog.dependencies import CatalogCacheDependency
from app.catalog.schemas import HotelRead, RoomTypeRead
from app.catalog.service import CatalogService
from app.exceptions import HotelNotFoundException
from app.users.dependencies import SessionDependency

router = APIRouter(prefix="/api/v1/hotels", tags=["Catalog"])


@router.get("/{hotel_id}", response_model=HotelRead, summary="Get a hotel")
async def get_hotel(
    hotel_id: int,
    session: SessionDependency,
    cache: CatalogCacheDependency,
) -> HotelRead:
    hotel = await CatalogService(session, cache).get_hotel(hotel_id)
    if hotel is None:
        raise HotelNotFoundException
    return hotel


@router.get(
    "/{hotel_id}/rooms",
    response_model=list[RoomTypeRead],
    summary="List hotel room types",
)
async def list_room_types(
    hotel_id: int,
    session: SessionDependency,
    cache: CatalogCacheDependency,
) -> list[RoomTypeRead]:
    room_types = await CatalogService(session, cache).list_room_types(hotel_id)
    if room_types is None:
        raise HotelNotFoundException
    return room_types
