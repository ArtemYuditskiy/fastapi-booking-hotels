from collections.abc import AsyncIterator
from typing import Protocol

from redis.asyncio import Redis

from app.config import settings


class AsyncRedisClient(Protocol):
    async def get(self, key: str) -> str | bytes | None: ...

    async def set(self, key: str, value: str, *, ex: int) -> None: ...

    async def delete(self, *keys: str) -> None: ...

    def scan_iter(self, match: str) -> AsyncIterator[str]: ...


class RedisClient:
    def __init__(self, client: Redis) -> None:
        self._client = client

    async def get(self, key: str) -> str | bytes | None:
        value = await self._client.get(key)
        if value is None or isinstance(value, (str, bytes)):
            return value
        raise TypeError("Redis returned an unsupported value type")

    async def set(self, key: str, value: str, *, ex: int) -> None:
        await self._client.set(key, value, ex=ex)

    async def delete(self, *keys: str) -> None:
        await self._client.delete(*keys)

    async def scan_iter(self, match: str) -> AsyncIterator[str]:
        async for key in self._client.scan_iter(match=match):
            if isinstance(key, bytes):
                yield key.decode()
            elif isinstance(key, str):
                yield key
            else:
                raise TypeError("Redis returned an unsupported key type")

    async def close(self) -> None:
        await self._client.aclose()


def create_redis_client(url: str | None = None) -> RedisClient:
    client = Redis.from_url(
        url or settings.REDIS_CACHE_URL,
        decode_responses=True,
        socket_connect_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
        socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
    )
    return RedisClient(client)


redis_client = create_redis_client()
