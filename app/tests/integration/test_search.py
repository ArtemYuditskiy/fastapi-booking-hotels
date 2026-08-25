from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bookings.models import Booking, BookingStatus
from app.catalog.models import Hotel, RoomType
from app.catalog.seed import seed_catalog
from app.database import async_session_maker
from app.users.models import User

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_search")]

DATE_FROM = date.today() + timedelta(days=10)
DATE_TO = DATE_FROM + timedelta(days=3)


def search_params(**overrides: str) -> dict[str, str]:
    params = {
        "city": "Seattle",
        "date_from": DATE_FROM.isoformat(),
        "date_to": DATE_TO.isoformat(),
    }
    params.update(overrides)
    return params


async def prepare_search_data(session: AsyncSession) -> tuple[User, RoomType]:
    await seed_catalog(session)
    user = User(email="traveler@example.com", hashed_password="not-used-in-this-test")
    session.add(user)
    await session.flush()
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
    await session.commit()
    return user, room_type


def build_booking(
    *,
    user_id: int,
    room_type: RoomType,
    status: BookingStatus,
    date_from: date = DATE_FROM,
    date_to: date = DATE_TO,
    expires_at: datetime | None = None,
) -> Booking:
    nights = (date_to - date_from).days
    return Booking(
        user_id=user_id,
        room_type_id=room_type.id,
        date_from=date_from,
        date_to=date_to,
        price_per_night=room_type.price,
        currency="USD",
        total_cost=room_type.price * nights,
        status=status,
        expires_at=expires_at or datetime.now(UTC) + timedelta(minutes=15),
    )


def find_room(payload: list[dict[str, object]], code: str) -> dict[str, object]:
    for hotel in payload:
        rooms = hotel["rooms"]
        if not isinstance(rooms, list):
            continue
        for room in rooms:
            if isinstance(room, dict) and room.get("code") == code:
                return room
    raise AssertionError(f"Room type {code} was not found in search results")


async def test_search_returns_city_hotels_with_usd_totals(
    client: AsyncClient,
) -> None:
    async with async_session_maker() as session:
        await seed_catalog(session)

    response = await client.get(
        "/api/v1/hotels",
        params=search_params(city="  sEaTtLe  "),
    )

    assert response.status_code == 200
    payload = response.json()
    assert [hotel["name"] for hotel in payload] == [
        "Harbor View Seattle",
        "Lake Union Lodge",
        "Pioneer Square House",
    ]
    assert {hotel["city"] for hotel in payload} == {"Seattle"}
    room = find_room(payload, "standard-queen")
    assert room["rooms_left"] == 12
    assert room["price_per_night"] == "128.00"
    assert room["currency"] == "USD"
    assert room["total_cost"] == "384.00"


async def test_search_counts_only_overlapping_active_bookings(
    client: AsyncClient,
) -> None:
    async with async_session_maker() as session:
        user, room_type = await prepare_search_data(session)
        now = datetime.now(UTC)
        session.add_all(
            [
                build_booking(
                    user_id=user.id,
                    room_type=room_type,
                    status=BookingStatus.CONFIRMED,
                ),
                build_booking(
                    user_id=user.id,
                    room_type=room_type,
                    status=BookingStatus.CREATED,
                    expires_at=now + timedelta(minutes=10),
                ),
                build_booking(
                    user_id=user.id,
                    room_type=room_type,
                    status=BookingStatus.CREATED,
                    expires_at=now - timedelta(minutes=1),
                ),
                build_booking(
                    user_id=user.id,
                    room_type=room_type,
                    status=BookingStatus.CANCELLED,
                ),
                build_booking(
                    user_id=user.id,
                    room_type=room_type,
                    status=BookingStatus.CONFIRMED,
                    date_from=DATE_FROM - timedelta(days=2),
                    date_to=DATE_FROM,
                ),
                build_booking(
                    user_id=user.id,
                    room_type=room_type,
                    status=BookingStatus.CONFIRMED,
                    date_from=DATE_TO,
                    date_to=DATE_TO + timedelta(days=2),
                ),
            ]
        )
        await session.commit()

    response = await client.get("/api/v1/hotels", params=search_params())

    assert response.status_code == 200
    room = find_room(response.json(), "standard-queen")
    assert room["rooms_left"] == 10


async def test_search_excludes_a_fully_booked_room_type(
    client: AsyncClient,
) -> None:
    async with async_session_maker() as session:
        user, room_type = await prepare_search_data(session)
        room_type.quantity = 1
        session.add(
            build_booking(
                user_id=user.id,
                room_type=room_type,
                status=BookingStatus.CONFIRMED,
            )
        )
        await session.commit()

    response = await client.get("/api/v1/hotels", params=search_params())

    assert response.status_code == 200
    room_codes = {room["code"] for hotel in response.json() for room in hotel["rooms"]}
    assert "standard-queen" not in room_codes
    assert "bay-king" in room_codes


async def test_search_applies_price_filters_and_hotel_pagination(
    client: AsyncClient,
) -> None:
    async with async_session_maker() as session:
        await seed_catalog(session)

    filtered_response = await client.get(
        "/api/v1/hotels",
        params=search_params(min_price="150.00", max_price="200.00"),
    )
    paginated_response = await client.get(
        "/api/v1/hotels",
        params=search_params(limit="1", offset="1"),
    )

    assert filtered_response.status_code == 200
    filtered = filtered_response.json()
    assert [hotel["name"] for hotel in filtered] == [
        "Harbor View Seattle",
        "Lake Union Lodge",
    ]
    assert all(
        Decimal("150.00") <= Decimal(room["price_per_night"]) <= Decimal("200.00")
        for hotel in filtered
        for room in hotel["rooms"]
    )
    assert paginated_response.status_code == 200
    assert [hotel["name"] for hotel in paginated_response.json()] == [
        "Lake Union Lodge"
    ]


@pytest.mark.parametrize(
    "overrides",
    [
        {
            "date_from": (date.today() - timedelta(days=1)).isoformat(),
            "date_to": DATE_TO.isoformat(),
        },
        {"date_to": DATE_FROM.isoformat()},
        {"date_to": (DATE_FROM + timedelta(days=31)).isoformat()},
        {"min_price": "200.00", "max_price": "100.00"},
        {"min_price": "-1.00"},
    ],
)
async def test_search_rejects_invalid_ranges(
    client: AsyncClient,
    overrides: dict[str, str],
) -> None:
    response = await client.get(
        "/api/v1/hotels",
        params=search_params(**overrides),
    )

    assert response.status_code == 422


async def test_search_returns_an_empty_list_for_an_unknown_city(
    client: AsyncClient,
) -> None:
    async with async_session_maker() as session:
        await seed_catalog(session)

    response = await client.get(
        "/api/v1/hotels",
        params=search_params(city="Unknown City"),
    )

    assert response.status_code == 200
    assert response.json() == []
