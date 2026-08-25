import re
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import RequestResponseEndpoint

from app.bookings.router import router as bookings_router
from app.catalog.router import router as catalog_router
from app.database import engine
from app.health.router import router as health_router
from app.logger import bind_request_id, logger, reset_request_id
from app.redis_client import redis_client
from app.users.router import router as users_router

REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,64}")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await redis_client.close()
        await engine.dispose()


app = FastAPI(
    title="Hotel Booking API",
    description="An API-only hotel catalog and booking service.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(users_router)
app.include_router(catalog_router)
app.include_router(bookings_router)
app.include_router(health_router)


@app.middleware("http")
async def log_request_duration(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    supplied_request_id = request.headers.get("X-Request-ID")
    request_id = (
        supplied_request_id
        if supplied_request_id and REQUEST_ID_PATTERN.fullmatch(supplied_request_id)
        else str(uuid4())
    )
    request_id_token = bind_request_id(request_id)
    start_time = time.perf_counter()
    try:
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            "request_completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.exception(
            "request_failed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": 500,
                "duration_ms": duration_ms,
            },
        )
        raise
    finally:
        reset_request_id(request_id_token)
