import json
from typing import Protocol

from pydantic import TypeAdapter, ValidationError
from redis.exceptions import RedisError

from app.catalog.schemas import HotelRead, RoomTypeRead
from app.config import settings
from app.logger import logger
from app.redis_client import AsyncRedisClient

CATALOG_CACHE_PREFIX = "catalog:v1"
ROOM_TYPE_LIST_ADAPTER = TypeAdapter(list[RoomTypeRead])


class CatalogCache(Protocol):
    async def get_hotel(self, hotel_id: int) -> HotelRead | None: ...

    async def set_hotel(self, hotel: HotelRead) -> None: ...

    async def get_room_types(self, hotel_id: int) -> list[RoomTypeRead] | None: ...

    async def set_room_types(
        self,
        hotel_id: int,
        room_types: list[RoomTypeRead],
    ) -> None: ...

    async def invalidate(self) -> None: ...


class RedisCatalogCache:
    def __init__(
        self,
        client: AsyncRedisClient,
        *,
        ttl_seconds: int = settings.CATALOG_CACHE_TTL_SECONDS,
    ) -> None:
        self._client = client
        self._ttl_seconds = ttl_seconds
        self._available = True

    async def get_hotel(self, hotel_id: int) -> HotelRead | None:
        key = self.hotel_key(hotel_id)
        payload = await self._get_payload(key)
        if payload is None:
            return None

        try:
            hotel = HotelRead.model_validate(payload)
        except ValidationError as error:
            await self._discard_invalid(key, error)
            return None

        self._log_hit(key)
        return hotel

    async def set_hotel(self, hotel: HotelRead) -> None:
        await self._set_payload(self.hotel_key(hotel.id), hotel.model_dump_json())

    async def get_room_types(self, hotel_id: int) -> list[RoomTypeRead] | None:
        key = self.room_types_key(hotel_id)
        payload = await self._get_payload(key)
        if payload is None:
            return None

        try:
            room_types = ROOM_TYPE_LIST_ADAPTER.validate_python(payload)
        except ValidationError as error:
            await self._discard_invalid(key, error)
            return None

        self._log_hit(key)
        return room_types

    async def set_room_types(
        self,
        hotel_id: int,
        room_types: list[RoomTypeRead],
    ) -> None:
        payload = ROOM_TYPE_LIST_ADAPTER.dump_json(room_types).decode()
        await self._set_payload(self.room_types_key(hotel_id), payload)

    async def invalidate(self) -> None:
        if not self._available:
            return

        pattern = f"{CATALOG_CACHE_PREFIX}:*"
        try:
            keys = [key async for key in self._client.scan_iter(pattern)]
            if keys:
                await self._client.delete(*keys)
        except RedisError as error:
            self._mark_unavailable(key=pattern, operation="invalidate", error=error)

    async def _get_payload(self, key: str) -> object | None:
        if not self._available:
            return None

        try:
            value = await self._client.get(key)
        except RedisError as error:
            self._mark_unavailable(key=key, operation="get", error=error)
            return None

        if value is None:
            logger.info("cache_miss", extra={"cache_key": key})
            return None

        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError, UnicodeError) as error:
            await self._discard_invalid(key, error)
            return None

    async def _set_payload(self, key: str, payload: str) -> None:
        if not self._available:
            return

        try:
            await self._client.set(key, payload, ex=self._ttl_seconds)
        except RedisError as error:
            self._mark_unavailable(key=key, operation="set", error=error)

    async def _discard_invalid(self, key: str, error: Exception) -> None:
        logger.warning(
            "cache_invalid",
            extra={"cache_key": key, "error_type": type(error).__name__},
        )
        try:
            await self._client.delete(key)
        except RedisError as redis_error:
            self._mark_unavailable(
                key=key,
                operation="delete",
                error=redis_error,
            )

    def _mark_unavailable(
        self,
        *,
        key: str,
        operation: str,
        error: RedisError,
    ) -> None:
        self._available = False
        logger.warning(
            "cache_unavailable",
            extra={
                "cache_key": key,
                "cache_operation": operation,
                "error_type": type(error).__name__,
            },
        )

    @staticmethod
    def hotel_key(hotel_id: int) -> str:
        return f"{CATALOG_CACHE_PREFIX}:hotels:{hotel_id}"

    @staticmethod
    def room_types_key(hotel_id: int) -> str:
        return f"{CATALOG_CACHE_PREFIX}:hotels:{hotel_id}:room-types"

    @staticmethod
    def _log_hit(key: str) -> None:
        logger.info("cache_hit", extra={"cache_key": key})
