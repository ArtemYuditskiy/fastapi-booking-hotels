from collections.abc import AsyncIterator
from decimal import Decimal

from redis.exceptions import RedisError

from app.catalog.cache import RedisCatalogCache
from app.catalog.schemas import HotelRead, RoomTypeRead


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.expirations: dict[str, int] = {}
        self.deleted: list[str] = []
        self.get_calls = 0
        self.fail = False

    async def get(self, key: str) -> str | None:
        self.get_calls += 1
        if self.fail:
            raise RedisError("Redis is unavailable")
        return self.values.get(key)

    async def set(self, key: str, value: str, *, ex: int) -> None:
        if self.fail:
            raise RedisError("Redis is unavailable")
        self.values[key] = value
        self.expirations[key] = ex

    async def delete(self, *keys: str) -> None:
        if self.fail:
            raise RedisError("Redis is unavailable")
        for key in keys:
            self.values.pop(key, None)
            self.deleted.append(key)

    async def scan_iter(self, match: str) -> AsyncIterator[str]:
        if self.fail:
            raise RedisError("Redis is unavailable")
        prefix = match.removesuffix("*")
        for key in list(self.values):
            if key.startswith(prefix):
                yield key


def build_hotel() -> HotelRead:
    return HotelRead(
        id=7,
        slug="harbor-view-seattle",
        name="Harbor View Seattle",
        city="Seattle",
        country="United States",
        address="2217 Western Avenue, Seattle, WA",
        services=["wifi", "breakfast"],
    )


def build_room_type() -> RoomTypeRead:
    return RoomTypeRead(
        id=11,
        hotel_id=7,
        code="standard-queen",
        name="Standard Queen",
        description="A quiet queen room for short city stays.",
        price=Decimal("128.00"),
        currency="USD",
        quantity=12,
        services=["wifi", "workspace"],
    )


async def test_cache_round_trip_preserves_typed_catalog_data() -> None:
    redis = FakeRedis()
    cache = RedisCatalogCache(redis, ttl_seconds=90)

    await cache.set_hotel(build_hotel())
    await cache.set_room_types(7, [build_room_type()])

    hotel = await cache.get_hotel(7)
    room_types = await cache.get_room_types(7)
    assert hotel == build_hotel()
    assert room_types == [build_room_type()]
    assert redis.expirations == {
        "catalog:v1:hotels:7": 90,
        "catalog:v1:hotels:7:room-types": 90,
    }


async def test_cache_miss_returns_none() -> None:
    cache = RedisCatalogCache(FakeRedis())

    assert await cache.get_hotel(404) is None


async def test_unavailable_cache_is_disabled_for_the_current_request() -> None:
    redis = FakeRedis()
    redis.fail = True
    cache = RedisCatalogCache(redis)

    assert await cache.get_hotel(7) is None
    assert await cache.get_room_types(7) is None
    await cache.set_hotel(build_hotel())

    assert redis.get_calls == 1


async def test_invalid_cache_entry_is_deleted_and_treated_as_a_miss() -> None:
    redis = FakeRedis()
    key = "catalog:v1:hotels:7"
    redis.values[key] = "not-json"
    cache = RedisCatalogCache(redis)

    assert await cache.get_hotel(7) is None
    assert key in redis.deleted


async def test_invalidation_removes_only_versioned_catalog_keys() -> None:
    redis = FakeRedis()
    redis.values = {
        "catalog:v1:hotels:7": "{}",
        "catalog:v1:hotels:8": "{}",
        "celery-task-meta-1": "{}",
    }
    cache = RedisCatalogCache(redis)

    await cache.invalidate()

    assert redis.values == {"celery-task-meta-1": "{}"}
