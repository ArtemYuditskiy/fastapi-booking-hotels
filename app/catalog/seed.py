import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import TypedDict

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.cache import RedisCatalogCache
from app.catalog.models import Hotel, RoomType
from app.database import async_session_maker
from app.logger import logger
from app.redis_client import create_redis_client


class RoomTypeSeed(TypedDict):
    code: str
    name: str
    description: str
    price: Decimal
    quantity: int
    services: list[str]


class HotelSeed(TypedDict):
    slug: str
    name: str
    city: str
    country: str
    address: str
    services: list[str]
    room_types: list[RoomTypeSeed]


@dataclass(frozen=True, slots=True)
class SeedResult:
    hotels: int
    room_types: int


CATALOG_SEED: list[HotelSeed] = [
    {
        "slug": "harbor-view-seattle",
        "name": "Harbor View Seattle",
        "city": "Seattle",
        "country": "United States",
        "address": "2217 Western Avenue, Seattle, WA",
        "services": ["wifi", "breakfast", "parking", "fitness"],
        "room_types": [
            {
                "code": "standard-queen",
                "name": "Standard Queen",
                "description": "A quiet queen room for short city stays.",
                "price": Decimal("128.00"),
                "quantity": 12,
                "services": ["wifi", "workspace", "coffee"],
            },
            {
                "code": "bay-king",
                "name": "Bay King",
                "description": "A king room with a partial waterfront view.",
                "price": Decimal("174.00"),
                "quantity": 8,
                "services": ["wifi", "workspace", "city-view"],
            },
            {
                "code": "corner-suite",
                "name": "Corner Suite",
                "description": "A spacious suite with a lounge area and bay windows.",
                "price": Decimal("246.00"),
                "quantity": 4,
                "services": ["wifi", "lounge", "espresso-machine"],
            },
        ],
    },
    {
        "slug": "pioneer-square-seattle",
        "name": "Pioneer Square House",
        "city": "Seattle",
        "country": "United States",
        "address": "89 South Jackson Street, Seattle, WA",
        "services": ["wifi", "parking", "cafe", "pet-friendly"],
        "room_types": [
            {
                "code": "classic-double",
                "name": "Classic Double",
                "description": "A compact double room in the historic district.",
                "price": Decimal("112.00"),
                "quantity": 14,
                "services": ["wifi", "workspace"],
            },
            {
                "code": "garden-queen",
                "name": "Garden Queen",
                "description": "A queen room facing a quiet brick courtyard.",
                "price": Decimal("149.00"),
                "quantity": 6,
                "services": ["wifi", "workspace", "courtyard-view"],
            },
        ],
    },
    {
        "slug": "lake-union-lodge-seattle",
        "name": "Lake Union Lodge",
        "city": "Seattle",
        "country": "United States",
        "address": "410 Westlake Avenue North, Seattle, WA",
        "services": ["wifi", "breakfast", "bike-rental", "fitness"],
        "room_types": [
            {
                "code": "urban-queen",
                "name": "Urban Queen",
                "description": "A bright queen room close to cafes and transit.",
                "price": Decimal("156.00"),
                "quantity": 9,
                "services": ["wifi", "workspace"],
            },
            {
                "code": "terrace-king",
                "name": "Terrace King",
                "description": "A king room with a terrace overlooking Lake Union.",
                "price": Decimal("212.00"),
                "quantity": 5,
                "services": ["wifi", "terrace", "espresso-machine"],
            },
            {
                "code": "family-loft",
                "name": "Family Loft",
                "description": "A loft-style room with extra sleeping space.",
                "price": Decimal("268.00"),
                "quantity": 3,
                "services": ["wifi", "sofa-bed", "kitchenette"],
            },
        ],
    },
    {
        "slug": "red-river-house-austin",
        "name": "Red River House",
        "city": "Austin",
        "country": "United States",
        "address": "604 Red River Street, Austin, TX",
        "services": ["wifi", "pool", "parking", "bar"],
        "room_types": [
            {
                "code": "comfort-king",
                "name": "Comfort King",
                "description": "A relaxed king room for weekend trips.",
                "price": Decimal("122.00"),
                "quantity": 14,
                "services": ["wifi", "coffee", "workspace"],
            },
            {
                "code": "poolside-double",
                "name": "Poolside Double",
                "description": "A double room near the outdoor pool.",
                "price": Decimal("151.00"),
                "quantity": 7,
                "services": ["wifi", "pool-access"],
            },
            {
                "code": "music-suite",
                "name": "Music Suite",
                "description": "A suite with extra living space near downtown venues.",
                "price": Decimal("219.00"),
                "quantity": 4,
                "services": ["wifi", "lounge", "sound-system"],
            },
        ],
    },
    {
        "slug": "south-congress-austin",
        "name": "South Congress Hotel",
        "city": "Austin",
        "country": "United States",
        "address": "1712 South Congress Avenue, Austin, TX",
        "services": ["wifi", "breakfast", "fitness", "meeting-rooms"],
        "room_types": [
            {
                "code": "city-double",
                "name": "City Double",
                "description": "A practical double room near local shops and cafes.",
                "price": Decimal("109.00"),
                "quantity": 16,
                "services": ["wifi", "workspace"],
            },
            {
                "code": "avenue-king",
                "name": "Avenue King",
                "description": "A king room overlooking South Congress Avenue.",
                "price": Decimal("178.00"),
                "quantity": 8,
                "services": ["wifi", "city-view", "coffee"],
            },
        ],
    },
    {
        "slug": "lady-bird-lake-austin",
        "name": "Lady Bird Lake Inn",
        "city": "Austin",
        "country": "United States",
        "address": "805 Riverside Drive, Austin, TX",
        "services": ["wifi", "pool", "parking", "bike-rental"],
        "room_types": [
            {
                "code": "park-queen",
                "name": "Park Queen",
                "description": "A bright queen room near the lakeside trail.",
                "price": Decimal("105.00"),
                "quantity": 18,
                "services": ["wifi", "coffee"],
            },
            {
                "code": "patio-king",
                "name": "Patio King",
                "description": "A king room with a private shaded patio.",
                "price": Decimal("148.00"),
                "quantity": 9,
                "services": ["wifi", "patio", "workspace"],
            },
            {
                "code": "lake-suite",
                "name": "Lake Suite",
                "description": "A large suite with a separate lounge and lake view.",
                "price": Decimal("225.00"),
                "quantity": 4,
                "services": ["wifi", "lake-view", "lounge"],
            },
        ],
    },
    {
        "slug": "flatiron-house-new-york",
        "name": "Flatiron House",
        "city": "New York",
        "country": "United States",
        "address": "27 West 24th Street, New York, NY",
        "services": ["wifi", "breakfast", "fitness", "restaurant"],
        "room_types": [
            {
                "code": "standard-king",
                "name": "Standard King",
                "description": "A comfortable king room in the business district.",
                "price": Decimal("179.00"),
                "quantity": 15,
                "services": ["wifi", "workspace"],
            },
            {
                "code": "executive-king",
                "name": "Executive King",
                "description": "A larger king room with lounge access.",
                "price": Decimal("249.00"),
                "quantity": 7,
                "services": ["wifi", "lounge-access", "espresso-machine"],
            },
        ],
    },
    {
        "slug": "brickell-garden-miami",
        "name": "Brickell Garden Miami",
        "city": "Miami",
        "country": "United States",
        "address": "92 Southeast 8th Street, Miami, FL",
        "services": ["wifi", "pool", "breakfast", "spa"],
        "room_types": [
            {
                "code": "garden-double",
                "name": "Garden Double",
                "description": "A double room facing tropical garden paths.",
                "price": Decimal("154.00"),
                "quantity": 11,
                "services": ["wifi", "garden-view"],
            },
            {
                "code": "balcony-king",
                "name": "Balcony King",
                "description": "A king room with a private balcony.",
                "price": Decimal("226.00"),
                "quantity": 6,
                "services": ["wifi", "balcony", "coffee"],
            },
            {
                "code": "spa-suite",
                "name": "Spa Suite",
                "description": "A suite with extra space and spa access included.",
                "price": Decimal("338.00"),
                "quantity": 3,
                "services": ["wifi", "spa-access", "lounge"],
            },
        ],
    },
    {
        "slug": "brooklyn-heights-new-york",
        "name": "Brooklyn Heights Hotel",
        "city": "New York",
        "country": "United States",
        "address": "146 Montague Street, Brooklyn, NY",
        "services": ["wifi", "breakfast", "cafe", "courtyard"],
        "room_types": [
            {
                "code": "courtyard-queen",
                "name": "Courtyard Queen",
                "description": "A queen room overlooking the interior courtyard.",
                "price": Decimal("165.00"),
                "quantity": 10,
                "services": ["wifi", "courtyard-view"],
            },
            {
                "code": "loft-king",
                "name": "Loft King",
                "description": "A high-ceiling king room in a restored townhouse.",
                "price": Decimal("235.00"),
                "quantity": 5,
                "services": ["wifi", "workspace", "coffee"],
            },
        ],
    },
    {
        "slug": "hudson-park-new-york",
        "name": "Hudson Park Hotel",
        "city": "New York",
        "country": "United States",
        "address": "518 West 38th Street, New York, NY",
        "services": ["wifi", "breakfast", "fitness", "rooftop-bar"],
        "room_types": [
            {
                "code": "city-queen",
                "name": "City Queen",
                "description": "A queen room designed for short Manhattan stays.",
                "price": Decimal("198.00"),
                "quantity": 13,
                "services": ["wifi", "coffee"],
            },
            {
                "code": "studio-king",
                "name": "Studio King",
                "description": "A studio room with a king bed and compact kitchenette.",
                "price": Decimal("285.00"),
                "quantity": 6,
                "services": ["wifi", "kitchenette", "workspace"],
            },
            {
                "code": "hudson-suite",
                "name": "Hudson Suite",
                "description": "A suite with a lounge area and river view.",
                "price": Decimal("410.00"),
                "quantity": 4,
                "services": ["wifi", "river-view", "lounge"],
            },
        ],
    },
    {
        "slug": "south-beach-miami",
        "name": "South Beach House",
        "city": "Miami",
        "country": "United States",
        "address": "840 Collins Avenue, Miami Beach, FL",
        "services": ["wifi", "breakfast", "beach-access", "restaurant"],
        "room_types": [
            {
                "code": "beach-double",
                "name": "Beach Double",
                "description": "A double room within walking distance of the beach.",
                "price": Decimal("142.00"),
                "quantity": 9,
                "services": ["wifi", "coffee"],
            },
            {
                "code": "art-deco-king",
                "name": "Art Deco King",
                "description": "A king room with Art Deco details and extra workspace.",
                "price": Decimal("198.00"),
                "quantity": 5,
                "services": ["wifi", "workspace", "city-view"],
            },
        ],
    },
    {
        "slug": "coconut-grove-miami",
        "name": "Coconut Grove Retreat",
        "city": "Miami",
        "country": "United States",
        "address": "2980 McFarlane Road, Miami, FL",
        "services": ["wifi", "breakfast", "pool", "fitness"],
        "room_types": [
            {
                "code": "classic-queen",
                "name": "Classic Queen",
                "description": "A quiet queen room close to the marina and cafes.",
                "price": Decimal("129.00"),
                "quantity": 12,
                "services": ["wifi", "coffee"],
            },
            {
                "code": "marina-king",
                "name": "Marina King",
                "description": "A king room with a view toward the marina.",
                "price": Decimal("205.00"),
                "quantity": 6,
                "services": ["wifi", "marina-view", "workspace"],
            },
            {
                "code": "grove-suite",
                "name": "Grove Suite",
                "description": "A suite with a separate lounge and shaded balcony.",
                "price": Decimal("295.00"),
                "quantity": 3,
                "services": ["wifi", "lounge", "balcony"],
            },
        ],
    },
]


