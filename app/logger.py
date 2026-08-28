import logging
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

from pythonjsonlogger.json import JsonFormatter

from app.config import settings

request_id_context: ContextVar[str | None] = ContextVar(
    "request_id",
    default=None,
)


def bind_request_id(request_id: str) -> Token[str | None]:
    return request_id_context.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    request_id_context.reset(token)


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_context.get()
        return True


class ApplicationJsonFormatter(JsonFormatter):
    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        if not log_record.get("timestamp"):
            log_record["timestamp"] = datetime.now(UTC).isoformat(
                timespec="milliseconds"
            )
        log_record["level"] = record.levelname.upper()
        log_record["event"] = log_record.pop("message", record.getMessage())


logger = logging.getLogger("hotel_booking")
logger.setLevel(settings.LOG_LEVEL)
logger.propagate = False

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.addFilter(RequestContextFilter())
    handler.setFormatter(
        ApplicationJsonFormatter(
            "%(timestamp)s %(level)s %(message)s %(request_id)s %(module)s %(funcName)s"
        )
    )
    logger.addHandler(handler)
