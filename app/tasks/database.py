import asyncio
from collections.abc import Awaitable, Callable

from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

type DatabaseOperation[ResultT] = Callable[[AsyncSession], Awaitable[ResultT]]


async def _run_database_operation[ResultT](
    operation: DatabaseOperation[ResultT],
) -> ResultT:
    engine = create_async_engine(
        settings.active_database_url,
        poolclass=NullPool,
    )
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_maker() as session:
            return await operation(session)
    finally:
        await engine.dispose()


def run_database_task[ResultT](operation: DatabaseOperation[ResultT]) -> ResultT:
    return asyncio.run(_run_database_operation(operation))
