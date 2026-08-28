import io
import json
import logging
from uuid import UUID

from httpx import AsyncClient

from app.logger import ApplicationJsonFormatter, RequestContextFilter, logger


def capture_json_logs() -> tuple[io.StringIO, logging.Handler]:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RequestContextFilter())
    handler.setFormatter(
        ApplicationJsonFormatter(
            "%(timestamp)s %(level)s %(message)s %(request_id)s %(module)s %(funcName)s"
        )
    )
    logger.addHandler(handler)
    return stream, handler


async def test_request_log_uses_client_request_id(client: AsyncClient) -> None:
    stream, handler = capture_json_logs()
    try:
        response = await client.get(
            "/health",
            headers={"X-Request-ID": "client-request-42"},
        )
    finally:
        logger.removeHandler(handler)

    assert response.headers["X-Request-ID"] == "client-request-42"
    event = json.loads(stream.getvalue())
    assert event["event"] == "request_completed"
    assert event["request_id"] == "client-request-42"
    assert event["method"] == "GET"
    assert event["path"] == "/health"
    assert event["status"] == 200
    assert isinstance(event["duration_ms"], float)
    assert event["level"] == "INFO"
    assert event["timestamp"].endswith("+00:00")


async def test_unsafe_request_id_is_replaced(client: AsyncClient) -> None:
    response = await client.get(
        "/health",
        headers={"X-Request-ID": "unsafe request id"},
    )

    generated_request_id = response.headers["X-Request-ID"]
    assert generated_request_id != "unsafe request id"
    assert str(UUID(generated_request_id)) == generated_request_id
