import asyncio
from collections import Counter
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.bookings.models import Booking
from app.catalog.models import Hotel, RoomType
from app.catalog.seed import seed_catalog
from app.database import async_session_maker
from app.users.models import User
from app.users.security import create_access_token

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_search")]


async def test_concurrent_requests_cannot_exceed_room_quantity(
    client: AsyncClient,
) -> None:
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
        room_type.quantity = 3
        user = User(
            email="concurrent-owner@example.com",
            hashed_password="not-used-in-booking-tests",
        )
        session.add(user)
        await session.commit()
        room_type_id = room_type.id
        user_id = user.id

    date_from = date.today() + timedelta(days=10)
    payload = {
        "room_type_id": room_type_id,
        "date_from": date_from.isoformat(),
        "date_to": (date_from + timedelta(days=2)).isoformat(),
    }
    headers = {
        "Authorization": f"Bearer {create_access_token(user_id)}",
    }

    responses = await asyncio.gather(
        *(
            client.post(
                "/api/v1/bookings",
                headers=headers,
                json=payload,
            )
            for _ in range(10)
        )
    )

    status_counts = Counter(response.status_code for response in responses)
    assert status_counts == {201: 3, 409: 7}
    assert all(
        response.json() == {"detail": "No rooms are available for the selected dates"}
        for response in responses
        if response.status_code == 409
    )

    async with async_session_maker() as session:
        stored_bookings = await session.scalar(
            select(func.count(Booking.id)).where(
                Booking.room_type_id == room_type_id,
                Booking.date_from == date_from,
                Booking.date_to == date_from + timedelta(days=2),
            )
        )
    assert stored_bookings == 3
