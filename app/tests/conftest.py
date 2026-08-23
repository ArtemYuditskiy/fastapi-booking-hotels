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

from app.config import settings
from app.database import async_session_maker
from app.main import app
from app.users.models import User


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
        await session.execute(delete(User))
        await session.commit()
    yield
    async with async_session_maker() as session:
        await session.execute(delete(User))
        await session.commit()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client
