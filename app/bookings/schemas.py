from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from app.bookings.models import BookingStatus
from app.bookings.policy import validate_stay_period


def format_money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


class BookingCreate(BaseModel):
    room_type_id: int = Field(gt=0)
    date_from: date
    date_to: date

    @model_validator(mode="after")
    def validate_dates(self) -> "BookingCreate":
        validate_stay_period(self.date_from, self.date_to)
        return self


class BookingRead(BaseModel):
    id: int
    user_id: int
    room_type_id: int
    date_from: date
    date_to: date
    price_per_night: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    currency: Literal["USD"]
    total_cost: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    status: BookingStatus
    expires_at: datetime
    created_at: datetime
    updated_at: datetime

    @field_serializer("price_per_night", "total_cost")
    def serialize_money(self, value: Decimal) -> str:
        return format_money(value)

    model_config = ConfigDict(from_attributes=True)
