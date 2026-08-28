import pytest
from redis.asyncio import Redis

from app.catalog.cache import RedisCatalogCache
from app.catalog.schemas import HotelRead
from app.config import settings
from app.redis_client import create_redis_client

pytestmark = pytest.mark.integration

HOTEL_ID = 987654
PRESERVED_KEY = "celery-smoke-key"


def build_hotel() -> HotelRead:
    return HotelRead(
        id=HOTEL_ID,
        slug="redis-smoke-hotel",
        name="Redis Smoke Hotel",
        city="Seattle",
        country="United States",
        address="1 Cache Lane, Seattle, WA",
        services=["wifi"],
    )


async def test_real_redis_round_trip_ttl_and_invalidation() -> None:
    raw_client = Redis.from_url(settings.REDIS_CACHE_URL, decode_responses=True)
    client = create_redis_client(settings.REDIS_CACHE_URL)
    cache = RedisCatalogCache(client, ttl_seconds=30)
    hotel_key = cache.hotel_key(HOTEL_ID)

    try:
        await raw_client.delete(hotel_key, PRESERVED_KEY)
        await raw_client.set(PRESERVED_KEY, "preserve")

        await cache.set_hotel(build_hotel())

        assert await cache.get_hotel(HOTEL_ID) == build_hotel()
        assert 1 <= await raw_client.ttl(hotel_key) <= 30

        await cache.invalidate()

        assert await raw_client.get(hotel_key) is None
        assert await raw_client.get(PRESERVED_KEY) == "preserve"
    finally:
        await raw_client.delete(hotel_key, PRESERVED_KEY)
        await client.close()
        await raw_client.aclose()
