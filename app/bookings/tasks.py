from sqlalchemy.ext.asyncio import AsyncSession

from app.bookings.expiration import BookingExpirationService
from app.logger import logger
from app.tasks.celery import celery
from app.tasks.database import run_database_task


async def _expire_due_holds(session: AsyncSession) -> int:
    booking_ids = await BookingExpirationService(session).expire_due_holds()
    return len(booking_ids)


@celery.task(name="bookings.expire_holds", ignore_result=True)
def expire_booking_holds() -> int:
    try:
        expired_count = run_database_task(_expire_due_holds)
    except Exception:
        logger.exception("booking_expiration_failed")
        raise

    logger.info(
        "booking_expiration_completed",
        extra={"expired_count": expired_count},
    )
    return expired_count
