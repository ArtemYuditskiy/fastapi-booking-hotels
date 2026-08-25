import asyncio
import os
from collections.abc import AsyncIterator, Iterator

os.environ["MODE"] = "TEST"

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.bookings.models import Booking
from app.catalog.cache import CatalogCache
from app.catalog.dependencies import get_catalog_cache
from app.catalog.models import Hotel, RoomType
from app.catalog.schemas import HotelRead, RoomTypeRead
from app.config import settings
from app.database import async_session_maker
from app.main import app
from app.users.models import User


class EmptyCatalogCache:
    async def get_hotel(self, hotel_id: int) -> HotelRead | None:
        return None

    async def set_hotel(self, hotel: HotelRead) -> None:
        return None

    async def get_room_types(self, hotel_id: int) -> list[RoomTypeRead] | None:
        return None

    async def set_room_types(
        self,
        hotel_id: int,
        room_types: list[RoomTypeRead],
    ) -> None:
        return None

    async def invalidate(self) -> None:
        return None


def get_empty_catalog_cache() -> CatalogCache:
    return EmptyCatalogCache()


async def reset_test_schema() -> None:
    test_engine = create_async_engine(settings.TEST_DATABASE_URL)
    async with test_engine.begin() as connection:
        await connection.execute(text("DROP SCHEMA public CASCADE"))
        await connection.execute(text("CREATE SCHEMA public"))
    await test_engine.dispose()


@pytest.fixture(scope="session")
def migrated_database() -> Iterator[None]:
    if settings.TEST_DATABASE_URL == settings.DATABASE_URL:
        raise RuntimeError("TEST_DATABASE_URL must differ from DATABASE_URL")

    asyncio.run(reset_test_schema())
    alembic_config = Config("alembic.ini")
    command.upgrade(alembic_config, "head")
    yield


@pytest.fixture
async def clean_users(migrated_database: None) -> AsyncIterator[None]:
    async with async_session_maker() as session:
        await session.execute(delete(Booking))
        await session.execute(delete(User))
        await session.commit()
    yield
    async with async_session_maker() as session:
        await session.execute(delete(Booking))
        await session.execute(delete(User))
        await session.commit()


@pytest.fixture
async def clean_catalog(migrated_database: None) -> AsyncIterator[None]:
    async with async_session_maker() as session:
        await session.execute(delete(Booking))
        await session.execute(delete(RoomType))
        await session.execute(delete(Hotel))
        await session.commit()
    yield
    async with async_session_maker() as session:
        await session.execute(delete(Booking))
        await session.execute(delete(RoomType))
        await session.execute(delete(Hotel))
        await session.commit()


@pytest.fixture
async def clean_search(migrated_database: None) -> AsyncIterator[None]:
    async with async_session_maker() as session:
        await session.execute(delete(Booking))
        await session.execute(delete(RoomType))
        await session.execute(delete(Hotel))
        await session.execute(delete(User))
        await session.commit()
    yield
    async with async_session_maker() as session:
        await session.execute(delete(Booking))
        await session.execute(delete(RoomType))
        await session.execute(delete(Hotel))
        await session.execute(delete(User))
        await session.commit()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_catalog_cache] = get_empty_catalog_cache
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_catalog_cache, None)
