from celery import Celery

from app.config import settings

celery = Celery(
    "hotel_booking",
    broker=settings.CELERY_BROKER_URL,
    include=["app.bookings.tasks"],
)

celery.conf.update(
    accept_content=["json"],
    beat_schedule={
        "expire-booking-holds": {
            "task": "bookings.expire_holds",
            "schedule": float(settings.CELERY_BEAT_INTERVAL_SECONDS),
        },
    },
    broker_connection_retry_on_startup=True,
    enable_utc=True,
    result_backend=None,
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_ignore_result=True,
    task_serializer="json",
    timezone="UTC",
)
