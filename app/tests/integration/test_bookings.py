from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.bookings.models import Booking, BookingStatus
from app.bookings.policy import BOOKING_HOLD_DURATION
from app.catalog.models import Hotel, RoomType
from app.catalog.seed import seed_catalog
from app.database import async_session_maker
from app.users.models import User
from app.users.security import create_access_token

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_search")]

DATE_FROM = date.today() + timedelta(days=10)
DATE_TO = DATE_FROM + timedelta(days=3)


def auth_headers(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def booking_payload(
    room_type_id: int,
    *,
    date_from: date = DATE_FROM,
    date_to: date = DATE_TO,
) -> dict[str, object]:
    return {
        "room_type_id": room_type_id,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
    }


async def add_user(session: AsyncSession, email: str) -> User:
    user = User(email=email, hashed_password="not-used-in-booking-tests")
    session.add(user)
    await session.flush()
    return user


async def prepare_room(
    session: AsyncSession,
    *,
    quantity: int | None = None,
) -> RoomType:
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
    if quantity is not None:
        room_type.quantity = quantity
    return room_type


async def create_booking(
    client: AsyncClient,
    *,
    user_id: int,
    room_type_id: int,
    date_from: date = DATE_FROM,
    date_to: date = DATE_TO,
) -> Response:
    return await client.post(
        "/api/v1/bookings",
        headers=auth_headers(user_id),
        json=booking_payload(
            room_type_id,
            date_from=date_from,
            date_to=date_to,
        ),
    )


async def test_create_booking_stores_a_fifteen_minute_usd_hold(
    client: AsyncClient,
) -> None:
    async with async_session_maker() as session:
        room_type = await prepare_room(session)
        user = await add_user(session, "owner@example.com")
        await session.commit()

    before_request = datetime.now(UTC)
    response = await create_booking(
        client,
        user_id=user.id,
        room_type_id=room_type.id,
    )
    after_request = datetime.now(UTC)

    assert response.status_code == 201
    payload = response.json()
    assert payload["user_id"] == user.id
    assert payload["room_type_id"] == room_type.id
    assert payload["status"] == "created"
    assert payload["price_per_night"] == "128.00"
    assert payload["currency"] == "USD"
    assert payload["total_cost"] == "384.00"
    expires_at = datetime.fromisoformat(payload["expires_at"])
    assert before_request + BOOKING_HOLD_DURATION <= expires_at
    assert expires_at <= after_request + BOOKING_HOLD_DURATION


async def test_active_hold_blocks_inventory_but_adjacent_dates_do_not(
    client: AsyncClient,
) -> None:
    async with async_session_maker() as session:
        room_type = await prepare_room(session, quantity=1)
        user = await add_user(session, "owner@example.com")
        await session.commit()

    first = await create_booking(
        client,
        user_id=user.id,
        room_type_id=room_type.id,
    )
    overlap = await create_booking(
        client,
        user_id=user.id,
        room_type_id=room_type.id,
    )
    adjacent = await create_booking(
        client,
        user_id=user.id,
        room_type_id=room_type.id,
        date_from=DATE_TO,
        date_to=DATE_TO + timedelta(days=2),
    )

    assert first.status_code == 201
    assert overlap.status_code == 409
    assert overlap.json() == {"detail": "No rooms are available for the selected dates"}
    assert adjacent.status_code == 201


async def test_confirm_and_cancel_are_idempotent(client: AsyncClient) -> None:
    async with async_session_maker() as session:
        room_type = await prepare_room(session)
        user = await add_user(session, "owner@example.com")
        await session.commit()

    created = await create_booking(
        client,
        user_id=user.id,
        room_type_id=room_type.id,
    )
    booking_id = created.json()["id"]
    headers = auth_headers(user.id)

    confirmed = await client.post(
        f"/api/v1/bookings/{booking_id}/confirm",
        headers=headers,
    )
    confirmed_again = await client.post(
        f"/api/v1/bookings/{booking_id}/confirm",
        headers=headers,
    )
    cancelled = await client.delete(
        f"/api/v1/bookings/{booking_id}",
        headers=headers,
    )
    cancelled_again = await client.delete(
        f"/api/v1/bookings/{booking_id}",
        headers=headers,
    )
    confirmation_conflict = await client.post(
        f"/api/v1/bookings/{booking_id}/confirm",
        headers=headers,
    )

    assert confirmed.json()["status"] == "confirmed"
    assert confirmed_again.json()["status"] == "confirmed"
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled_again.json()["status"] == "cancelled"
    assert confirmation_conflict.status_code == 409
    assert confirmation_conflict.json() == {
        "detail": "Booking cannot be confirmed in its current state"
    }


async def test_booking_endpoints_hide_another_users_booking(
    client: AsyncClient,
) -> None:
    async with async_session_maker() as session:
        room_type = await prepare_room(session)
        owner = await add_user(session, "owner@example.com")
        stranger = await add_user(session, "stranger@example.com")
        await session.commit()

    created = await create_booking(
        client,
        user_id=owner.id,
        room_type_id=room_type.id,
    )
    booking_id = created.json()["id"]
    stranger_headers = auth_headers(stranger.id)

    listed = await client.get("/api/v1/bookings", headers=stranger_headers)
    detail = await client.get(
        f"/api/v1/bookings/{booking_id}",
        headers=stranger_headers,
    )
    confirmed = await client.post(
        f"/api/v1/bookings/{booking_id}/confirm",
        headers=stranger_headers,
    )
    cancelled = await client.delete(
        f"/api/v1/bookings/{booking_id}",
        headers=stranger_headers,
    )

    assert listed.json() == []
    assert detail.status_code == 404
    assert confirmed.status_code == 404
    assert cancelled.status_code == 404
    assert (
        detail.json()
        == confirmed.json()
        == cancelled.json()
        == {"detail": "Booking not found"}
    )


async def test_expired_hold_is_reported_and_cannot_be_confirmed(
    client: AsyncClient,
) -> None:
    async with async_session_maker() as session:
        room_type = await prepare_room(session, quantity=1)
        user = await add_user(session, "owner@example.com")
        await session.commit()

    created = await create_booking(
        client,
        user_id=user.id,
        room_type_id=room_type.id,
    )
    booking_id = created.json()["id"]
    async with async_session_maker() as session:
        await session.execute(
            update(Booking)
            .where(Booking.id == booking_id)
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()

    headers = auth_headers(user.id)
    detail = await client.get(f"/api/v1/bookings/{booking_id}", headers=headers)
    available_search = await client.get(
        "/api/v1/hotels",
        params={
            "city": "Seattle",
            "date_from": DATE_FROM.isoformat(),
            "date_to": DATE_TO.isoformat(),
        },
    )
    confirmation = await client.post(
        f"/api/v1/bookings/{booking_id}/confirm",
        headers=headers,
    )

    assert detail.json()["status"] == "expired"
    available_room = next(
        room
        for hotel in available_search.json()
        for room in hotel["rooms"]
        if room["room_type_id"] == room_type.id
    )
    assert available_room["rooms_left"] == 1
    assert confirmation.status_code == 409
    assert confirmation.json() == {"detail": "Booking hold has expired"}
    async with async_session_maker() as session:
        stored_status = await session.scalar(
            select(Booking.status).where(Booking.id == booking_id)
        )
    assert stored_status == BookingStatus.EXPIRED


async def test_booking_routes_require_bearer_authentication(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/bookings")

    assert response.status_code == 401


async def test_unknown_room_type_returns_404(client: AsyncClient) -> None:
    async with async_session_maker() as session:
        user = await add_user(session, "owner@example.com")
        await session.commit()

    response = await create_booking(
        client,
        user_id=user.id,
        room_type_id=999999,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Room type not found"}
