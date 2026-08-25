import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.bookings.expiration import BookingExpirationService
from app.bookings.models import Booking, BookingStatus
from app.bookings.tasks import expire_booking_holds
from app.catalog.models import Hotel, RoomType
from app.catalog.seed import seed_catalog
from app.database import async_session_maker
from app.users.models import User

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_search")]


async def add_booking(
    *,
    status: BookingStatus,
    expires_at: datetime,
) -> Booking:
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
            email=f"expiration-{status.value}-{expires_at.timestamp()}@example.com",
            hashed_password="not-used-in-booking-tests",
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
            status=status,
            expires_at=expires_at,
        )
        session.add(booking)
        await session.commit()
        return booking


async def test_expiration_service_updates_only_due_created_holds() -> None:
    now = datetime.now(UTC)
    due = await add_booking(
        status=BookingStatus.CREATED,
        expires_at=now - timedelta(seconds=1),
    )
    future = await add_booking(
        status=BookingStatus.CREATED,
        expires_at=now + timedelta(hours=1),
    )
    confirmed = await add_booking(
        status=BookingStatus.CONFIRMED,
        expires_at=now - timedelta(hours=1),
    )
    cancelled = await add_booking(
        status=BookingStatus.CANCELLED,
        expires_at=now - timedelta(hours=1),
    )

    async with async_session_maker() as session:
        expired_ids = await BookingExpirationService(session).expire_due_holds(now=now)
        repeated_ids = await BookingExpirationService(session).expire_due_holds(now=now)

    assert expired_ids == [due.id]
    assert repeated_ids == []

    async with async_session_maker() as session:
        rows = (
            await session.execute(
                select(Booking.id, Booking.status).where(
                    Booking.id.in_([due.id, future.id, confirmed.id, cancelled.id])
                )
            )
        ).tuples()
        stored_statuses = {booking_id: status for booking_id, status in rows}

    assert stored_statuses == {
        due.id: BookingStatus.EXPIRED,
        future.id: BookingStatus.CREATED,
        confirmed.id: BookingStatus.CONFIRMED,
        cancelled.id: BookingStatus.CANCELLED,
    }


async def test_celery_task_runs_async_database_work_on_an_isolated_loop() -> None:
    due = await add_booking(
        status=BookingStatus.CREATED,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )

    expired_count = await asyncio.to_thread(expire_booking_holds.run)

    assert expired_count == 1
    async with async_session_maker() as session:
        stored_status = await session.scalar(
            select(Booking.status).where(Booking.id == due.id)
        )
    assert stored_status == BookingStatus.EXPIRED
