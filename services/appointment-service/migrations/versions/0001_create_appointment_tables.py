"""Create appointments and outbox_events tables

Revision ID: 0001
Revises:
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SLOT_OCCUPYING = "status IN ('BOOKED', 'CHECKED_IN', 'COMPLETED')"


def upgrade() -> None:
    is_postgresql = op.get_bind().dialect.name == "postgresql"
    if is_postgresql:
        # Needed for "provider_id WITH =" inside the GiST exclusion constraint (trusted extension, PG13+).
        op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # patient_id / provider_id / facility_id reference other services by ID only: no cross-service FKs.
    op.create_table(
        "appointments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("facility_id", sa.Uuid(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reason_code", sa.String(length=32), nullable=False),
        sa.Column("cancellation_reason", sa.String(length=32), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name=op.f("ck_appointments_ends_after_starts")),
        sa.CheckConstraint(
            "status IN ('BOOKED', 'CHECKED_IN', 'COMPLETED', 'CANCELLED', 'NO_SHOW')",
            name=op.f("ck_appointments_status_allowed"),
        ),
        sa.CheckConstraint(
            "(status = 'CANCELLED') = (cancellation_reason IS NOT NULL)",
            name=op.f("ck_appointments_cancellation_reason_iff_cancelled"),
        ),
        sa.CheckConstraint(
            "reason_code = upper(reason_code)", name=op.f("ck_appointments_reason_code_uppercase")
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_appointments_version_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appointments")),
    )
    op.create_index("ix_appointments_provider_id_starts_at", "appointments", ["provider_id", "starts_at"])
    op.create_index("ix_appointments_patient_id_starts_at", "appointments", ["patient_id", "starts_at"])
    op.create_index("ix_appointments_status", "appointments", ["status"])
    if is_postgresql:
        # Final authority against double-booking, including concurrent requests ('[)' = adjacent allowed).
        op.execute(
            "ALTER TABLE appointments ADD CONSTRAINT ex_appointments_provider_overlap "
            "EXCLUDE USING gist (provider_id WITH =, tstzrange(starts_at, ends_at, '[)') WITH &&) "
            f"WHERE ({_SLOT_OCCUPYING})"
        )

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("aggregate_type", sa.String(length=32), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox_events")),
    )
    op.create_index(
        "ix_outbox_events_published_at_occurred_at", "outbox_events", ["published_at", "occurred_at"]
    )
    op.create_index("ix_outbox_events_aggregate_id", "outbox_events", ["aggregate_id"])


def downgrade() -> None:
    # WARNING: drops all appointment and outbox data. Never run against a live database without a
    # verified backup and explicit authorization. The btree_gist extension is left installed because
    # it may have existed before this migration and is harmless.
    op.drop_index("ix_outbox_events_aggregate_id", table_name="outbox_events")
    op.drop_index("ix_outbox_events_published_at_occurred_at", table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_index("ix_appointments_status", table_name="appointments")
    op.drop_index("ix_appointments_patient_id_starts_at", table_name="appointments")
    op.drop_index("ix_appointments_provider_id_starts_at", table_name="appointments")
    op.drop_table("appointments")
