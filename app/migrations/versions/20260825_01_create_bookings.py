"""Create bookings table.

Revision ID: 20260825_01
Revises: 20260824_01
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260825_01"
down_revision: str | None = "20260824_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

booking_status = sa.Enum(
    "created",
    "confirmed",
    "cancelled",
    "expired",
    name="booking_status",
)


def upgrade() -> None:
    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("room_type_id", sa.Integer(), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column(
            "price_per_night",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
        ),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("total_cost", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "status",
            booking_status,
            server_default="created",
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("currency = 'USD'", name=op.f("ck_bookings_currency_usd")),
        sa.CheckConstraint("date_to > date_from", name=op.f("ck_bookings_dates_valid")),
        sa.CheckConstraint(
            "price_per_night >= 0",
            name=op.f("ck_bookings_price_non_negative"),
        ),
        sa.CheckConstraint(
            "total_cost >= 0",
            name=op.f("ck_bookings_total_cost_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["room_type_id"],
            ["room_types.id"],
            name=op.f("fk_bookings_room_type_id_room_types"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_bookings_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bookings")),
    )
    op.create_index(
        "ix_bookings_availability_lookup",
        "bookings",
        ["room_type_id", "status", "date_from", "date_to"],
        unique=False,
    )
    op.create_index("ix_bookings_user_id", "bookings", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_bookings_user_id", table_name="bookings")
    op.drop_index("ix_bookings_availability_lookup", table_name="bookings")
    op.drop_table("bookings")
    booking_status.drop(op.get_bind())
