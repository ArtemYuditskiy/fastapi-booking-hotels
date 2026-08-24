from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


def format_money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


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
