"""Create hotel catalog tables.

Revision ID: 20260824_01
Revises: 20260823_01
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260824_01"
down_revision: str | None = "20260823_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hotels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("services", postgresql.ARRAY(sa.String(length=50)), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hotels")),
    )
    op.create_index(
        "ix_hotels_city_lower",
        "hotels",
        [sa.text("lower(city)")],
        unique=False,
    )
    op.create_index(op.f("ix_hotels_slug"), "hotels", ["slug"], unique=True)

    op.create_table(
        "room_types",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("services", postgresql.ARRAY(sa.String(length=50)), nullable=False),
        sa.CheckConstraint("currency = 'USD'", name=op.f("ck_room_types_currency_usd")),
        sa.CheckConstraint("price >= 0", name=op.f("ck_room_types_price_non_negative")),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_room_types_quantity_positive")),
        sa.ForeignKeyConstraint(
            ["hotel_id"],
            ["hotels.id"],
            name=op.f("fk_room_types_hotel_id_hotels"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_room_types")),
        sa.UniqueConstraint("hotel_id", "code", name="uq_room_types_hotel_id_code"),
    )


def downgrade() -> None:
    op.drop_table("room_types")
    op.drop_index(op.f("ix_hotels_slug"), table_name="hotels")
    op.drop_index("ix_hotels_city_lower", table_name="hotels")
    op.drop_table("hotels")
