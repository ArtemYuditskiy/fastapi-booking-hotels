from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Hotel(Base):
    __tablename__ = "hotels"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    city: Mapped[str] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(255))
    services: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ARRAY(String(50))),
        default=list,
    )

    room_types: Mapped[list["RoomType"]] = relationship(
        back_populates="hotel",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (Index("ix_hotels_city_lower", func.lower(city)),)


class RoomType(Base):
    __tablename__ = "room_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotels.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(500))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(
        String(3), default="USD", server_default="USD"
    )
    quantity: Mapped[int]
    services: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ARRAY(String(50))),
        default=list,
    )

    hotel: Mapped[Hotel] = relationship(back_populates="room_types")

    __table_args__ = (
        CheckConstraint("price >= 0", name="price_non_negative"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("currency = 'USD'", name="currency_usd"),
        UniqueConstraint("hotel_id", "code", name="uq_room_types_hotel_id_code"),
    )
