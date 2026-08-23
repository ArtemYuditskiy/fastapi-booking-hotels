import logging
from datetime import UTC, datetime

from pythonjsonlogger.json import JsonFormatter

from app.config import settings


class CustomJsonFormatter(JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        if not log_record.get("timestamp"):
            log_record["timestamp"] = datetime.now(UTC).isoformat(
                timespec="milliseconds"
            )
        log_record["level"] = record.levelname.upper()


logger = logging.getLogger("hotel_booking")
logger.setLevel(settings.LOG_LEVEL)
logger.propagate = False

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        CustomJsonFormatter(
            "%(timestamp)s %(level)s %(message)s %(module)s %(funcName)s"
        )
    )
    logger.addHandler(handler)
