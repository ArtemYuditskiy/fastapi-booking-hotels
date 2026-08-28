from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from app.bookings.policy import validate_stay_period
from app.money import format_money


class HotelRead(BaseModel):
    id: int
    slug: str
    name: str
    city: str
    country: str
    address: str
    services: list[str]

    model_config = ConfigDict(from_attributes=True)


class RoomTypeRead(BaseModel):
    id: int
    hotel_id: int
    code: str
    name: str
    description: str
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    currency: Literal["USD"]
    quantity: int = Field(gt=0)
    services: list[str]

    @field_serializer("price")
    def serialize_price(self, value: Decimal) -> str:
        return format_money(value)

    model_config = ConfigDict(from_attributes=True)


class HotelSearchParams(BaseModel):
    city: str = Field(min_length=1, max_length=100)
    date_from: date
    date_to: date
    min_price: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=10,
        decimal_places=2,
    )
    max_price: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=10,
        decimal_places=2,
    )
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @field_validator("city")
    @classmethod
    def normalize_city(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("City must not be blank")
        return normalized

    @model_validator(mode="after")
    def validate_search_range(self) -> "HotelSearchParams":
        validate_stay_period(self.date_from, self.date_to)
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price must not exceed max_price")
        return self


class AvailableRoomTypeRead(BaseModel):
    room_type_id: int
    code: str
    name: str
    description: str
    rooms_left: int = Field(gt=0)
    price_per_night: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    currency: Literal["USD"]
    total_cost: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    services: list[str]

    @field_serializer("price_per_night", "total_cost")
    def serialize_money(self, value: Decimal) -> str:
        return format_money(value)


class HotelSearchResult(HotelRead):
    rooms: list[AvailableRoomTypeRead]
