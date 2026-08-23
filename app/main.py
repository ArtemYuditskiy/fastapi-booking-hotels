import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.database import engine
from app.health.router import router as health_router
from app.logger import logger
from app.users.router import router as users_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


app = FastAPI(
    title="Hotel Booking API",
    description="An API-only hotel catalog and booking service.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(users_router)
app.include_router(health_router)


@app.middleware("http")
async def log_request_duration(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    logger.info(
        "Request handled",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round(process_time * 1000, 2),
        },
    )
    return response
