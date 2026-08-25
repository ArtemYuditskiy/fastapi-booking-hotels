import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, update

from app.bookings.models import Booking, BookingStatus
from app.catalog.models import Hotel, RoomType
from app.catalog.seed import seed_catalog
from app.database import async_session_maker
from app.notifications.delivery import DeliveryOutcome, NotificationDeliveryService
from app.notifications.mailer import (
    OutgoingEmail,
    PermanentEmailDeliveryError,
)
from app.notifications.models import (
    Notification,
    NotificationKind,
    NotificationStatus,
)
from app.notifications.tasks import send_notification
from app.users.models import User

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_search")]


class RecordingEmailSender:
    def __init__(self) -> None:
        self.messages: list[OutgoingEmail] = []

    async def send(self, message: OutgoingEmail) -> None:
        self.messages.append(message)


class BlockingEmailSender(RecordingEmailSender):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def send(self, message: OutgoingEmail) -> None:
        self.messages.append(message)
        self.started.set()
        await self.release.wait()


class FailingEmailSender:
    async def send(self, message: OutgoingEmail) -> None:
        del message
        raise OSError("temporary SMTP outage")


class PermanentlyFailingEmailSender:
    async def send(self, message: OutgoingEmail) -> None:
        del message
        raise PermanentEmailDeliveryError("recipient rejected")


async def add_pending_notification(*, now: datetime) -> Notification:
    async with async_session_maker() as session:
        await seed_catalog(session)
        room_type = await session.scalar(
            select(RoomType)
            .join(Hotel, Hotel.id == RoomType.hotel_id)
            .where(
                Hotel.slug == "harbor-view-seattle",
                RoomType.code == "standard-queen",
            )
        )
        if room_type is None:
            raise RuntimeError("Seeded room type was not found")

        user = User(
            email=f"delivery-{now.timestamp()}@example.com",
            hashed_password="not-used-in-notification-tests",
        )
        session.add(user)
        await session.flush()

        date_from = date.today() + timedelta(days=10)
        booking = Booking(
            user_id=user.id,
            room_type_id=room_type.id,
            date_from=date_from,
            date_to=date_from + timedelta(days=2),
            price_per_night=Decimal("128.00"),
            currency="USD",
            total_cost=Decimal("256.00"),
            status=BookingStatus.CONFIRMED,
            expires_at=now + timedelta(minutes=15),
        )
        session.add(booking)
        await session.flush()

        notification = Notification(
            booking_id=booking.id,
            kind=NotificationKind.BOOKING_CONFIRMATION,
            recipient_email=user.email,
            subject=f"Booking #{booking.id} confirmed",
            body="Confirmation body",
            status=NotificationStatus.PENDING,
            attempts=0,
            next_attempt_at=now,
        )
        session.add(notification)
        await session.commit()
        return notification


async def test_parallel_delivery_claims_send_only_once() -> None:
    now = datetime.now(UTC)
    notification = await add_pending_notification(now=now)
    sender = BlockingEmailSender()

    async def deliver() -> DeliveryOutcome:
        async with async_session_maker() as session:
            result = await NotificationDeliveryService(session, sender).deliver(
                notification_id=notification.id,
                now=now,
            )
            return result.outcome

    first_delivery = asyncio.create_task(deliver())
    await sender.started.wait()
    second_outcome = await deliver()
    sender.release.set()
    first_outcome = await first_delivery

    assert first_outcome == DeliveryOutcome.SENT
    assert second_outcome == DeliveryOutcome.SKIPPED
    assert len(sender.messages) == 1

    async with async_session_maker() as session:
        stored = await session.get(Notification, notification.id)
    assert stored is not None
    assert stored.status == NotificationStatus.SENT
    assert stored.attempts == 1
    assert stored.sent_at == now
    assert stored.locked_at is None


async def test_temporary_failures_back_off_and_eventually_fail() -> None:
    now = datetime.now(UTC)
    notification = await add_pending_notification(now=now)
    sender = FailingEmailSender()

    async with async_session_maker() as session:
        first_result = await NotificationDeliveryService(
            session,
            sender,
            max_attempts=2,
            retry_base_seconds=10,
        ).deliver(notification_id=notification.id, now=now)

    assert first_result.outcome == DeliveryOutcome.RETRY
    assert first_result.retry_after_seconds == 10

    async with async_session_maker() as session:
        too_early = await NotificationDeliveryService(
            session,
            sender,
            max_attempts=2,
            retry_base_seconds=10,
        ).deliver(
            notification_id=notification.id,
            now=now + timedelta(seconds=9),
        )
    assert too_early.outcome == DeliveryOutcome.SKIPPED

    async with async_session_maker() as session:
        final_result = await NotificationDeliveryService(
            session,
            sender,
            max_attempts=2,
            retry_base_seconds=10,
        ).deliver(
            notification_id=notification.id,
            now=now + timedelta(seconds=10),
        )

    assert final_result.outcome == DeliveryOutcome.FAILED
    async with async_session_maker() as session:
        stored = await session.get(Notification, notification.id)
    assert stored is not None
    assert stored.status == NotificationStatus.FAILED
    assert stored.attempts == 2
    assert stored.locked_at is None
    assert stored.last_error == "OSError: temporary SMTP outage"


async def test_permanent_failure_does_not_retry() -> None:
    now = datetime.now(UTC)
    notification = await add_pending_notification(now=now)

    async with async_session_maker() as session:
        result = await NotificationDeliveryService(
            session,
            PermanentlyFailingEmailSender(),
        ).deliver(notification_id=notification.id, now=now)

    assert result.outcome == DeliveryOutcome.FAILED
    async with async_session_maker() as session:
        stored = await session.get(Notification, notification.id)
    assert stored is not None
    assert stored.status == NotificationStatus.FAILED
    assert stored.attempts == 1


async def test_stale_processing_claim_is_recovered() -> None:
    now = datetime.now(UTC)
    notification = await add_pending_notification(now=now)
    async with async_session_maker() as session:
        await session.execute(
            update(Notification)
            .where(Notification.id == notification.id)
            .values(
                status=NotificationStatus.PROCESSING,
                attempts=1,
                locked_at=now - timedelta(seconds=301),
            )
        )
        await session.commit()

    sender = RecordingEmailSender()
    async with async_session_maker() as session:
        service = NotificationDeliveryService(session, sender)
        dispatchable_ids = await service.list_dispatchable_ids(now=now)
        result = await service.deliver(notification_id=notification.id, now=now)

    assert notification.id in dispatchable_ids
    assert result.outcome == DeliveryOutcome.SENT
    assert len(sender.messages) == 1
    async with async_session_maker() as session:
        stored = await session.get(Notification, notification.id)
    assert stored is not None
    assert stored.status == NotificationStatus.SENT
    assert stored.attempts == 2


async def test_celery_send_task_uses_notification_id_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    notification = await add_pending_notification(now=now)
    sender = RecordingEmailSender()
    monkeypatch.setattr("app.notifications.tasks._smtp_sender", lambda: sender)

    outcome = await asyncio.to_thread(send_notification.run, notification.id)

    assert outcome == DeliveryOutcome.SENT.value
    assert len(sender.messages) == 1
    assert sender.messages[0].recipient == notification.recipient_email
