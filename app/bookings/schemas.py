from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from app.bookings.models import Booking, BookingStatus
from app.bookings.policy import validate_stay_period
from app.money import format_money


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

    @classmethod
    def from_booking(
        cls,
        booking: Booking,
        *,
        now: datetime | None = None,
    ) -> "BookingRead":
        result = cls.model_validate(booking)
        current_time = now or datetime.now(UTC)
        if result.status == BookingStatus.CREATED and result.expires_at <= current_time:
            result.status = BookingStatus.EXPIRED
        return result

    model_config = ConfigDict(from_attributes=True)
