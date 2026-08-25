from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BookingStatus(StrEnum):
    CREATED = "created"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


booking_status_enum = Enum(
    BookingStatus,
    name="booking_status",
    values_callable=lambda members: [member.value for member in members],
)


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    room_type_id: Mapped[int] = mapped_column(
        ForeignKey("room_types.id", ondelete="RESTRICT")
    )
    date_from: Mapped[date] = mapped_column(Date)
    date_to: Mapped[date] = mapped_column(Date)
    price_per_night: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        server_default="USD",
    )
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[BookingStatus] = mapped_column(
        booking_status_enum,
        default=BookingStatus.CREATED,
        server_default=BookingStatus.CREATED.value,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint("date_to > date_from", name="dates_valid"),
        CheckConstraint("price_per_night >= 0", name="price_non_negative"),
        CheckConstraint("total_cost >= 0", name="total_cost_non_negative"),
        CheckConstraint("currency = 'USD'", name="currency_usd"),
        Index("ix_bookings_user_id", "user_id"),
        Index(
            "ix_bookings_availability_lookup",
            "room_type_id",
            "status",
            "date_from",
            "date_to",
        ),
    )
