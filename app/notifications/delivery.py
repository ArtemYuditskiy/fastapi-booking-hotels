from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.logger import logger
from app.notifications.mailer import (
    EmailSender,
    OutgoingEmail,
    PermanentEmailDeliveryError,
)
from app.notifications.models import Notification, NotificationStatus
from app.notifications.repository import NotificationRepository


class DeliveryOutcome(StrEnum):
    SENT = "sent"
    SKIPPED = "skipped"
    RETRY = "retry"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    outcome: DeliveryOutcome
    retry_after_seconds: int | None = None


class NotificationDeliveryService:
    def __init__(
        self,
        session: AsyncSession,
        sender: EmailSender,
        *,
        max_attempts: int = settings.NOTIFICATION_MAX_ATTEMPTS,
        retry_base_seconds: int = settings.NOTIFICATION_RETRY_BASE_SECONDS,
        claim_timeout_seconds: int = settings.NOTIFICATION_CLAIM_TIMEOUT_SECONDS,
    ) -> None:
        self._session = session
        self._sender = sender
        self._max_attempts = max_attempts
        self._retry_base_seconds = retry_base_seconds
        self._claim_timeout = timedelta(seconds=claim_timeout_seconds)
        self._repository = NotificationRepository(session)

    async def list_dispatchable_ids(
        self,
        *,
        now: datetime | None = None,
        limit: int = settings.NOTIFICATION_BATCH_SIZE,
    ) -> list[int]:
        current_time = now or datetime.now(UTC)
        return await self._repository.list_dispatchable_ids(
            now=current_time,
            stale_before=current_time - self._claim_timeout,
            limit=limit,
        )

    async def deliver(
        self,
        *,
        notification_id: int,
        now: datetime | None = None,
    ) -> DeliveryResult:
        current_time = now or datetime.now(UTC)
        notification = await self._claim(
            notification_id=notification_id,
            now=current_time,
        )
        if notification is None:
            return DeliveryResult(DeliveryOutcome.SKIPPED)

        message = OutgoingEmail(
            recipient=notification.recipient_email,
            sender=settings.SMTP_FROM_EMAIL,
            subject=notification.subject,
            body=notification.body,
        )
        try:
            await self._sender.send(message)
        except Exception as error:
            return await self._record_failure(
                notification=notification,
                error=error,
                now=current_time,
            )

        marked_sent = await self._mark_sent(notification=notification, now=current_time)
        if not marked_sent:
            return DeliveryResult(DeliveryOutcome.SKIPPED)

        logger.info(
            "notification_sent",
            extra={
                "notification_id": notification.id,
                "booking_id": notification.booking_id,
                "attempt": notification.attempts,
            },
        )
        return DeliveryResult(DeliveryOutcome.SENT)

    async def _claim(
        self,
        *,
        notification_id: int,
        now: datetime,
    ) -> Notification | None:
        try:
            notification = await self._repository.claim_for_delivery(
                notification_id=notification_id,
                now=now,
                stale_before=now - self._claim_timeout,
            )
            await self._session.commit()
            return notification
        except Exception:
            await self._session.rollback()
            raise

    async def _mark_sent(
        self,
        *,
        notification: Notification,
        now: datetime,
    ) -> bool:
        if notification.locked_at is None:
            return False

        try:
            claimed = await self._repository.get_claimed_for_update(
                notification_id=notification.id,
                locked_at=notification.locked_at,
            )
            if claimed is None:
                await self._session.rollback()
                return False
            claimed.status = NotificationStatus.SENT
            claimed.sent_at = now
            claimed.locked_at = None
            claimed.last_error = None
            await self._session.commit()
            return True
        except Exception:
            await self._session.rollback()
            raise

    async def _record_failure(
        self,
        *,
        notification: Notification,
        error: Exception,
        now: datetime,
    ) -> DeliveryResult:
        if notification.locked_at is None:
            return DeliveryResult(DeliveryOutcome.SKIPPED)

        is_final = (
            isinstance(error, PermanentEmailDeliveryError)
            or notification.attempts >= self._max_attempts
        )
        retry_after = self._retry_base_seconds * 2 ** (notification.attempts - 1)

        try:
            claimed = await self._repository.get_claimed_for_update(
                notification_id=notification.id,
                locked_at=notification.locked_at,
            )
            if claimed is None:
                await self._session.rollback()
                return DeliveryResult(DeliveryOutcome.SKIPPED)

            claimed.status = (
                NotificationStatus.FAILED if is_final else NotificationStatus.PENDING
            )
            claimed.locked_at = None
            claimed.last_error = f"{type(error).__name__}: {error}"[:500]
            if not is_final:
                claimed.next_attempt_at = now + timedelta(seconds=retry_after)
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        log_context = {
            "notification_id": notification.id,
            "booking_id": notification.booking_id,
            "attempt": notification.attempts,
        }
        if is_final:
            logger.error("notification_failed", extra=log_context)
            return DeliveryResult(DeliveryOutcome.FAILED)

        logger.warning(
            "notification_retry_scheduled",
            extra={**log_context, "retry_after_seconds": retry_after},
        )
        return DeliveryResult(DeliveryOutcome.RETRY, retry_after)
