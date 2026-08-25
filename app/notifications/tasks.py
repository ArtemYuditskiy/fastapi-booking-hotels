from celery.app.task import Task
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.logger import logger
from app.notifications.delivery import (
    DeliveryOutcome,
    DeliveryResult,
    NotificationDeliveryService,
)
from app.notifications.mailer import SMTPEmailSender
from app.tasks.celery import celery
from app.tasks.database import run_database_task


def _smtp_sender() -> SMTPEmailSender:
    return SMTPEmailSender(
        host=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        timeout=settings.SMTP_TIMEOUT_SECONDS,
    )


async def _list_dispatchable_ids(session: AsyncSession) -> list[int]:
    return await NotificationDeliveryService(
        session,
        _smtp_sender(),
    ).list_dispatchable_ids()


async def _deliver_notification(
    session: AsyncSession,
    *,
    notification_id: int,
) -> DeliveryResult:
    return await NotificationDeliveryService(
        session,
        _smtp_sender(),
    ).deliver(notification_id=notification_id)


@celery.task(name="notifications.dispatch_pending", ignore_result=True)
def dispatch_pending_notifications() -> int:
    notification_ids = run_database_task(_list_dispatchable_ids)
    dispatched_count = 0

    for notification_id in notification_ids:
        try:
            send_notification.delay(notification_id)
        except Exception:
            logger.exception(
                "notification_dispatch_failed",
                extra={"notification_id": notification_id},
            )
        else:
            dispatched_count += 1

    logger.info(
        "notification_dispatch_completed",
        extra={
            "candidate_count": len(notification_ids),
            "dispatched_count": dispatched_count,
        },
    )
    return dispatched_count


@celery.task(
    bind=True,
    name="notifications.send",
    ignore_result=True,
    max_retries=None,
)
def send_notification(task: Task, notification_id: int) -> str:
    result = run_database_task(
        lambda session: _deliver_notification(
            session,
            notification_id=notification_id,
        )
    )
    if result.outcome == DeliveryOutcome.RETRY:
        raise task.retry(
            countdown=result.retry_after_seconds,
            max_retries=None,
        )
    return result.outcome.value
