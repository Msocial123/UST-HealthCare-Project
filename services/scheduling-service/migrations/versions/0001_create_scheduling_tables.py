"""Create working_hours and availability_exceptions tables

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


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    # provider_id / facility_id reference other services by ID only: no cross-service foreign keys.
    op.create_table(
        "working_hours",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("facility_id", sa.Uuid(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("start_local_time", sa.Time(), nullable=False),
        sa.Column("end_local_time", sa.Time(), nullable=False),
        sa.Column("slot_minutes", sa.SmallInteger(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name=op.f("ck_working_hours_weekday_range")),
        sa.CheckConstraint(
            "slot_minutes BETWEEN 5 AND 120", name=op.f("ck_working_hours_slot_minutes_range")
        ),
        sa.CheckConstraint(
            "end_local_time > start_local_time", name=op.f("ck_working_hours_end_after_start")
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from", name=op.f("ck_working_hours_valid_range")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_working_hours")),
    )
    op.create_index("ix_working_hours_provider_id_weekday", "working_hours", ["provider_id", "weekday"])
    op.create_table(
        "availability_exceptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("facility_id", sa.Uuid(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("reason_code", sa.String(length=32), nullable=False),
        *_audit_columns(),
        sa.CheckConstraint("ends_at > starts_at", name=op.f("ck_availability_exceptions_ends_after_starts")),
        sa.CheckConstraint(
            "type IN ('LEAVE', 'HOLIDAY', 'BLOCKED', 'EXTRA_HOURS')",
            name=op.f("ck_availability_exceptions_type_allowed"),
        ),
        sa.CheckConstraint(
            "type <> 'EXTRA_HOURS' OR facility_id IS NOT NULL",
            name=op.f("ck_availability_exceptions_extra_hours_facility"),
        ),
        sa.CheckConstraint(
            "reason_code = upper(reason_code)", name=op.f("ck_availability_exceptions_reason_code_uppercase")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_availability_exceptions")),
    )
    op.create_index(
        "ix_availability_exceptions_provider_id_starts_at",
        "availability_exceptions",
        ["provider_id", "starts_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_availability_exceptions_provider_id_starts_at", table_name="availability_exceptions")
    op.drop_table("availability_exceptions")
    op.drop_index("ix_working_hours_provider_id_weekday", table_name="working_hours")
    op.drop_table("working_hours")
