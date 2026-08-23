from celery import Celery

from app.config import settings

celery = Celery(
    "hotel_booking",
    broker=settings.REDIS_URL,
)
