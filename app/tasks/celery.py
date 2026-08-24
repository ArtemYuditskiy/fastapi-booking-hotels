from celery import Celery

from app.config import settings

celery = Celery(
    "hotel_booking",
    broker=settings.CELERY_BROKER_URL,
)
