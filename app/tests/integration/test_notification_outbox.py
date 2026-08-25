from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.bookings.models import Booking, BookingStatus
from app.bookings.service import BookingService
from app.catalog.models import Hotel, RoomType
from app.catalog.seed import seed_catalog
from app.database import async_session_maker
from app.notifications.models import (
    Notification,
    NotificationKind,
    NotificationStatus,
)
from app.notifications.repository import NotificationRepository
from app.users.models import User
from app.users.security import create_access_token

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_search")]


async def create_reservation_hold(client: AsyncClient) -> tuple[int, int]:
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
            email="notification-owner@example.com",
            hashed_password="not-used-in-booking-tests",
        )
        session.add(user)
        await session.commit()
        user_id = user.id
        room_type_id = room_type.id

    date_from = date.today() + timedelta(days=10)
    response = await client.post(
        "/api/v1/bookings",
        headers={
            "Authorization": f"Bearer {create_access_token(user_id)}",
        },
        json={
            "room_type_id": room_type_id,
            "date_from": date_from.isoformat(),
            "date_to": (date_from + timedelta(days=2)).isoformat(),
        },
    )
    assert response.status_code == 201
    return response.json()["id"], user_id


async def test_confirm_creates_one_pending_notification_snapshot(
    client: AsyncClient,
) -> None:
    booking_id, user_id = await create_reservation_hold(client)
    headers = {
        "Authorization": f"Bearer {create_access_token(user_id)}",
    }

    first = await client.post(
        f"/api/v1/bookings/{booking_id}/confirm",
        headers=headers,
    )
    repeated = await client.post(
        f"/api/v1/bookings/{booking_id}/confirm",
        headers=headers,
    )

    assert first.status_code == 200
    assert repeated.status_code == 200
    async with async_session_maker() as session:
        notifications = list(
            await session.scalars(
                select(Notification).where(Notification.booking_id == booking_id)
            )
        )

    assert len(notifications) == 1
    notification = notifications[0]
    assert notification.kind == NotificationKind.BOOKING_CONFIRMATION
    assert notification.status == NotificationStatus.PENDING
    assert notification.attempts == 0
    assert notification.recipient_email == "notification-owner@example.com"
    assert notification.subject == f"Booking #{booking_id} confirmed"
    assert "Total: USD 256.00." in notification.body


async def test_outbox_failure_rolls_back_booking_confirmation(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    booking_id, user_id = await create_reservation_hold(client)

    async def fail_to_add_notification(
        _repository: NotificationRepository,
        **_values: object,
    ) -> Notification:
        raise RuntimeError("simulated outbox failure")

    monkeypatch.setattr(NotificationRepository, "add", fail_to_add_notification)

    async with async_session_maker() as session:
        with pytest.raises(RuntimeError, match="simulated outbox failure"):
            await BookingService(session).confirm(
                booking_id=booking_id,
                user_id=user_id,
            )

    async with async_session_maker() as session:
        stored_status = await session.scalar(
            select(Booking.status).where(Booking.id == booking_id)
        )
        notification_count = await session.scalar(
            select(func.count(Notification.id)).where(
                Notification.booking_id == booking_id
            )
        )

    assert stored_status == BookingStatus.CREATED
    assert notification_count == 0