async def seed_catalog(session: AsyncSession) -> SeedResult:
    room_types_count = 0
    async with session.begin():
        for hotel_data in CATALOG_SEED:
            room_types = hotel_data["room_types"]
            hotel_values = {
                "slug": hotel_data["slug"],
                "name": hotel_data["name"],
                "city": hotel_data["city"],
                "country": hotel_data["country"],
                "address": hotel_data["address"],
                "services": hotel_data["services"],
            }
            hotel_statement = (
                insert(Hotel)
                .values(**hotel_values)
                .on_conflict_do_update(
                    index_elements=[Hotel.slug],
                    set_={
                        key: value
                        for key, value in hotel_values.items()
                        if key != "slug"
                    },
                )
                .returning(Hotel.id)
            )
            hotel_id = await session.scalar(hotel_statement)
            if hotel_id is None:
                raise RuntimeError(f"Could not seed hotel {hotel_data['slug']}")

            for room_type in room_types:
                room_values = {
                    **room_type,
                    "hotel_id": hotel_id,
                    "currency": "USD",
                }
                room_statement = (
                    insert(RoomType)
                    .values(**room_values)
                    .on_conflict_do_update(
                        constraint="uq_room_types_hotel_id_code",
                        set_={
                            "name": room_values["name"],
                            "description": room_values["description"],
                            "price": room_values["price"],
                            "currency": room_values["currency"],
                            "quantity": room_values["quantity"],
                            "services": room_values["services"],
                        },
                    )
                )
                await session.execute(room_statement)
                room_types_count += 1

    return SeedResult(hotels=len(CATALOG_SEED), room_types=room_types_count)


async def main() -> None:
    async with async_session_maker() as session:
        result = await seed_catalog(session)

    redis_client = create_redis_client()
    try:
        await RedisCatalogCache(redis_client).invalidate()
    finally:
        await redis_client.close()

    logger.info(
        "catalog_seeded",
        extra={
            "hotels_count": result.hotels,
            "room_types_count": result.room_types,
        },
    )


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
