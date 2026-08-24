from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
from httpx import AsyncClient
from redis.exceptions import RedisError
from sqlalchemy import func, select, update

from app.catalog.cache import CatalogCache, RedisCatalogCache
from app.catalog.dependencies import get_catalog_cache
from app.catalog.models import Hotel, RoomType
from app.catalog.seed import CATALOG_SEED, seed_catalog
from app.database import async_session_maker
from app.main import app

pytestmark = pytest.mark.integration


class UnavailableRedis:
    async def get(self, key: str) -> str | None:
        raise RedisError("Redis is unavailable")

    async def set(self, key: str, value: str, *, ex: int) -> None:
        raise RedisError("Redis is unavailable")

    async def delete(self, *keys: str) -> None:
        raise RedisError("Redis is unavailable")

    async def scan_iter(self, match: str) -> AsyncIterator[str]:
        raise RedisError("Redis is unavailable")
        yield


def get_unavailable_catalog_cache() -> CatalogCache:
    return RedisCatalogCache(UnavailableRedis())


@pytest.mark.usefixtures("clean_catalog")
async def test_catalog_seed_is_idempotent_and_restores_seed_values() -> None:
    async with async_session_maker() as session:
        first_result = await seed_catalog(session)
        await session.execute(
            update(Hotel)
            .where(Hotel.slug == "harbor-view-seattle")
            .values(name="Outdated name")
        )
        await session.commit()
        second_result = await seed_catalog(session)

        hotels_count = await session.scalar(select(func.count(Hotel.id)))
        room_types_count = await session.scalar(select(func.count(RoomType.id)))
        hotel_name = await session.scalar(
            select(Hotel.name).where(Hotel.slug == "harbor-view-seattle")
        )
        city_counts = await session.execute(
            select(Hotel.city, func.count(Hotel.id)).group_by(Hotel.city)
        )
        hotels_per_city = dict(city_counts.tuples().all())

    expected_room_types = sum(len(hotel["room_types"]) for hotel in CATALOG_SEED)
    assert first_result.hotels == second_result.hotels == len(CATALOG_SEED)
    assert first_result.room_types == second_result.room_types == expected_room_types
    assert hotels_count == len(CATALOG_SEED)
    assert room_types_count == expected_room_types
    assert hotel_name == "Harbor View Seattle"
    assert hotels_per_city == {
        "Austin": 3,
        "Miami": 3,
        "New York": 3,
        "Seattle": 3,
    }


@pytest.mark.usefixtures("clean_catalog")
async def test_hotel_details_fall_back_to_postgresql_when_redis_is_unavailable(
    client: AsyncClient,
) -> None:
    async with async_session_maker() as session:
        await seed_catalog(session)
        hotel_id = await session.scalar(
            select(Hotel.id).where(Hotel.slug == "harbor-view-seattle")
        )

    app.dependency_overrides[get_catalog_cache] = get_unavailable_catalog_cache
    response = await client.get(f"/api/v1/hotels/{hotel_id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": hotel_id,
        "slug": "harbor-view-seattle",
        "name": "Harbor View Seattle",
        "city": "Seattle",
        "country": "United States",
        "address": "2217 Western Avenue, Seattle, WA",
        "services": ["wifi", "breakfast", "parking", "fitness"],
    }


@pytest.mark.usefixtures("clean_catalog")
async def test_room_types_use_decimal_usd_prices(client: AsyncClient) -> None:
    async with async_session_maker() as session:
        await seed_catalog(session)
        hotel_id = await session.scalar(
            select(Hotel.id).where(Hotel.slug == "harbor-view-seattle")
        )

    response = await client.get(f"/api/v1/hotels/{hotel_id}/rooms")

    assert response.status_code == 200
    room_types = response.json()
    assert room_types[0]["code"] == "standard-queen"
    assert room_types[0]["currency"] == "USD"
    assert room_types[0]["price"] == "128.00"
    assert Decimal(room_types[0]["price"]) == Decimal("128.00")


async def test_unknown_hotel_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/hotels/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Hotel not found"}
