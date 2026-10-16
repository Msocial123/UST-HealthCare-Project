"""Create facilities, departments and rooms tables

Revision ID: 0001
Revises:
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "facilities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("facility_type", sa.String(length=32), nullable=False),
        sa.Column("address_line1", sa.String(length=200), nullable=False),
        sa.Column("address_line2", sa.String(length=200), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("state_province", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=16), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("main_phone", sa.String(length=32), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("code = upper(code)", name=op.f("ck_facilities_code_uppercase")),
        sa.CheckConstraint(
            "facility_type IN ('HOSPITAL', 'CLINIC', 'DIAGNOSTIC_CENTER')",
            name=op.f("ck_facilities_facility_type_allowed"),
        ),
        sa.CheckConstraint(
            "country_code = upper(country_code)", name=op.f("ck_facilities_country_code_uppercase")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_facilities")),
        sa.UniqueConstraint("code", name=op.f("uq_facilities_code")),
    )
    op.create_index("ix_facilities_name", "facilities", ["name"])
    op.create_table(
        "departments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("facility_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("floor", sa.String(length=16), nullable=True),
        sa.Column("phone_extension", sa.String(length=10), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("code = upper(code)", name=op.f("ck_departments_code_uppercase")),
        sa.ForeignKeyConstraint(
            ["facility_id"],
            ["facilities.id"],
            name=op.f("fk_departments_facility_id_facilities"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_departments")),
        sa.UniqueConstraint("facility_id", "code", name="uq_departments_facility_id_code"),
    )
    op.create_table(
        "rooms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("room_number", sa.String(length=16), nullable=False),
        sa.Column("room_type", sa.String(length=16), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("room_number = upper(room_number)", name=op.f("ck_rooms_room_number_uppercase")),
        sa.CheckConstraint(
            "room_type IN ('CONSULTATION', 'WARD', 'PROCEDURE', 'OTHER')",
            name=op.f("ck_rooms_room_type_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            name=op.f("fk_rooms_department_id_departments"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rooms")),
        sa.UniqueConstraint("department_id", "room_number", name="uq_rooms_department_id_room_number"),
    )


def downgrade() -> None:
    op.drop_table("rooms")
    op.drop_table("departments")
    op.drop_index("ix_facilities_name", table_name="facilities")
    op.drop_table("facilities")
